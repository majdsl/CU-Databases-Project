"""Reproduce findings from the two archived October 6 recovery runs; no Docker calls."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.recovery import make_rows, compare_rows
from benchmarks.core import engine_schedule

PILOT = '20261006T155703Z-recovery-adbea5ba'
FULL = '20261006T161514Z-recovery-99656d7e'
ENGINES = ['InnoDB', 'Aria', 'MyISAM', 'MEMORY', 'ROCKSDB']
MODES = ['clean', 'sigkill']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_run(run_id, pilot):
    folder = ROOT / 'evidence/recovery' / run_id
    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    rounds = 1 if pilot else 5
    require(result['status'] == 'completed' and result['pilot'] == pilot,
            'Incomplete or incorrectly labeled run')
    require(result['run_id'] == run_id and result['rounds'] == rounds
            and result['rows'] == 1000 and result['seed'] == 20260923,
            'This report is specific to the archived 1,000-row experiments')
    require(not result['retained_projects'] and 'active_project' not in result,
            'Unresolved trial resources')
    schedule = engine_schedule(result['seed'], 5)[:rounds]
    require(result['schedule'] == schedule, 'Wrong engine schedule')
    expected_order = [(r, engine, mode)
        for r, engines in enumerate(schedule, 1)
        for position, engine in enumerate(engines)
        for mode in (MODES if (r + position) % 2 else list(reversed(MODES)))]
    require([(t['round'], t['engine'], t['mode']) for t in result['trials']]
            == expected_order, 'Missing, repeated or out-of-order trials')
    require(len({t['project'] for t in result['trials']}) == rounds * 10,
            'Trial projects are not unique')
    expected = make_rows(result['rows'], result['seed'])
    expected_hash = compare_rows(expected, expected)['expected_dataset_sha256']
    observations = []
    for index, trial in enumerate(result['trials'], 1):
        engine, mode = trial['engine'], trial['mode']
        receipt = trial['acknowledgments']
        require(receipt['engine'] == engine and receipt['rows'] == 1000
                and receipt['seed'] == result['seed']
                and receipt['acknowledged_ids'] == list(range(1, 1001))
                and receipt['acknowledged_count'] == 1000
                and receipt['in_flight_at_receipt'] == 0
                and receipt['expected_dataset_sha256'] == expected_hash,
                f'Invalid acknowledgment receipt: {index}')
        state = trial['stopped_state']
        require(state['Status'] == 'exited' and not state['OOMKilled']
                and state['ExitCode'] == (0 if mode == 'clean' else 137),
                f'Wrong stop state: {index}')
        relative = f'{index:02d}-{engine.lower()}-{mode}/restart.log'
        require(trial['restart_log'].replace('\\', '/') == relative,
                f'Unexpected log path: {index}')
        log_path = folder / relative
        log_bytes = log_path.read_bytes()
        require(hashlib.sha256(log_bytes).hexdigest() == trial['restart_log_sha256'],
                f'Log checksum mismatch: {log_path}; preserve log bytes with -text')
        require(json.loads(log_path.with_name('acknowledgments.json').read_text(
                encoding='utf-8')) == receipt, f'Receipt copies differ: {index}')
        # Fail closed if the archived outcome changes; never substitute unknown survival with zero.
        oracle = compare_rows(expected, [] if engine == 'MEMORY' else expected)
        observation = trial['observation']
        require(all(observation.get(k) == v for k, v in oracle.items()),
                f'Unexpected data outcome: {index}; review evidence before reporting')
        require(trial['cleanup'] == 'removed_own_disposable_resources',
                f'Unreviewed cleanup outcome: {index}')
        checks = observation.get('check_table_messages', [])
        require(bool(checks), f'Missing CHECK TABLE diagnostic: {index}')
        if engine == 'MEMORY':
            require(any("doesn't support check" in str(m).lower() for m in checks),
                    'Unexpected MEMORY diagnostic')
        else:
            require(all(m[2:] == ['status', 'OK'] for m in checks),
                    f'Unexpected CHECK TABLE diagnostic: {index}')
        seconds = trial['restart_through_verification_seconds']
        require(math.isfinite(seconds) and seconds >= 0, 'Invalid timing')
        log = log_bytes.decode('utf-8')
        observations.append(dict(run_id=run_id, pilot=pilot, trial=index,
            engine=engine, round=trial['round'], stop=mode,
            acknowledged_rows=1000, intact_rows=observation['intact_rows'],
            missing_rows=len(observation['missing_ids']), changed_rows=len(observation['changed_ids']),
            unexpected_rows=len(observation['unexpected_ids']), duplicate_rows=len(observation['duplicate_ids']),
            intact_percent=observation['intact_rows'] / 10,
            restart_through_verification_seconds=seconds,
            crashed_table_warning='is marked as crashed and should be repaired' in log,
            aria_recovery_done='Aria engine: recovery done' in log,
            log_sha256=trial['restart_log_sha256']))
    for key in ['db_image_id', 'runner_image_id']:
        require(len({t[key] for t in result['trials']}) == 1, 'Image changed within run')
    return result, observations


def summarize(rows):
    groups = []
    for engine in ENGINES:
        for mode in MODES:
            group = [r for r in rows if r['engine'] == engine and r['stop'] == mode]
            values = [r['restart_through_verification_seconds'] for r in group]
            groups.append(dict(engine=engine, stop=mode, trials=len(group),
                intact_rows_per_trial=sorted({r['intact_rows'] for r in group}),
                crashed_table_warning_trials=sum(r['crashed_table_warning'] for r in group),
                aria_recovery_done_trials=sum(r['aria_recovery_done'] for r in group),
                restart_seconds_median=statistics.median(values),
                restart_seconds_min=min(values), restart_seconds_max=max(values)))
    return groups


def charts(rows, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'svg.hashsalt': 'cu-recovery-findings-v1'})
    colors = ['#2166ac', '#c85b18']
    labels = ['Clean restart', 'Process crash (SIGKILL)']
    for metric, name, title, ylabel in [
        ('intact_percent', 'recovery-row-survival', 'Rows survived in four engines; MEMORY emptied',
         'Intact acknowledged rows (%)'),
        ('restart_through_verification_seconds', 'recovery-restart-verification',
         'Restart through verification: all 50 trials', 'Elapsed time (seconds)')]:
        fig, ax = plt.subplots(figsize=(10, 5.8))
        fig.subplots_adjust(left=.10, right=.98, bottom=.24, top=.78)
        for j, mode in enumerate(MODES):
            for i, engine in enumerate(ENGINES):
                group = [r for r in rows if r['engine'] == engine and r['stop'] == mode]
                values = [r[metric] for r in group]
                center = i + (-.18 if j == 0 else .18)
                ax.scatter([center + (k-2)*.035 for k in range(5)], values,
                           c=colors[j], marker='o' if j == 0 else '^', s=38,
                           label=labels[j] if i == 0 else None, zorder=3)
                median = statistics.median(values)
                ax.plot([center-.12, center+.12], [median, median], c=colors[j], lw=2)
                if metric == 'intact_percent':
                    ax.text(center, median + (4 if median == 0 else -9),
                            f'{median:.0f}%', ha='center', fontsize=10, color=colors[j])
        ax.set_xticks(range(5), ['InnoDB', 'Aria', 'MyISAM', 'MEMORY', 'MyRocks\n(ROCKSDB)'])
        ax.set_ylabel(ylabel)
        ax.set_ylim((-5, 108) if metric == 'intact_percent' else (0, 6))
        ax.set_axisbelow(True); ax.grid(axis='y', alpha=.22)
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(loc='lower left', bbox_to_anchor=(0, 1.01), frameon=False, ncol=2)
        fig.suptitle(title, x=.10, ha='left', y=.97, fontsize=17, weight='bold')
        fig.text(.10, .895, 'Five fresh-volume trials per engine and condition · 1,000 acknowledged inserts per trial', fontsize=10)
        footer = ('Each point is one trial; horizontal strokes mark medians. Pilot excluded.\n'
                  'Host/kernel remained running; these observations do not establish power-loss durability.')
        if metric != 'intact_percent':
            footer = ('Each point is one trial; strokes mark medians. Includes Docker, polling, row checks and CHECK TABLE.\n'
                      'Not engine-only recovery latency. MEMORY verification reads an empty table. Pilot excluded.')
        fig.text(.10, .055, footer, fontsize=9, linespacing=1.6)
        for suffix in ['png', 'svg']:
            fig.savefig(directory / f'{name}.{suffix}', dpi=180,
                        metadata={'Date': None} if suffix == 'svg' else {})
        plt.close(fig)


def main():
    pilot, pilot_rows = load_run(PILOT, True)
    full, rows = load_run(FULL, False)
    groups = summarize(rows)
    for result, records in [(pilot, pilot_rows), (full, rows)]:
        for row in records:
            require(row['crashed_table_warning'] == (row['engine'] == 'MyISAM' and row['stop'] == 'sigkill'),
                    'Log warnings changed; review findings text')
            require(row['aria_recovery_done'] == (row['engine'] == 'Aria' and row['stop'] == 'sigkill'),
                    'Aria recovery signals changed; review findings text')
        for trial in result['trials']:
            receipt = trial['acknowledgments']
            settings = {'innodb_flush_log_at_trx_commit': '1', 'rocksdb_flush_log_at_trx_commit': '1',
                        'innodb_doublewrite': 'ON', 'log_bin': 'OFF',
                        'aria_recover_options': 'BACKUP,QUICK', 'myisam_recover_options': 'BACKUP,QUICK'}
            require(all(receipt['global_variables'].get(k) == v for k, v in settings.items())
                    and receipt['session_variables']['autocommit'] == 'ON', 'Settings changed')
    docs = ROOT / 'docs'; data = docs / 'data'; figures = docs / 'figures'
    data.mkdir(parents=True, exist_ok=True); figures.mkdir(parents=True, exist_ok=True)
    with (data / 'recovery-observations.csv').open('w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    provenance = dict(full_run=FULL, excluded_pilot=PILOT, statistical_unit='one fresh-volume trial',
        timing='Docker restart request through observer completion, including full read and CHECK TABLE',
        power_condition=full['power_condition'], host_platform=full['host_platform'],
        compose_version=full['compose_version'], groups=groups, pilot_groups=summarize(pilot_rows),
        db_image_id=full['trials'][0]['db_image_id'], runner_image_id=full['trials'][0]['runner_image_id'],
        run_source_sha256=full['source_sha256'],
        canonical_results_sha256={r['run_id']: hashlib.sha256(json.dumps(r, sort_keys=True,
            separators=(',', ':'), ensure_ascii=True).encode()).hexdigest() for r in [pilot, full]})
    (data / 'recovery-statistics.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8')
    charts(rows, figures)
    table = ['| Engine | Stop | Trials | Intact rows per trial | Median seconds | Min–max seconds | Crash-table warnings |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for g in groups:
        table.append(f"| {g['engine']} | {g['stop']} | {g['trials']} | {g['intact_rows_per_trial'][0]} | "
            f"{g['restart_seconds_median']:.3f} | {g['restart_seconds_min']:.3f}–{g['restart_seconds_max']:.3f} | "
            f"{g['crashed_table_warning_trials']} |")
    report = f'''# Recovery findings: acknowledged rows after process restart

**Verified scope:** full run `{FULL}`, October 6, 2026; 50 fresh-volume trials,
five per engine and stop condition, 1,000 acknowledged single-row autocommit inserts per trial.
The separate 10-trial pilot `{PILOT}` is validated but excluded from the full-run charts and statistics.

## Findings

- InnoDB, Aria, MyISAM and MyRocks returned all 1,000 rows unchanged in every clean and forced restart trial.
- MEMORY returned an empty table after all ten restarts, including the five clean controls.
  This observed volatility matters when choosing an engine for data that must survive restarts.
- All five MyISAM forced-restart logs flagged the benchmark table as crashed and needing repair.
  A subsequent full read matched every row, and CHECK TABLE returned OK. The harness issued no
  manual REPAIR TABLE. These logs must accompany the survival result; intact rows alone do not
  establish a clean recovery path or transactional guarantees. The precise repair work is not quantified.
- All five Aria forced-restart logs recorded Aria recovery completion. The pilot showed the same
  row-survival pattern and corresponding MyISAM/Aria log signals (one trial per condition).
- No table was unreadable or unavailable, and no trial project required retention. All intended
  clean stops exited 0; all SIGKILL stops exited 137 without an OOM flag.

![Acknowledged-row survival](figures/recovery-row-survival.png)

## Timing and complete full-run table

![Restart through verification](figures/recovery-restart-verification.png)

Timing spans Docker restart request through observer completion, including observer-container launch,
connection polling, full row comparison and CHECK TABLE. **It is not engine-only recovery latency.**
MEMORY verification reads zero rows, while the other engines read 1,000; timing is not equal-work
across engines. The chart shows every trial, with deterministic horizontal offsets for legibility.
Horizontal strokes are medians; the table gives observed ranges, not confidence intervals.

{chr(10).join(table)}

The statistical unit is one fresh-volume trial, not one inserted row. Five trials per condition
on one host are descriptive evidence, not an engine-speed ranking or a reliability probability.
Condition order is not perfectly balanced within each engine; host variation remains a confounder.

## Recorded conditions and limits

Power condition: `{full['power_condition']}`. Server: MariaDB 11.8.9, x86_64;
Docker Desktop Linux containers on WSL2. Each run used one DB image ID and one runner image ID.
Image IDs, source hashes and canonical result hashes are in [derived statistics](data/recovery-statistics.json).
The canonical result hashes use sorted compact JSON to ignore Git/OS line-ending changes.
Restart log hashes verify the original bytes; `evidence/recovery/.gitattributes` disables log text conversion.

Recorded global settings include `innodb_flush_log_at_trx_commit=1`,
`rocksdb_flush_log_at_trx_commit=1`, `innodb_doublewrite=ON`, `log_bin=OFF`,
and `aria_recover_options=myisam_recover_options=BACKUP,QUICK`. Session autocommit was ON.
These are recorded conditions, not proof of equal durability across engines. Full per-trial
settings and actual table DDL remain in the acknowledgment receipts.

The server was stopped between statements after every insert was acknowledged. Its writer connection
remained open; receipt transfer and host orchestration introduced a delay before the stop.
SIGKILL left the host/kernel and filesystem cache running. This does not test power loss,
storage-device failure, interrupted statements, uncertain commit outcomes or open transactions.
The small synthetic dataset and this crash timing cannot establish general durability guarantees.
In particular, MyISAM's intact rows in this experiment do not establish transactional atomicity.

## Evidence and reproduction

- [Full raw results](../evidence/recovery/{FULL}/results.json) and [original summary](../evidence/recovery/{FULL}/summary.md).
- [Pilot raw results](../evidence/recovery/{PILOT}/results.json) remain separate.
- [All full-run observations](data/recovery-observations.csv), [statistics and provenance](data/recovery-statistics.json).
- [Recovery protocol](recovery-method.md) documents isolation, acknowledgment handling and limitations.
- Example [MyISAM crash log](../evidence/recovery/{FULL}/10-myisam-sigkill/restart.log)
  and [Aria crash log](../evidence/recovery/{FULL}/07-aria-sigkill/restart.log).

The figures and report are committed; viewing them needs no database or plotting installation.
To regenerate from archived evidence on the host, install Matplotlib 3.10.8
in your chosen reporting environment, then run from the repository root:

```powershell
python -m pip install matplotlib==3.10.8
python scripts/report_recovery_findings.py
```

The generator checks both runs, complete schedules, receipt copies, expected row digests,
stop states and every restart-log checksum before reporting. It fails on changed or unknown
outcomes rather than counting them as zero survival. It does not start Docker or rerun experiments.
PNG and SVG versions are emitted; Matplotlib/font/platform differences may affect rendering.
'''
    (docs / 'recovery-findings.md').write_text(report, encoding='utf-8')
    print('Validated 60 trials and 60 log checksums; reported 50 full-run trials. Wrote recovery findings and two charts.')


if __name__ == '__main__':
    main()
