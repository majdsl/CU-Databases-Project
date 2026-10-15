"""Validate archived OpenFlights runs and regenerate derived data, figures and findings."""
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import openflights as benchmark
from benchmarks.core import ENGINES, dataset_digest
from benchmarks.openflights_data import load_dataset

PILOT = '20261009T152651Z-openflights-b44366ef'
FULL = '20261009T160813Z-openflights-6884f225'
METRICS = ('load_seconds', 'lookup_ms', 'scan_ms', 'source_ms')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode()).hexdigest()


def validate_run(run_id, pilot, manifest, rows):
    folder = ROOT / 'evidence/openflights' / run_id
    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    require(result['run_id'] == run_id and result['experiment'] == 'openflights_routes_v1',
            'Unexpected run identity')
    config = benchmark.Config(**result['config'])
    require(config.pilot == pilot and 'active_trial' not in result, 'Incomplete or mislabeled run')
    require(result['dataset'] == manifest and result['rows'] == len(rows) == 67663,
            'Dataset manifest or count differs')
    require(result['dataset_sha256'] == dataset_digest(rows), 'Dataset checksum differs')
    scan, sources = benchmark.oracles(rows)
    require(result['scan_oracle'] == list(scan), 'Full-scan oracle differs')
    stats = benchmark.summarize(result)  # Checks completion, schedule, counts and finite timings.
    require(result['statistics'] == stats, 'Recorded statistics differ from recalculation')
    require((folder / 'summary.md').read_text(encoding='utf-8') == benchmark.markdown(result),
            'Original summary differs from recalculation')
    schemas = set()
    for trial in result['trials']:
        keys, source_ids = benchmark.query_streams(config, trial['round']-1, rows, sources)
        require(trial['lookup_ids'] == keys and trial['source_ids'] == source_ids,
                'Query streams differ from recorded seed')
        require(trial['source_result_counts'] == [sources[k][0] for k in source_ids],
                'Source query result cardinalities differ')
        require(re.search(r'ENGINE=' + trial['engine'] + r'\b', trial['actual_ddl'], re.I),
                'Actual table engine differs')
        schemas.add(re.sub(r'ENGINE=\w+', 'ENGINE=ENGINE', trial['actual_ddl']).replace(' PAGE_CHECKSUM=1', ''))
        plans = trial['explain']
        require(plans['point'][0][5] == 'PRIMARY'
                and plans['source'][0][5] == 'source_destination'
                and plans['scan'][0][3] == 'ALL', 'Plans changed; review findings text')
        messages = trial['analyze_messages']
        if trial['engine'] == 'MEMORY':
            require(any("doesn't support analyze" in str(m).lower() for m in messages),
                    'MEMORY ANALYZE diagnostic changed')
        else:
            require(bool(messages) and all(m[2:] == ['status', 'OK'] for m in messages),
                    'Unexpected ANALYZE diagnostic')
    require(len(schemas) == 1, 'Schemas differ beyond engine/Aria checksum option')
    session = result['session_variables']
    require(session['query_cache_type'] == 'OFF' and session['autocommit'] == 'ON'
            and session['max_heap_table_size'] == '134217728'
            and 'NO_ENGINE_SUBSTITUTION' in session['sql_mode']
            and 'STRICT_ALL_TABLES' in session['sql_mode'], 'Controls changed')
    return result, stats


def observations(result):
    records = []
    for trial in result['trials']:
        records.append(dict(run_id=result['run_id'], engine=trial['engine'], round=trial['round'],
            position=trial['position'], verified_rows=trial['verified_rows'],
            dataset_sha256=trial['verified_dataset_sha256'], load_seconds=trial['load_seconds'],
            lookup_ms=statistics.mean(trial['lookup_ms']), scan_ms=statistics.mean(trial['scan_ms']),
            source_ms=statistics.mean(trial['source_ms']), lookup_samples=len(trial['lookup_ms']),
            scan_samples=len(trial['scan_ms']), source_samples=len(trial['source_ms'])))
    return records


