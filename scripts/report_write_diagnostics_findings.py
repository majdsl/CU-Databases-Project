"""Validate archived concurrent-write evidence and reproduce its report and figures."""
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks import write_diagnostics as benchmark
from benchmarks.core import ENGINES, describe
from benchmarks.telemetry import difference, quota_cpus

PILOT='20261017T170909Z-write-diagnostics-31a106d2'
FULL='20261017T172951Z-write-diagnostics-773525b2'
PATTERNS=('disjoint','hotspot')
CLIENTS=(1,2,4)


def require(condition,message):
    if not condition:raise ValueError(message)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def check_source(recorded):
    for path,digest in recorded.items():
        p=ROOT/path
        require(p.resolve().is_relative_to(ROOT.resolve()),'Unexpected source path')
        raw=p.read_bytes().replace(b'\r\n',b'\n')
        require(digest in (hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\n',b'\r\n')).hexdigest()),
                'Measured source differs: '+path)


def validate(result,run_id,mode):
    require(result['run_id']==run_id and result['mode']==mode and
            result['experiment']=='isolated_write_diagnostics_v1','Wrong run identity')
    require(result['schedule']==benchmark.schedule(mode),'Wrong schedule')
    summary=benchmark.summary(result)  # Regenerates every initial/final row hash and checks worker counts and deltas.
    stop=result['clean_stop']
    require(stop['Status']=='exited' and stop['ExitCode']==0 and not stop['OOMKilled'] and result['cleanup']=='completed','Unclean lifecycle')
    require(result['power_condition']=='plugged in; battery saver off','Power conditions changed')
    check_source(result['source_sha256'])
    require(len(result['source_sha256'])==3,'Missing host source provenance')
    first=result['trials'][0]
    globals_=first['prepare']['global_variables']
    require(all(int(globals_[k])==134217728 for k in ('innodb_buffer_pool_size','aria_pagecache_buffer_size','key_buffer_size','rocksdb_block_cache_size')),'Recorded cache configuration changed')
    require(globals_['innodb_flush_log_at_trx_commit']=='1' and globals_['rocksdb_flush_log_at_trx_commit']=='1' and globals_['log_bin']=='OFF','Recorded durability configuration changed')
    require(first['prepare']['server_version'].startswith('11.8.9-MariaDB'),'Recorded server version changed')
    check_source(first['prepare']['source_sha256'])
    for trial in result['trials']:
        require(trial['db_cpu_before']==trial['db_cpu']['before'] and trial['db_cpu_after']==trial['db_cpu']['after'],'CPU snapshots disagree')
        for stage in ('prepare','writes','verify'):
            item=trial[stage]
            require(item['runtime']==first['prepare']['runtime'] and item['server_version']==first['prepare']['server_version'],'Runtime changed')
            require(quota_cpus(item['runtime']['cgroup_cpu_max'])==2 and int(item['runtime']['cgroup_memory_max'])==536870912,'Runner budget changed')
        prepare=trial['prepare']
        for field in ('source_sha256','global_variables','session_variables','config'):
            require(prepare[field]==first['prepare'][field],'Within-run controls differ: '+field)
        require('ENGINE='+trial['engine'].upper() in prepare['actual_ddl'].upper(),'Actual engine mismatch')
        session=prepare['session_variables']
        require(session['query_cache_type']=='OFF' and session['autocommit']=='ON' and
                'STRICT_ALL_TABLES' in session['sql_mode'] and 'NO_ENGINE_SUBSTITUTION' in session['sql_mode'],'Session controls changed')
        db=trial['db_cpu'];runner=trial['writes']['runner_cpu']
        require(runner==difference(runner['before'],runner['after']) and runner['cgroup_status']=='available','Runner CPU unavailable or inconsistent')
        require(runner['window_seconds']>=trial['writes']['elapsed_seconds'],'Runner window excludes updates')
        for cpu in (db,runner):
            require(cpu['counter_delta'].get('nr_throttled')==0 and cpu['counter_delta'].get('throttled_usec')==0,'Zero local throttling finding changed')
        for endpoint in ('before','after'):
            require(db[endpoint]['container_id']==first['db_cpu']['before']['container_id'] and
                    db[endpoint]['started_at']==first['db_cpu']['before']['started_at'],'Database restarted or replaced')
        locks=trial['writes']['lock_delta']
        require(all(value is not None for value in locks.values()),'Lock counters unavailable')
        if trial['engine']=='InnoDB':
            require(locks['Innodb_row_lock_waits']==0 and locks['Innodb_row_lock_time']==0,'InnoDB no-observed-wait finding changed')
    return summary


def load(run_id,mode):
    directory=ROOT/'evidence/write-diagnostics'/run_id
    result=json.loads((directory/'results.json').read_text(encoding='utf-8-sig'))
    summary=validate(result,run_id,mode)
    require(summary==(directory/'summary.md').read_text(encoding='utf-8-sig'),'Original summary differs')
    hashes={}
    expected={'results.json','summary.md'}
    for number,trial in enumerate(result['trials'],1):
        for stage in ('prepare','writes','verify'):
            name=f'trial-{number:03d}-{stage}.json';expected.add(name)
            raw=json.loads((directory/name).read_text(encoding='utf-8-sig'))
            require(raw==trial[stage],'Raw stage differs: '+name)
            hashes[name]=canonical_hash(raw)
    require({p.name for p in directory.iterdir()}==expected,'Missing or unexpected evidence file')
    return result,hashes


def observations(result):
    records=[]
    for t in result['trials']:
        w=t['writes'];db=t['db_cpu'];runner=w['runner_cpu'];locks=w['lock_delta']
        r=dict(run_id=result['run_id'],round=t['round'],engine=t['engine'],pattern=t['pattern'],clients=t['clients'],
               updates=w['completed'],updates_per_second=w['updates_per_second'],update_seconds=w['elapsed_seconds'],
               db_cpu_seconds=db['cpu_seconds'],db_window_seconds=db['wall_seconds'],
               db_window_min_seconds=db['wall_seconds_bounds'][0],db_window_max_seconds=db['wall_seconds_bounds'][1],
               db_average_cores=db['average_cores'],runner_window_seconds=runner['window_seconds'],
               runner_average_cores=runner['cgroup_average_cores'],runner_process_cpu_seconds=runner['process_cpu_seconds'],
               db_to_update_window_ratio=db['wall_seconds']/w['elapsed_seconds'],
               db_throttled_periods=db['counter_delta']['nr_throttled'],runner_throttled_periods=runner['counter_delta']['nr_throttled'],
               table_locks_immediate=locks['Table_locks_immediate'],table_locks_waited=locks['Table_locks_waited'],
               table_waits_per_1000_updates=locks['Table_locks_waited']/w['completed']*1000,
               innodb_row_waits=locks['Innodb_row_lock_waits'] if t['engine']=='InnoDB' else None,
               innodb_row_lock_time_ms=locks['Innodb_row_lock_time'] if t['engine']=='InnoDB' else None,
               innodb_pending_waits_before=w['lock_before']['values']['Innodb_row_lock_current_waits'] if t['engine']=='InnoDB' else None,
               innodb_pending_waits_after=w['lock_after']['values']['Innodb_row_lock_current_waits'] if t['engine']=='InnoDB' else None,
               initial_sha256=t['prepare']['initial_dataset_sha256'],final_sha256=t['verify']['verified_final_sha256'])
        records.append(r)
    return records


def statistics(records):
    metrics=('updates_per_second','db_average_cores','runner_average_cores','db_cpu_seconds','db_window_seconds',
             'update_seconds','db_to_update_window_ratio','table_waits_per_1000_updates','table_locks_waited',
             'innodb_row_waits','innodb_row_lock_time_ms')
    groups=[]
    for engine in ENGINES:
        for pattern in PATTERNS:
            for clients in CLIENTS:
                selected=[r for r in records if (r['engine'],r['pattern'],r['clients'])==(engine,pattern,clients)]
                require(len(selected)==5,'Expected five full trials per condition')
                group=dict(engine=engine,pattern=pattern,clients=clients)
                for field in metrics:
                    values=[r[field] for r in selected]
                    group[field]=None if any(v is None for v in values) else describe(values)
                groups.append(group)
    return groups


def charts(groups,directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.hashsalt':'write-diagnostics-v1'})
    colors=dict(zip(ENGINES,('#2864a5','#bb5722','#00877c','#9852a1','#606775')))
    def plot(ax,pattern,field,engines=ENGINES):
        for engine in engines:
            selected=[g for g in groups if g['engine']==engine and g['pattern']==pattern]
            ax.errorbar(CLIENTS,[g[field]['mean'] for g in selected],
                        yerr=[g[field]['sample_sd'] for g in selected],marker='o',capsize=4,
                        label=engine,color=colors[engine],linewidth=1.8)
        ax.set_xticks(CLIENTS);ax.set_xlabel('Concurrent clients');ax.grid(axis='y',alpha=.2)
        ax.spines[['top','right']].set_visible(False);ax.set_title('Disjoint rows' if pattern=='disjoint' else 'Shared 16-row hotspot',loc='left',weight='bold')
    def save(fig,name):
        for ext in ('png','svg'):
            fig.savefig(directory/(name+'.'+ext),dpi=180,metadata={'Date':None} if ext=='svg' else {})
        plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,6.5),sharey=True)
    fig.subplots_adjust(left=.09,right=.97,top=.75,bottom=.2,wspace=.18)
    for ax,pattern in zip(axes,PATTERNS):
        plot(ax,pattern,'updates_per_second');ax.set_yscale('log');ax.set_ylim(300,20000)
    axes[0].set_ylabel('Updates per second (log scale; higher is faster)')
    fig.suptitle('Two to four clients: throughput does not always rise',x=.04,y=.97,ha='left',fontsize=17,weight='bold')
    fig.text(.04,.91,'10,000 autocommit updates per trial · five balanced engine-order rounds · mean ± sample SD')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper left',bbox_to_anchor=(.03,.88),ncol=5,frameon=False)
    fig.text(.04,.055,'Warm reused server; one laptop; pilot excluded. Durability and cache budgets are unequal.\nTimings include Python, scheduling, driver and network work. SD is not a confidence interval.',fontsize=9,linespacing=1.7)
    save(fig,'write-diagnostics-throughput')

    fig,axes=plt.subplots(2,2,figsize=(12,9))
    fig.subplots_adjust(left=.09,right=.97,top=.81,bottom=.16,hspace=.45,wspace=.2)
    for row,field in enumerate(('runner_average_cores','db_average_cores')):
        for ax,pattern in zip(axes[row],PATTERNS):
            plot(ax,pattern,field);ax.set_ylim(0,2 if row==0 else .6)
            ax.set_ylabel('Runner average cores' if row==0 else 'DB-container average cores')
    fig.suptitle('CPU observations use different windows',x=.04,y=.98,ha='left',fontsize=17,weight='bold')
    fig.text(.04,.93,'Mean ± sample SD across five trials per condition · both quotas: two CPUs')
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper left',bbox_to_anchor=(.03,.9),ncol=5,frameon=False)
    fig.text(.04,.035,'Top: worker setup, writes and teardown. Bottom: wider runner-launch window, including background CPU.\nRows use different vertical scales. Do not subtract these series to isolate query overhead or add their cores.\nNo local cgroup throttling was recorded; that does not rule out host contention or short CPU peaks.',fontsize=9,linespacing=1.7)
    save(fig,'write-diagnostics-cpu')

    fig,axes=plt.subplots(1,2,figsize=(12,6.5),sharey=True)
    fig.subplots_adjust(left=.09,right=.97,top=.75,bottom=.24,wspace=.18)
    for ax,pattern in zip(axes,PATTERNS):
        plot(ax,pattern,'table_waits_per_1000_updates',('Aria','MyISAM','MEMORY'))
        ax.set_yscale('symlog',linthresh=1);ax.set_ylim(-.15,1500)
        ax.set_yticks([0,1,10,100,1000],['0','1','10','100','1,000'])
    axes[0].set_ylabel('Table-lock waits per 1,000 updates')
    fig.suptitle('Table-lock waits appear with concurrent writers',x=.04,y=.97,ha='left',fontsize=17,weight='bold')
    fig.text(.04,.91,'Mean ± sample SD · symmetric-log scale (linear from 0 to 1) · five trials per condition')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper left',bbox_to_anchor=(.03,.88),ncol=3,frameon=False)
    fig.text(.04,.055,'InnoDB and ROCKSDB table-lock deltas were zero in all full trials (omitted curves).\nInnoDB row-lock wait/time deltas were also zero. Those counters do not measure MyRocks row locks.\nThese are wait-event counts, not percent of time blocked, latency or a full inventory of server contention.',fontsize=9,linespacing=1.7)
    save(fig,'write-diagnostics-lock-waits')


