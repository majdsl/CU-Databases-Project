"""Validate archived MEMORY index runs and reproduce derived findings; no Docker needed."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import memory_indexes as benchmark

PILOT = '20261016T163614Z-memory-indexes-6d072a50'
FULL = '20261016T170049Z-memory-indexes-d7d3b1c7'
LABELS = {'equality': 'Equality', 'range_10': 'Range: 10 matches', 'range_1000': 'Range: 1,000 matches'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def validate(result, run_id, mode):
    require(result['run_id'] == run_id and result['experiment'] == 'memory_indexes_v1', 'Wrong run identity')
    require(result['config']['mode'] == mode and 'active_trial' not in result, 'Wrong mode or unfinished trial')
    stats = benchmark.summarize(result)
    require(stats == result['statistics'], 'Saved statistics differ from recalculation')
    session = result['session_variables']
    require(session['query_cache_type'] == 'OFF' and session['max_heap_table_size'] == '134217728'
            and session['autocommit'] == 'ON' and 'NO_ENGINE_SUBSTITUTION' in session['sql_mode']
            and 'STRICT_ALL_TABLES' in session['sql_mode'], 'Recorded controls differ')
    source = (ROOT / 'benchmarks/memory_indexes.py').read_bytes().replace(b'\r\n', b'\n')
    require(result['source_sha256']['benchmarks/memory_indexes.py'] in
            [hashlib.sha256(source).hexdigest(), hashlib.sha256(source.replace(b'\n', b'\r\n')).hexdigest()],
            'Measured harness differs from report validator; review version before regenerating')
    schemas = set()
    for t in result['trials']:
        require('ENGINE=MEMORY' in t['actual_ddl'], 'Actual engine differs')
        schemas.add(t['actual_ddl'].replace('USING HASH', 'USING BTREE'))
        for label, d in t['diagnostics'].items():
            require(label in LABELS and d['parameters'] == t['query_streams'][label][0], 'Diagnostic parameters differ')
            require(len(d['explain']) == 1, 'Unexpected plan shape')
            plan = d['explain'][0]
            scan = label != 'equality' and t['index'] == 'HASH'
            expected_type = 'ALL' if scan else 'ref' if label == 'equality' else 'range'
            require(plan['type'] == expected_type and plan['key'] == (None if scan else 'probe_k'),
                    'Access path changed; narrative needs review')
            counters = d['handler_read_delta']
            expected = {k: 0 for k in counters}
            if scan:
                expected['Handler_read_rnd_next'] = t['rows'] + 1
            else:
                expected['Handler_read_key'] = 1
                expected['Handler_read_next'] = 1 if label == 'equality' else int(label.split('_')[1])
            require(counters == expected, 'Counter pattern changed; narrative needs review')
        require(set(t['diagnostics']) == set(LABELS), 'Missing diagnostic')
    require(len(schemas) == 1, 'DDL differs beyond index type')
    return stats


def load(run_id, mode):
    folder = ROOT / 'evidence/memory-indexes' / run_id
    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    stats = validate(result, run_id, mode)
    require((folder/'summary.md').read_text(encoding='utf-8') == benchmark.markdown(result), 'Original summary differs')
    return result, stats


def observations(result):
    return [dict(run_id=result['run_id'], rows=t['rows'], index=t['index'], round=t['round'],
                 position=t['position'], workload=label, mean_ms=statistics.mean(t['timings_ms'][label]),
                 samples=len(t['timings_ms'][label]), verified_rows=t['verified_rows'],
                 dataset_sha256=t['verified_dataset_sha256'],
                 plan_type=t['diagnostics'][label]['explain'][0]['type'],
                 plan_key=t['diagnostics'][label]['explain'][0]['key'],
                 handler_requests=sum(t['diagnostics'][label]['handler_read_delta'].values()))
            for t in result['trials'] for label in LABELS]


def charts(records, stats, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'svg.hashsalt':'cu-memory-findings-v1'})
    colors = {'HASH':'#b65c19', 'BTREE':'#197b88'}
    groups = [(10000,'HASH'),(10000,'BTREE'),(100000,'HASH'),(100000,'BTREE')]
    fig, axes = plt.subplots(3,1,figsize=(10,11))
    fig.subplots_adjust(left=.22,right=.96,top=.85,bottom=.12,hspace=.59)
    for ax,(label,title) in zip(axes,LABELS.items()):
        for y,(size,index) in enumerate(groups):
            values=[r['mean_ms'] for r in records if (r['rows'],r['index'],r['workload'])==(size,index,label)]
            ax.scatter(values,[y+(i-2.5)*.065 for i in range(6)],s=29,color=colors[index],zorder=3)
            s=stats[str(size)][index][label]
            ax.errorbar(s['mean'],y,xerr=s['sample_sd'],fmt='D',color='black',ms=4,capsize=4,zorder=4)
        ax.set_yticks(range(4),[f'{n:,} · {i}' for n,i in groups]);ax.set_ylim(3.5,-.5)
        ax.set_xlim(left=0);ax.set_title(title,loc='left',weight='bold');ax.set_xlabel('Trial mean latency (ms)')
        ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);ax.spines[['top','right','left']].set_visible(False)
    fig.suptitle('MEMORY indexes: similar equality, different range costs',x=.04,ha='left',y=.98,fontsize=17,weight='bold')
    fig.text(.04,.938,'Six full-run trials per group · 100 queries per workload/trial · lower is faster')
    fig.legend(handles=[Line2D([],[],marker='o',color='#666666',linestyle='None',label='Trial mean'),
                        Line2D([],[],marker='D',color='black',label='Mean ± sample SD')],
               loc='upper left',bbox_to_anchor=(.03,.918),ncol=2,frameon=False)
    fig.text(.04,.035,'Panels use different horizontal scales, each starting at zero. SD is not a confidence interval.\n'
             'Warm single-client reads; driver/network included. Pilot excluded. One laptop, one full run.',fontsize=9,linespacing=1.6)
    save(fig,directory,'memory-index-latency',plt)

    fig,axes=plt.subplots(1,2,figsize=(11,5.8))
    fig.subplots_adjust(left=.09,right=.97,top=.77,bottom=.28,wspace=.3)
    for ax,size in zip(axes,(10000,100000)):
        for index in colors:
            values=[]
            for label in LABELS:
                unique={r['handler_requests'] for r in records if (r['rows'],r['index'],r['workload'])==(size,index,label)}
                require(len(unique)==1,'Counter variation changed; plot must show spread')
                values.append(unique.pop())
            ax.plot(range(3),values,marker='o',color=colors[index],label=index,lw=2)
            for x,y in enumerate(values):
                # Equality markers overlap: use opposite offsets for legibility.
                dy=9 if index=='HASH' else -17
                ax.annotate(f'{y:,}',(x,y),xytext=(0,dy),textcoords='offset points',ha='center',fontsize=9,color=colors[index])
        ax.set_yscale('log');ax.set_ylim(.5,400000);ax.set_xticks(range(3),['Equality','Range 10','Range 1,000'])
        ax.set_title(f'{size:,} rows',loc='left',weight='bold');ax.grid(axis='y',alpha=.2)
        ax.spines[['top','right']].set_visible(False);ax.set_ylabel('Handler read requests (log scale)')
    fig.suptitle('Range queries take different access paths',x=.04,ha='left',y=.98,fontsize=17,weight='bold')
    fig.text(.04,.91,'Separate diagnostic replay: first query of each workload in each trial')
    axes[1].legend(frameon=False,loc='upper left')
    fig.text(.04,.07,'Each value repeated in all six trials. Equality uses the secondary index in both variants.\n'
             'HASH range: N + 1 sequential requests. BTREE range: 1 key request + 10 or 1,000 next requests.\n'
             'Logical handler requests are not physical reads, CPU time or rows returned. Pilot excluded.',fontsize=9,linespacing=1.7)
    save(fig,directory,'memory-index-access-paths',plt)


def save(fig,directory,name,plt):
    for ext in ('png','svg'):
        fig.savefig(directory/(name+'.'+ext),dpi=180,metadata={'Date':None} if ext=='svg' else {})
    plt.close(fig)


def report(result,stats):
    table=['| Rows | Index | Equality (ms) | Range 10 (ms) | Range 1,000 (ms) |','| ---: | --- | ---: | ---: | ---: |']
    ratios=[]
    for size in ('10000','100000'):
        for index in ('HASH','BTREE'):
            cells=[f"{stats[size][index][label]['mean']:.4f} ± {stats[size][index][label]['sample_sd']:.4f}" for label in LABELS]
            table.append('| '+' | '.join([f'{int(size):,}',index]+cells)+' |')
        ratios.append('| '+f'{int(size):,}'+' | '+' | '.join(f"{stats[size]['HASH'][label]['mean']/stats[size]['BTREE'][label]['mean']:.2f}×" for label in LABELS)+' |')
    return f'''# MEMORY findings: why the index type matters

The full run `{FULL}` contains **24 verified table trials**: six rounds at each of
10,000 and 100,000 rows, with both HASH and BTREE. Across trials, 1,320,000 loaded
rows and 7,200 timed query answers were checked. The four-trial pilot `{PILOT}`
was separately validated and excluded from all statistics and charts below.

## Finding and practical recommendation

For these unique-key, warm-read workloads, equality means were nearly identical.
For ranges, BTREE had lower mean times at both sizes. At 100,000 rows, HASH took
**{stats['100000']['HASH']['range_10']['mean']/stats['100000']['BTREE']['range_10']['mean']:.2f} times as long** for the 10-row range and
**{stats['100000']['HASH']['range_1000']['mean']/stats['100000']['BTREE']['range_1000']['mean']:.2f} times as long** for the 1,000-row range.
These are ratios of observed group means, not confidence bounds or universal speedups.

The plans and counters support an access-path explanation: every recorded HASH range
query scanned the table, while every recorded BTREE range query used `probe_k`.
Only the secondary index type changed; primary key, integer columns, data, query
streams and settings were held constant within each round/size pair.

**Choose BTREE for a rebuildable MEMORY table that needs these kinds of range queries.**
This run provides no clear equality-latency reason to prefer HASH: observed equality
trial ranges overlap, and client overhead is included. It does not test duplicate-heavy
keys, writes, ordering, concurrency or memory exhaustion. Both variants remain volatile;
see the separate [restart evidence](recovery-findings.md). No index choice makes MEMORY durable.

![Individual trial means and sample standard deviations](figures/memory-index-latency.png)

## All full-run measurements

Mean ± sample SD across six **trial means**, each averaging 100 timed queries.
Queries and rows are not independent experimental repeats. SD is descriptive spread,
not a confidence interval. No significance test or independent-host replication is claimed.

{chr(10).join(table)}

| Rows | HASH/BTREE equality | HASH/BTREE range 10 | HASH/BTREE range 1,000 |
| ---: | ---: | ---: | ---: |
{chr(10).join(ratios)}

All 72 trial/workload observations are in the [CSV](data/memory-index-observations.csv).
The [statistics/provenance JSON](data/memory-index-statistics.json) includes distributions,
canonical evidence hashes and paired per-round HASH-minus-BTREE latency differences.
Those differences preserve pairing; ratios above are ratios of group means, not averages
of per-round ratios. No pilot sample enters either calculation.

## Mechanism evidence

![Logical handler requests in diagnostic replays](figures/memory-index-access-paths.png)

Every trial recorded the actual MEMORY engine, a BTREE primary key on `id`, and the
requested secondary index on `k`. All normalized DDL matched beyond that index type.
Equality used `ref` access on `probe_k` for both variants, with one key and one next
request. The range diagnostics were consistent in all six rounds at both sizes:

| Secondary index | EXPLAIN access | Recorded range requests |
| --- | --- | --- |
| HASH | `ALL`, no selected index | `Handler_read_rnd_next=N+1`: 10,001 or 100,001 |
| BTREE | `range`, key `probe_k` | One `Handler_read_key`, plus 10 or 1,000 `Handler_read_next` |

The diagnostic is a separate replay of the first query of each workload, after timing;
it does not capture every timed query. Counts are logical handler requests, including
end-of-scan behavior, not physical I/O, CPU time or returned-row counts. EXPLAIN row
estimates need not equal actual matches. Plans were selected naturally without hints.
This supports the measured range mechanism; it does not separately measure pure index
traversal time or establish that every timing difference has only one cause.

## Conditions and limitations

- MariaDB `{result['server_version']}`, Python 3.12.15 and PyMySQL 1.1.2 in WSL2 containers.
  Recorded power condition: `{result['power_condition']}`.
- Session MEMORY table cap 128 MiB; query cache OFF; autocommit ON; strict mode and no
  engine substitution. The runner recorded one CPU quota and 512 MiB. The recorded
  Compose config gives the DB two CPUs and 2 GiB; these are limits, not dedicated cores.
- Each size/round pair uses identical seeded data and query streams. HASH and BTREE
  each run first three times per size; size order alternates. Schedule is deterministic.
- Every table is read completely for validation before queries, followed by warmup.
  One client and reused server; timings include driver/network work. No cold-cache or
  larger-than-memory conclusion follows, and client/server CPU time is not separated.
- Query order is fixed: equality, range 10, range 1,000. Server background work, host load
  and interactions with order are not independently controlled. Six rounds are on one host.
- The 1,000-row range selects 10% of the small table but 1% of the large one. This is
  fixed-cardinality range scaling, not constant-percentage selectivity scaling.
- Keys are a seeded permutation; `v` is nonindexed and must be read for the sum. No
  duplicate-heavy hash behavior, composite prefix, write cost or index-RAM comparison is claimed.

Pilot/full recorded source hashes, runtime and selected settings match; that does not
prove identical background host load. Historical source hashes retain Windows line endings.
Canonical JSON hashes identify parsed evidence independent of Git line-ending conversion.

## Evidence and reproduction

- [Full results](../evidence/memory-indexes/{FULL}/results.json) and [original summary](../evidence/memory-indexes/{FULL}/summary.md).
- [Separate pilot](../evidence/memory-indexes/{PILOT}/results.json).
- [Protocol, schema and benchmark commands](memory-index-method.md).
- [Reusable engine recommendations](engine-recommendations.md).

The charts and this report are generated from archived evidence without Docker:

```powershell
python -m pip install -r requirements-report.txt
python scripts/report_memory_findings.py
```

The generator checks both runs' schedule, data hashes, query streams and answers, index
metadata, actual DDL, plan/counter patterns, session controls, original summaries and
recalculated statistics before writing outputs. It refuses changed evidence that would
invalidate this narrative. Historical raw results are not rewritten. See
[report reproducibility](report-reproducibility.md) for environment isolation and rendering limits.

References: [MariaDB MEMORY](https://mariadb.com/docs/server/server-usage/storage-engines/memory-storage-engine)
and [storage-engine index types](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/optimization-and-indexes/storage-engine-index-types).
'''


def main():
    pilot,pilot_stats=load(PILOT,'pilot');full,stats=load(FULL,'full')
    for key in ('source_sha256','runtime','server_version','session_variables','global_variables','power_condition'):
        require(pilot[key]==full[key],'Pilot/full conditions differ: '+key)
    rows=observations(full)
    for size in (10000,100000):
        for label in ('range_10','range_1000'):
            require(stats[str(size)]['HASH'][label]['mean']>stats[str(size)]['BTREE'][label]['mean'],'Range finding changed')
        h=stats[str(size)]['HASH']['equality'];b=stats[str(size)]['BTREE']['equality']
        require(max(h['min'],b['min'])<=min(h['max'],b['max']),'Equality overlap changed')
    pairs=[]
    for size in (10000,100000):
        for round_number in range(1,7):
            for label in LABELS:
                pair={r['index']:r['mean_ms'] for r in rows if (r['rows'],r['round'],r['workload'])==(size,round_number,label)}
                pairs.append(dict(rows=size,round=round_number,workload=label,hash_minus_btree_ms=pair['HASH']-pair['BTREE']))
    data=ROOT/'docs/data';figures=ROOT/'docs/figures';data.mkdir(parents=True,exist_ok=True);figures.mkdir(parents=True,exist_ok=True)
    with (data/'memory-index-observations.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    provenance=dict(full_run=FULL,excluded_pilot=PILOT,statistical_unit='trial mean of 100 queries; six rounds per size/index',
                    full_statistics=stats,pilot_statistics=pilot_stats,paired_differences=pairs,
                    canonical_results_sha256={FULL:canonical_hash(full),PILOT:canonical_hash(pilot)},
                    runtime=full['runtime'],server_version=full['server_version'],power_condition=full['power_condition'],
                    source_sha256=full['source_sha256'],session_variables=full['session_variables'],global_variables=full['global_variables'])
    (data/'memory-index-statistics.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    charts(rows,stats,figures)
    (ROOT/'docs/memory-index-findings.md').write_text(report(full,stats),encoding='utf-8')
    print('Validated 28 trials; reported 24 full trials, 72 trial/workload observations and four figure files.')


if __name__=='__main__':main()