def charts(records, stats, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'svg.hashsalt': 'cu-openflights-findings-v1'})
    palette = ['#2166ac', '#d97721', '#168079', '#8b5ba3', '#5c677d']
    labels = ['InnoDB', 'Aria', 'MyISAM', 'MEMORY', 'MyRocks (ROCKSDB)']
    legends = [Line2D([], [], color='#666666', marker='o', linestyle='None', label='Individual trial'),
               Line2D([], [], color='black', marker='D', markersize=4, label='Mean ± sample SD')]

    def panel(ax, metric, title, xlabel):
        for index, engine in enumerate(ENGINES):
            group = sorted((r for r in records if r['engine'] == engine), key=lambda r: r['round'])
            values = [r[metric] for r in group]
            ax.scatter(values, [index + (i-2)*.065 for i in range(5)], s=32,
                       color=palette[index], alpha=.9, zorder=3)
            summary = stats[engine][metric]
            ax.errorbar(summary['mean'], index, xerr=summary['sample_sd'], fmt='D',
                        ms=4, color='black', capsize=4, lw=1.4, zorder=4)
        ax.set_yticks(range(5), labels); ax.set_ylim(4.6, -.6)
        ax.set_xlim(left=0); ax.set_xlabel(xlabel); ax.set_title(title, loc='left', pad=12, fontsize=13)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='y', length=0); ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)

    def save(fig, name):
        for extension in ('png', 'svg'):
            fig.savefig(directory / (name + '.' + extension), dpi=180,
                        metadata={'Date': None} if extension == 'svg' else {})
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.8))
    fig.subplots_adjust(left=.23, right=.97, bottom=.23, top=.74)
    panel(ax, 'load_seconds', 'Complete load of 67,663 routes', 'Load completion time (seconds)')
    fig.suptitle('OpenFlights: load completion across five engines', x=.04, ha='left', y=.975, fontsize=17, weight='bold')
    fig.text(.04, .90, 'Five full-run trials per engine · all rows verified · lower time is faster', fontsize=11)
    fig.legend(handles=legends, loc='upper left', bbox_to_anchor=(.03, .87), ncol=2, frameon=False)
    fig.text(.04, .06, 'Includes driver batching and statement completion; excludes DDL, ANALYZE and verification.\n'
             'Durability is not equalized. Error bars show sample SD, not confidence intervals. Pilot excluded.', fontsize=9, linespacing=1.6)
    save(fig, 'openflights-load')

    fig, axes = plt.subplots(3, 1, figsize=(10, 12))
    fig.subplots_adjust(left=.23, right=.97, bottom=.12, top=.86, hspace=.56)
    for ax, metric, title in zip(axes, METRICS[1:],
            ['Primary-key lookup: 200 queries per trial', 'Full scan: 5 queries per trial',
             'Source-airport aggregate: 100 queries per trial']):
        panel(ax, metric, title, 'Mean latency within one trial (milliseconds)')
    fig.suptitle('OpenFlights: warm reads across five engines', x=.04, ha='left', y=.975, fontsize=17, weight='bold')
    fig.text(.04, .938, 'Every point is one round mean; each engine has five rounds. Lower time is faster.', fontsize=11)
    fig.legend(handles=legends, loc='upper left', bbox_to_anchor=(.03, .92), ncol=2, frameon=False)
    fig.text(.04, .035, 'Panels use different horizontal scales, each starting at zero. Same query streams across engines in each round.\n'
             'Warm caches; driver/network overhead included. Error bars are sample SD across round means. Pilot excluded.', fontsize=9, linespacing=1.6)
    save(fig, 'openflights-warm-reads')


