"""Regenerate CPU-comparison charts/tables from the four archived runs; no database needed."""
from pathlib import Path
import hashlib
import json
import math
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.concurrency import report

RUNS = {
    'morning': [(1, '20260929T082232Z-writes-75f6c965'), (2, '20260929T083304Z-writes-98fdb761')],
    'evening': [(1, '20260929T164329Z-writes-17d5c81f'), (2, '20260929T162946Z-writes-18a13d6d')],
}
ENGINES = ('InnoDB', 'Aria', 'MyISAM', 'MEMORY', 'ROCKSDB')
MODES = ('disjoint', 'hotspot')


def collect():
    records, provenance = [], []
    for block, entries in RUNS.items():
        runs = []
        for quota, run_id in entries:
            folder = ROOT / 'evidence/cpu-comparison' / run_id
            raw = (folder / 'results.json').read_bytes()
            run = json.loads(raw)
            if run['status'] != 'completed' or run['run_id'] != run_id or run['expected_runner_cpus'] != quota:
                raise ValueError('Wrong or incomplete archived run')
            if report(run) != (folder / 'summary.md').read_text(encoding='utf-8'):
                raise ValueError('Summary differs from raw data')
            if len(run['trials']) != 150:
                raise ValueError('Incomplete trial matrix')
            runs.append(run)
            provenance.append({'run_id': run_id, 'block': block, 'runner_cpus': quota,
                               'results_sha256': hashlib.sha256(raw).hexdigest()})
            for engine in ENGINES:
                for mode in MODES:
                    for clients in (1, 2, 4):
                        trials = [t for t in run['trials'] if (t['engine'], t['mode'], t['clients']) == (engine, mode, clients)]
                        if len(trials) != 5 or {t['round'] for t in trials} != set(range(1, 6)):
                            raise ValueError('Missing or duplicated rounds')
                        rates = []
                        throttled = 0
                        for t in trials:
                            if t['status'] != 'completed' or t['completed'] != 1000:
                                raise ValueError('Failed or incomplete trial')
                            rate = t['updates_per_second']
                            if not math.isfinite(rate) or not math.isclose(rate, 1000/t['elapsed_seconds'], rel_tol=1e-12):
                                raise ValueError('Invalid throughput')
                            cpu = t['runner_cpu']
                            if cpu['cgroup_status'] != 'available' or 'nr_throttled' not in cpu['counter_delta']:
                                raise ValueError('CPU counters unavailable')
                            throttled += cpu['counter_delta']['nr_throttled'] > 0
                            rates.append(rate)
                        records.append({'block': block, 'run_id': run_id, 'runner_cpus': quota,
                                        'engine': engine, 'pattern': mode, 'clients': clients,
                                        'mean_updates_s': statistics.mean(rates),
                                        'sample_sd_updates_s': statistics.stdev(rates),
                                        'trials': 5, 'throttled_trials': throttled})
        for key in ('config', 'source_sha256', 'dataset_sha256', 'global_variables', 'session_variables'):
            if runs[0][key] != runs[1][key]:
                raise ValueError('Comparison differs in ' + key)
    return records, provenance


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'svg.fonttype': 'none', 'svg.hashsalt': 'cu-cpu-comparison-v1',
                         'axes.spines.top': False, 'axes.spines.right': False})
    records, provenance = collect()
    out = ROOT / 'docs/figures'
    out.mkdir(exist_ok=True)
    titles = {'morning': 'Morning: battery saver on (team-reported)',
              'evening': 'Evening: plugged in, battery saver off (team-reported)'}
    for block in RUNS:
        fig, axes = plt.subplots(5, 2, figsize=(11, 14))
        for row, engine in enumerate(ENGINES):
            maximum = max(r['mean_updates_s'] + r['sample_sd_updates_s'] for r in records if r['engine'] == engine) * 1.12
            for col, mode in enumerate(MODES):
                ax = axes[row, col]
                for quota, color in ((1, '#2463A6'), (2, '#C05A12')):
                    points = sorted((r for r in records if (r['block'], r['engine'], r['pattern'], r['runner_cpus']) == (block, engine, mode, quota)), key=lambda r:r['clients'])
                    ax.errorbar([r['clients'] for r in points], [r['mean_updates_s'] for r in points],
                                yerr=[r['sample_sd_updates_s'] for r in points], marker='o', capsize=4,
                                linewidth=1.7, color=color, label=f'{quota} runner CPU' + ('s' if quota == 2 else ''))
                ax.set(title=f'{engine} | {mode}', xlabel='Concurrent clients', ylabel='Updates / second', ylim=(0, maximum), xticks=[1, 2, 4])
                ax.grid(axis='y', alpha=.2)
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.suptitle(titles[block], fontsize=17, y=.988)
        fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .967), ncol=2, frameon=False)
        fig.text(.5, .012, 'Mean ± sample SD of five trials per point; SD is not a confidence interval.\n1000 total updates per trial. Same server reused; durability differs by engine.', ha='center', fontsize=10)
        fig.tight_layout(rect=(0, .055, 1, .94), h_pad=1.5)
        fig.savefig(out / f'cpu-{block}.svg', metadata={'Date': None})
        plt.close(fig)
    (out / 'cpu-chart-data.json').write_text(json.dumps({'provenance': provenance, 'records': records}, indent=2)+'\n', encoding='utf-8')
    lines = ['# CPU comparison: all measured conditions', '',
             'Mean and sample SD across five trials on one reused server. Power conditions are not pooled.', '',
             '| Block | Engine | Pattern | Clients | Runner CPUs | Mean updates/s | Sample SD | Throttled trials / 5 |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in records:
        lines.append(f"| {r['block']} | {r['engine']} | {r['pattern']} | {r['clients']} | {r['runner_cpus']} | {r['mean_updates_s']:.2f} | {r['sample_sd_updates_s']:.2f} | {r['throttled_trials']} |")
    (ROOT / 'docs/cpu-measurements.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('Generated two SVG charts, 120 condition summaries and raw-file SHA-256 provenance.')


if __name__ == '__main__':
    main()