def report(full,groups,records):
    def get(engine,pattern,clients,field='updates_per_second'):
        return next(g[field]['mean'] for g in groups if (g['engine'],g['pattern'],g['clients'])==(engine,pattern,clients))
    declines={e:100*(1-get(e,'disjoint',4)/get(e,'disjoint',2)) for e in ('MyISAM','MEMORY')}
    require(all(v>0 for v in declines.values()),'Scaling direction changed; revise interpretation')
    require(all(r['table_locks_waited']==0 for r in records if r['engine'] in ('InnoDB','ROCKSDB')),'Zero table-wait statement changed')
    require(all(r['table_locks_waited']==0 for r in records if r['clients']==1),'Single-client zero-wait statement changed')
    table=['| Engine | Pattern | Clients | Updates/s ± SD | Runner cores ± SD | DB cores ± SD | Table waits/1,000 ± SD |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for g in groups:
        cells=[]
        for field,places in (('updates_per_second',1),('runner_average_cores',3),('db_average_cores',3),('table_waits_per_1000_updates',2)):
            s=g[field];cells.append(f"{s['mean']:.{places}f} ± {s['sample_sd']:.{places}f}")
        table.append('| '+' | '.join([g['engine'],g['pattern'],str(g['clients'])]+cells)+' |')
    ratio=[r['db_to_update_window_ratio'] for r in records]
    return f'''# Concurrent writes: CPU and lock-wait findings

Full run `{FULL}` contains **150 verified trials and 1,500,000 successful updates**.
Five rounds cover five engines, two patterns and 1/2/4 clients. Each trial loads
10,000 synthetic rows and executes 10,000 autocommit increments; every initial and
final row is checked. The 30-trial pilot `{PILOT}` is independently validated and
excluded from every statistic and figure below. Both runs completed on October 17,
2026 (Europe/Berlin); the evidence was archived in commit `b5eefc3`.

## Findings and decision

- Aria records almost one table-lock wait event per update with two or four clients,
  in both patterns; its mean throughput changes little from two to four clients.
  This directly observes table-lock contention, including on disjoint rows. It does
  not establish how much total runtime was spent waiting or separate logging cost.
- MyISAM and MEMORY disjoint throughput falls **{declines['MyISAM']:.1f}% and {declines['MEMORY']:.1f}%** from two to four clients.
  Table-lock waits increase, and runner CPU rises to about 1.66 average cores.
  Both locking and client execution are relevant observations; neither was isolated
  as the sole cause. The hotspot exhibits the same broad throughput pattern.
- InnoDB records zero row-lock wait counts and time deltas in all 30 of its full
  trials, including the 16-row hotspot. This workload did not establish InnoDB
  row-lock waiting; zero here is not a general concurrency guarantee.
- No local cgroup quota-throttling periods or time were recorded for either
  container in any full trial. Average CPU does not measure instantaneous peaks,
  Python scheduling costs, host contention, I/O waits or parent cgroup limits.

**Practical implication:** for frequent concurrent updates, include lock counters
and client telemetry in workload testing; disjoint records do not remove table-lock
contention. Do not use these unequal-durability timings to prefer a non-transactional
engine for authoritative records. Start persistent transactional workloads with the
requirements-based [engine recommendations](engine-recommendations.md), then measure
representative transaction length and contention. No universal engine ranking follows.

![Throughput across client counts](figures/write-diagnostics-throughput.png)

## Complete full-run results

Mean ± sample SD across **five trials per condition**. Individual updates are not
independent repeats; SD is not a confidence interval. CPU columns use distinct
windows, detailed below, and must not be added or subtracted. Table waits are events
per 1,000 completed updates, not a percentage of blocked time.

{chr(10).join(table)}

The [150-row CSV](data/write-diagnostics-observations.csv) preserves trial-level
observations. [Statistics and provenance](data/write-diagnostics-statistics.json)
include all group summaries and canonical evidence hashes. All individual statement
latencies remain in the immutable raw JSON; no significance test is claimed.

## CPU windows and limits

![Runner and database-container CPU](figures/write-diagnostics-cpu.png)

Throughput covers barrier release to the final successful update. Runner CPU covers
worker setup, updates and teardown. DB-container CPU is sampled by the host before
launching the writes runner and after it returns. Its wall window was **{min(ratio):.2f}–{max(ratio):.2f} times**
the throughput interval, with a larger relative startup cost for faster workloads.
CPU seconds divided by that broader wall time gives DB average cores. This can
lower the average relative to the active update period; it is not pure query CPU.

The database samples include background server work, healthchecks and the tiny `cat`
observer. Earlier load work can continue in the background. Host timestamps bound
sample-call uncertainty; minimum/maximum windows are retained in the CSV. No idle
baseline is subtracted. These measurements separate which container consumed CPU,
but **do not decompose client/network overhead from server execution latency**.
Low average DB CPU does not prove that server CPU cannot be a bottleneck.

## What the lock counters establish

![Table-lock waits](figures/write-diagnostics-lock-waits.png)

The global `Table_locks_waited` delta directly counts table locks that waited.
All single-client trials recorded zero. Aria's multi-client trials recorded roughly
10,000 events per 10,000 updates; MyISAM and MEMORY recorded fewer but more at four
clients than at two on average. InnoDB and ROCKSDB table-lock deltas were all zero.
These observations are consistent with table locking constraining concurrency,
without proving its share of elapsed time or excluding logging and scheduling.

`Innodb_row_lock_waits` and `Innodb_row_lock_time` (documented milliseconds) apply to
InnoDB. Their zero deltas do not describe MyRocks locking. Endpoint pending-wait
gauges can miss brief waits. SQL snapshots bracket worker execution, include their
own observation overhead, and are not atomic across counters. The dedicated server
limits unrelated work; it does not instrument every latch or metadata lock.
The [protocol](write-diagnostics-method.md) links the official counter definitions.

## Controls and reproducibility

- Same seeded data, schema and fixed total operation count within every condition;
  disjoint partitions or a shared 16-row hotspot. Worker barrier, no retry policy,
  actual-engine validation, complete row checks and independently regenerated hashes.
- Five engine orders are balanced. Six condition positions rotate across five
  rounds and therefore are not perfectly balanced. Tables reload each trial;
  one fresh isolated server/volume is reused across the full run. Cache/history
  effects remain, and these are short fixed-work bursts rather than sustained loads.
- MariaDB 11.8.9, Python 3.12.15, PyMySQL 1.1.2, WSL2. Recorded power condition:
  `{full['power_condition']}`. DB quota two CPUs/2 GiB; runner two CPUs/512 MiB.
  Measured source, selected settings and runtime match across the pilot and full
  runs. **DB and runner image IDs differ between runs**; the reason is not established
  by these records. Both identities are retained, and byte-identical images across
  runs are not claimed. One DB container was observed throughout each run.
- The InnoDB buffer pool, Aria page cache, MyISAM key buffer and MyRocks block cache
  were each configured to 128 MiB. They cover different things and do not equalize
  total memory or caching. MEMORY rows/indexes live in RAM. InnoDB and MyRocks
  flush-at-commit settings were 1; binary logging was off. These engines still do
  not have equivalent durability. See the [budget inventory](cache-and-durability.md).
- Both runs stopped cleanly without OOM; successful cleanup removed only their
  isolated volumes. This run measured neither crash recovery nor power-loss safety.
  CI tests correctness, not these performance values. Independent hosts, long
  transactions, enforced collisions and server-side tracing remain broader work.

## Evidence and regeneration

- [Full results](../evidence/write-diagnostics/{FULL}/results.json), [original summary](../evidence/write-diagnostics/{FULL}/summary.md).
- [Separate pilot](../evidence/write-diagnostics/{PILOT}/results.json).
- All **540 raw stage files** match the parent run records (90 pilot, 450 full).
- [Method and run commands](write-diagnostics-method.md); [report reproduction](report-reproducibility.md).

Generate the report, derived data and three charts (PNG/SVG), without Docker or new measurements:

```powershell
python -m pip install -r requirements-report.txt
python scripts/report_write_diagnostics_findings.py
```

The generator validates schedules, final-data oracles, worker counts, telemetry
arithmetic, controls, source identities, raw stage files, summaries and clean stops.
It rejects evidence changes that invalidate the narrative rather than silently
retaining old conclusions. Canonical hashes tolerate Git line-ending conversion;
raw evidence is not rewritten. Plotting libraries and fonts can affect rendering.
'''


def main():
    pilot,pw=load(PILOT,'pilot');full,fw=load(FULL,'full')
    for field in ('source_sha256','power_condition'):
        require(pilot[field]==full[field],'Pilot/full controls differ: '+field)
    for field in ('source_sha256','global_variables','session_variables','runtime','server_version'):
        require(pilot['trials'][0]['prepare'][field]==full['trials'][0]['prepare'][field],'Pilot/full conditions differ: '+field)
    records=observations(full);groups=statistics(records);narrative=report(full,groups,records)
    data=ROOT/'docs/data';figures=ROOT/'docs/figures';data.mkdir(exist_ok=True);figures.mkdir(exist_ok=True)
    with (data/'write-diagnostics-observations.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    provenance=dict(full_run=FULL,excluded_pilot=PILOT,statistical_unit='one trial; five per condition',groups=groups,
        canonical_results_sha256={FULL:canonical_hash(full),PILOT:canonical_hash(pilot)},
        stage_canonical_sha256={FULL:fw,PILOT:pw},source_sha256=full['source_sha256'],
        image_ids={r['run_id']:{key:r[key] for key in ('db_image_id','runner_image_id')} for r in (pilot,full)},
        runtime=full['trials'][0]['prepare']['runtime'],power_condition=full['power_condition'])
    (data/'write-diagnostics-statistics.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    charts(groups,figures)
    (ROOT/'docs/write-diagnostics-findings.md').write_text(narrative,encoding='utf-8')
    print('Validated 180 trials and 540 stage files; reported 150 full trials in 30 groups.')


if __name__=='__main__':main()