def report(result, stats):
    table = ['| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |',
             '| --- | ---: | ---: | ---: | ---: |']
    for engine in ENGINES:
        cells = [f"{stats[engine][m]['mean']:.4f} ± {stats[engine][m]['sample_sd']:.4f}" for m in METRICS]
        table.append('| ' + engine + ' | ' + ' | '.join(cells) + ' |')
    return f'''# OpenFlights findings: real route data across five engines

**Verified full run:** `{FULL}` (October 9, 2026), five balanced rounds across five engines.
Each of the 25 trials loaded and checked all **67,663 routes**: 1,691,575 verified row loads.
The separate five-trial pilot `{PILOT}` is validated but excluded from these statistics and charts.

## What the measurements show

- MEMORY had the lowest observed mean load and full-scan times. This supports considering
  it for rebuildable reference-data work where the table fits in memory. The separate
  [recovery experiment](recovery-findings.md) found complete row loss after both clean and
  forced restarts; it cannot be the sole persistent copy of this route dataset.
- Among the four disk-backed engines in this run, MyISAM had the lowest mean load time,
  while Aria had the lowest mean full-scan time. The results show that the fastest loader
  was not also the fastest scanner within that group.
- MyRocks had the highest mean full-scan time here. These small, warm, single-client trials
  do not test its sustained-ingestion or large-dataset behavior, nor equal storage budgets.
- Point-lookup means were close (about 0.234–0.249 ms), with overlapping observed ranges.
  Do not turn those small differences into a general ranking. Source-query timing includes
  variable result cardinality and client overhead; it is not pure index-traversal latency.

![Load completion times](figures/openflights-load.png)

![Warm read times](figures/openflights-warm-reads.png)

## Complete full-run summary

Values are **mean ± sample standard deviation across five trials**. Read measurements first
average queries within each trial. Neither individual queries nor rows are independent repeats.

{chr(10).join(table)}

Every round appears as a point in the figures; SD bars are descriptive spread, not confidence
intervals. [Per-trial derived data](data/openflights-observations.csv) preserves all 25 observations;
[statistics](data/openflights-statistics.json) includes medians, minima, maxima and provenance.
The archived JSON preserves all individual query samples. No significance test or universal winner
is claimed from five rounds on one host.

## Correctness, plans and conditions

All 25 trials matched canonical dataset SHA-256
`ea46aabb9533882cf36baa761b285ef8f8829915ff1b3a689fc8315206532441`.
The scan oracle was `(67663, 11, 305336)`: row count, total stops and equipment character count.
The source file, transformation, missing IDs and nonunique route combinations are documented
in the [method](openflights-method.md). This is OpenFlights route reference data, not synthetic
flight events or a current operating schedule. Data attribution: [OpenFlights](https://openflights.org/data.html),
via MariaDB/openflights; [ODbL 1.0](../data/openflights/LICENSE).

The recorded EXPLAIN samples in every trial used PRIMARY for point lookups,
source_destination for source aggregates, and ALL for full scans. Plans were captured for
the first lookup/source key, not every possible key. ANALYZE returned OK for the four disk-backed
engines; MEMORY reported that ANALYZE is unsupported. Its rows and answers were still verified.
Actual logical schemas matched apart from the engine and Aria's reported PAGE_CHECKSUM option.

The five full-run rounds placed each engine once in each position. Recorded conditions:

- MariaDB 11.8.9-MariaDB-ubu2404, Python 3.12.15, PyMySQL 1.1.2, WSL2 Linux containers.
- Power condition: `{result['power_condition']}`. See the [same-day hardware record](benchmark-environment.md).
- Runner runtime reported a one-CPU cgroup quota and 512 MiB limit; the recorded Compose
  source configures DB quota 2 CPUs / 2 GiB. Quotas are not dedicated cores.
- Query cache OFF, strict/no-substitution mode, autocommit ON, session MEMORY maximum 128 MiB.
- Pilot and full run recorded identical source hashes, runtime, server version and selected
  global/session settings. This does not establish identical host background load or cache state.

The dataset was fully read for verification before timed queries, followed by explicit warmups.
Load excludes DDL, ANALYZE and verification. Query times include execute/fetch and driver/network
overhead; answer comparison is outside the timer. The server/volume is reused, and engine caches,
durability settings and background work are not equalized. No cold-cache, physical-disk,
compression, sustained-compaction or concurrent-workload conclusion follows from this run.

## Interpreting the trade-offs

Engine design informs what to investigate; it does not by itself prove why a timing differs.
[MariaDB's engine guide](https://mariadb.com/docs/server/server-usage/storage-engines/choosing-the-right-storage-engine)
describes MEMORY's in-memory, volatile role and InnoDB's transactional role.
[InnoDB](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-storage-engine-introduction)
provides transactions and row-level locking;
[MyISAM](https://mariadb.com/docs/server/server-usage/storage-engines/myisam-storage-engine/myisam-overview)
uses table-level locking. This single-client read test does not measure their contention costs.
[MyRocks uses LSM storage](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/about-myrocks-for-mariadb);
its full-scan result here does not establish the causal cost of LSM organization or compaction.

Practical interpretation: benchmark MEMORY for disposable cached route data; assess persistent
engines against both load/read needs and required guarantees. MyISAM's loading result does not
erase the crashed-table warnings in our separate recovery evidence. If transactions are required,
do not choose from this speed table alone. Final recommendations must combine this report with
the [storage](storage-findings.md), [CPU/concurrency](cpu-findings.md) and
[recovery](recovery-findings.md) evidence and each experiment's limitations.

## Evidence and reproduction

- [Full raw results](../evidence/openflights/{FULL}/results.json) and [original summary](../evidence/openflights/{FULL}/summary.md).
- [Pilot raw results](../evidence/openflights/{PILOT}/results.json), kept separate.
- [Dataset pin](../data/openflights/manifest.json), [method](openflights-method.md),
  [trial CSV](data/openflights-observations.csv), [statistics/provenance](data/openflights-statistics.json).

Charts and this report are committed; viewing them requires no new experiment. Optional regeneration
on the host uses Matplotlib 3.10.8 and the checksum-verified source dataset:

```powershell
python scripts/fetch_openflights.py
python -m pip install matplotlib==3.10.8
python scripts/report_openflights_findings.py
```

The generator validates both archived runs, checksums, query streams, result cardinalities, schemas,
plans, sample counts, statistics and original summaries. It refuses incomplete or internally inconsistent evidence.
Canonical JSON hashes in the provenance ignore Git/OS line-ending conversion. Source hashes remain
as captured during the experiments; no historical provenance is rewritten. No Docker command is run.
'''


def main():
    manifest, rows = load_dataset(ROOT / 'data/openflights')
    pilot, pilot_stats = validate_run(PILOT, True, manifest, rows)
    full, stats = validate_run(FULL, False, manifest, rows)
    for field in ('source_sha256', 'runtime', 'server_version', 'global_variables', 'session_variables', 'power_condition'):
        require(pilot[field] == full[field], 'Pilot/full conditions changed; review report: ' + field)
    # Protect the measured comparisons embedded in the narrative from stale interpretation.
    require(min(ENGINES, key=lambda e: stats[e]['load_seconds']['mean']) == 'MEMORY'
            and min(ENGINES, key=lambda e: stats[e]['scan_ms']['mean']) == 'MEMORY', 'Ranking changed')
    disk = [e for e in ENGINES if e != 'MEMORY']
    require(min(disk, key=lambda e: stats[e]['load_seconds']['mean']) == 'MyISAM'
            and min(disk, key=lambda e: stats[e]['scan_ms']['mean']) == 'Aria'
            and max(ENGINES, key=lambda e: stats[e]['scan_ms']['mean']) == 'ROCKSDB', 'Ranking changed')
    records = observations(full)
    docs = ROOT / 'docs'; data = docs / 'data'; figures = docs / 'figures'
    data.mkdir(parents=True, exist_ok=True); figures.mkdir(parents=True, exist_ok=True)
    with (data / 'openflights-observations.csv').open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    provenance = dict(full_run=FULL, excluded_pilot=PILOT, statistical_unit='one trial; round mean for reads',
        full_statistics=stats, pilot_statistics=pilot_stats, dataset=manifest,
        dataset_sha256=full['dataset_sha256'], canonical_results_sha256={FULL: canonical_hash(full), PILOT: canonical_hash(pilot)},
        runtime=full['runtime'], server_version=full['server_version'], power_condition=full['power_condition'],
        source_sha256=full['source_sha256'], global_variables=full['global_variables'], session_variables=full['session_variables'])
    (data / 'openflights-statistics.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8')
    charts(records, stats, figures)
    (docs / 'openflights-findings.md').write_text(report(full, stats), encoding='utf-8')
    print('Verified 30 trials; reported 25 full-run trials. Wrote OpenFlights charts, derived data and findings.')


if __name__ == '__main__':
    main()
