"""Reproduce cache-pressure findings from immutable pilot/full evidence, without Docker."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SNAPSHOT=ROOT/'provenance/cache-pressure'
MEASURED_SOURCE_REVISION='db0639c0194092e8c338a68f2f9f24ed024d7a5f'
SOURCE_MANIFEST_SHA256_LF='4a6da277642b62298d2da9fe182d376f072dcd7abce9f390be9bbee59fd19c7b'
sys.path.insert(0,str(ROOT))
from benchmarks import cache_pressure as benchmark
from benchmarks.core import describe
from scripts.run_cache_pressure import expected_data

PILOT='20261016T224159Z-cache-pressure-fe05dc09'
FULL='20261016T224612Z-cache-pressure-ca6cb57e'
SIZES=(32768,262144)


def require(condition,message):
    if not condition:raise ValueError(message)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def source_manifest():
    """Historical source verification does not depend on the live working tree."""
    raw=(SOURCE_SNAPSHOT/'manifest.json').read_bytes().replace(b'\r\n',b'\n')
    require(hashlib.sha256(raw).hexdigest()==SOURCE_MANIFEST_SHA256_LF,
            'Measured source snapshot manifest changed')
    manifest=json.loads(raw)
    require(manifest['format_version']==1 and manifest['revision']==MEASURED_SOURCE_REVISION,
            'Unexpected measured source snapshot')
    require(set(manifest['files'])==set(manifest['host_paths'])|set(manifest['worker_paths'])
            and len(manifest['host_paths'])==3 and len(manifest['worker_paths'])==23,
            'Incomplete measured source snapshot')
    return manifest


def check_source(recorded,role):
    manifest=source_manifest()
    require(set(recorded)==set(manifest[role+'_paths']),
            'Missing or unexpected '+role+' source provenance')
    source_root=SOURCE_SNAPSHOT/'source'
    for name,recorded_hash in recorded.items():
        path=source_root/name
        require(path.resolve().is_relative_to(source_root.resolve()),'Unexpected source path')
        raw=path.read_bytes().replace(b'\r\n',b'\n')
        hashes={ending:hashlib.sha256(content).hexdigest() for ending,content in
                (('lf',raw),('crlf',raw.replace(b'\n',b'\r\n')))}
        entry=manifest['files'][name]
        require(all(entry['sha256_'+ending]==value for ending,value in hashes.items())
                and entry['git_blob_sha1']==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                'Measured source snapshot changed: '+name)
        require(recorded_hash in hashes.values(),'Measured source differs: '+name)


def validate(result,run_id,mode):
    require(result['run_id']==run_id and result['mode']==mode and result['experiment']=='isolated_innodb_cache_pressure_v1','Wrong run identity')
    require('active_project' not in result and 'active_trial' not in result,'Active/unfinished trial')
    stats=benchmark.summary(result)
    require(stats==result['statistics'],'Statistics differ from recalculation')
    expected={n:expected_data(n) for n in SIZES}
    for n in SIZES:require(expected[n]==result['expected_data'][str(n)],'Host oracle differs')
    check_source(result['source_sha256'],'host')
    projects=set();schemas=set()
    for t in result['trials']:
        check_source(t['source_sha256'],'worker')
        n=t['rows'];require(all(t[k]==v for k,v in expected[n].items()),'Trial data oracle differs')
        require(t['project'] not in projects,'Reused trial project');projects.add(t['project'])
        require('ENGINE=InnoDB' in t['actual_ddl'] and t['engine_reported_table_status']['Engine']=='InnoDB','Wrong engine')
        schemas.add(t['actual_ddl'])
        status=t['engine_reported_table_status']
        require(int(status['Data_length'])+int(status['Index_length'])==t['engine_reported_bytes'],'Footprint fields disagree')
        session=t['session_variables'];innodb=t['innodb_settings']
        require(session['query_cache_type']=='OFF' and session['autocommit']=='ON'
                and 'STRICT_ALL_TABLES' in session['sql_mode'] and 'NO_ENGINE_SUBSTITUTION' in session['sql_mode'],'Session controls differ')
        require(all(int(innodb[k])==benchmark.POOL for k in ('innodb_buffer_pool_size','innodb_buffer_pool_size_max','innodb_buffer_pool_size_auto_min')),'Pool controls differ')
        require(innodb['innodb_buffer_pool_load_at_startup']=='OFF' and innodb['innodb_buffer_pool_dump_at_shutdown']=='OFF','Pool persistence enabled')
        require(t['plans']['lookup'][0]['key']=='PRIMARY' and t['plans']['lookup'][0]['type']=='const'
                and t['plans']['scan'][0]['type']=='ALL','Query plan changed')
        phases=[t['lookup_counters']]+t['scan_counters']
        for phase in phases:
            counters=phase['delta']
            require(set(counters)==set(benchmark.COUNTERS),'Missing/extra counter')
            require(all(type(v) is int and v>=0 for v in counters.values()),'Invalid counter')
            if n==32768:
                require(counters['Innodb_buffer_pool_reads']==0 and counters['Innodb_data_read']==0,'Small-table no-read finding changed')
            else:
                require(counters['Innodb_buffer_pool_reads']>0 and counters['Innodb_data_read']>0,'Large-table read finding changed')
    require(len(schemas)==1,'Different schemas')
    return stats


def load(run_id,mode):
    folder=ROOT/'evidence/cache-pressure'/run_id
    result=json.loads((folder/'results.json').read_text(encoding='utf-8'))
    stats=validate(result,run_id,mode)
    require((folder/'summary.md').read_text(encoding='utf-8')==benchmark.markdown(result),'Original summary differs')
    worker_hashes={}
    for i,t in enumerate(result['trials'],1):
        filename=f'trial-{i:02d}.json';worker=json.loads((folder/filename).read_text(encoding='utf-8'))
        stripped={k:v for k,v in t.items() if k not in ('position','project','db_image_id','runner_image_id','clean_stop')}
        require(worker==stripped,'Archived worker differs from host record: '+filename)
        worker_hashes[filename]=canonical_hash(worker)
    return result,stats,worker_hashes


def observations(result):
    rows=[]
    for t in result['trials']:
        for phase,timings,counters in [('lookup',t['lookup_ms'],[t['lookup_counters']]),('scan',t['scan_ms'],t['scan_counters'])]:
            rows.append(dict(run_id=result['run_id'],round=t['round'],position=t['position'],rows=t['rows'],phase=phase,
                samples=len(timings),mean_ms=statistics.mean(timings),payload_mib=t['payload_total_bytes']/1048576,
                table_mib=t['engine_reported_bytes']/1048576,pool_mib=t['buffer_pool_bytes']/1048576,
                pool_reads=sum(c['delta']['Innodb_buffer_pool_reads'] for c in counters),
                pool_read_requests=sum(c['delta']['Innodb_buffer_pool_read_requests'] for c in counters),
                read_ahead=sum(c['delta']['Innodb_buffer_pool_read_ahead'] for c in counters),
                data_read_bytes=sum(c['delta']['Innodb_data_read'] for c in counters),
                dirty_pages_before=counters[0]['before']['Innodb_buffer_pool_pages_dirty'],
                dirty_pages_after=counters[-1]['after']['Innodb_buffer_pool_pages_dirty'],
                dataset_sha256=t['dataset_sha256']))
    return rows


def charts(rows,stats,directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.hashsalt':'cu-cache-pressure-v1'})
    colors=['#197b88','#b65c19'];labels=['32,768 rows\n37.56 MiB table','262,144 rows\n293.78 MiB table']
    fig,axes=plt.subplots(2,1,figsize=(10,7.8))
    fig.subplots_adjust(left=.23,right=.96,top=.77,bottom=.17,hspace=.65)
    for ax,phase,title in zip(axes,('lookup','scan'),('Random primary-key lookup','Full CRC32 scan')):
        for y,n in enumerate(SIZES):
            group=[r for r in rows if r['rows']==n and r['phase']==phase]
            values=[r['mean_ms'] for r in group];s=stats[str(n)][phase+'_ms']
            ax.scatter(values,[y+(i-2.5)*.045 for i in range(6)],color=colors[y],s=32,zorder=3)
            ax.errorbar(s['mean'],y,xerr=s['sample_sd'],fmt='D',color='black',ms=4,capsize=4,zorder=4)
        ax.set_yticks(range(2),labels);ax.set_ylim(1.45,-.45);ax.set_xlim(left=0)
        ax.set_title(title,loc='left',weight='bold');ax.set_xlabel('Trial mean latency (ms)')
        ax.spines[['top','right','left']].set_visible(False);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('InnoDB: beyond a fixed 128 MiB buffer pool',x=.04,ha='left',y=.98,fontsize=17,weight='bold')
    fig.text(.04,.92,'Six trials per size · 5,000 lookups and 3 scans per trial · pilot excluded')
    fig.legend(handles=[Line2D([],[],color='#666666',marker='o',linestyle='None',label='Trial mean'),
                        Line2D([],[],color='black',marker='D',label='Mean ± sample SD')],loc='upper left',bbox_to_anchor=(.03,.89),ncol=2,frameon=False)
    fig.text(.04,.045,'Different horizontal scales, both starting at zero. SD is not a confidence interval.\n'
             'The large table has 8× the payload. Scan time includes CRC32 work; it is not a pure cache penalty.\n'
             'Driver/network included. Post-verification reads; OS and virtualization caches remain.',fontsize=9,linespacing=1.6)
    save(fig,directory,'cache-pressure-latency',plt)
    fig,axes=plt.subplots(1,3,figsize=(12,5.7));fig.subplots_adjust(left=.08,right=.97,top=.77,bottom=.27,wspace=.5)
    values=[37.5625,293.78125]
    axes[0].bar(range(2),values,color=colors,width=.55)
    axes[0].axhline(128,color='black',ls='--',lw=1.2);axes[0].text(.5,133,'128 MiB pool',ha='center',fontsize=9)
    for i,v in enumerate(values):axes[0].text(i,v+5,f'{v:.2f}',ha='center',fontsize=9)
    axes[0].set_ylim(0,340);axes[0].set_title('Actual table allocation',loc='left',weight='bold');axes[0].set_ylabel('Engine-reported MiB')
    for ax,phase,title,ylabel in [(axes[1],'lookup','Random lookup read activity','Pool reads / 1,000 lookups'),(axes[2],'scan','Full-scan read volume','Data-read MiB / scan')]:
        for i,n in enumerate(SIZES):
            group=[r for r in rows if r['rows']==n and r['phase']==phase]
            v=[r['pool_reads']/r['samples']*1000 if phase=='lookup' else r['data_read_bytes']/r['samples']/1048576 for r in group]
            ax.scatter([i+(k-2.5)*.035 for k in range(6)],v,s=30,color=colors[i],zorder=3)
            ax.errorbar(i,statistics.mean(v),yerr=statistics.stdev(v),fmt='D',color='black',ms=4,capsize=4,zorder=4)
            if not any(v):ax.annotate('0 in all trials',(i,0),xytext=(0,10),textcoords='offset points',ha='center',fontsize=8)
        ax.set_ylim(bottom=-.04*ax.get_ylim()[1]);ax.set_title(title,loc='left',weight='bold',fontsize=11);ax.set_ylabel(ylabel)
    for ax in axes:
        ax.set_xticks(range(2),['Small','Large']);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('Read counters distinguish fitting and oversized tables',x=.035,ha='left',y=.98,fontsize=17,weight='bold')
    fig.text(.035,.91,'Small: 32 MiB payload · Large: 256 MiB payload · six full-run trials per size')
    fig.text(.035,.07,'Read panels: each point is one trial; diamonds show mean ± sample SD. Small-table counters were zero.\n'
             'Global InnoDB counters include background activity. Pool reads are not a query miss percentage.\n'
             'Data-read bytes do not prove physical SSD access: OS/VM caching and read-ahead remain.',fontsize=9,linespacing=1.7)
    save(fig,directory,'cache-pressure-read-activity',plt)


def save(fig,directory,name,plt):
    for ext in ('png','svg'):fig.savefig(directory/(name+'.'+ext),dpi=180,metadata={'Date':None} if ext=='svg' else {})
    plt.close(fig)


def report(full,stats,rows):
    table=['| Rows | Payload MiB | Table MiB | Lookup ms | Scan ms |','| ---: | ---: | ---: | ---: | ---: |']
    for n in SIZES:
        t=next(t for t in full['trials'] if t['rows']==n)
        cells=[f"{stats[str(n)][m]['mean']:.4f} ± {stats[str(n)][m]['sample_sd']:.4f}" for m in ('lookup_ms','scan_ms')]
        table.append('| '+' | '.join([f'{n:,}',str(t['payload_total_bytes']//1048576),f"{t['engine_reported_bytes']/1048576:.2f}"]+cells)+' |')
    lookup_ratio=stats['262144']['lookup_ms']['mean']/stats['32768']['lookup_ms']['mean']
    scan_ratio=stats['262144']['scan_ms']['mean']/stats['32768']['scan_ms']['mean']
    large=[t for t in full['trials'] if t['rows']==262144]
    reads=[t['lookup_counters']['delta']['Innodb_buffer_pool_reads'] for t in large]
    return f'''# InnoDB cache-pressure findings

**Verified full run:** `{FULL}` (October 17, 2026, Europe/Berlin; run IDs use UTC).
Twelve fresh-volume trials cover six rounds per table size: **1,769,472 verified row
loads, 60,000 timed lookups and 36 timed scans**. The separate two-trial pilot
`{PILOT}` was validated and excluded from all statistics and charts below.

## What changed when the table exceeded the pool

The buffer pool stayed at **128 MiB**. Actual engine-reported table allocation was
**37.56 MiB** for 32,768 rows and **293.78 MiB** for 262,144 rows in every trial.
The payload alone was 32 MiB versus 256 MiB; allocation includes row/index overhead.

The small table recorded **zero buffer-pool reads and zero data-read bytes** during
all measured lookup and scan windows. The large table recorded buffer-pool reads
in every window, including **{min(reads):,}–{max(reads):,} reads per 5,000-query lookup phase**.
This supports the intended fitting-versus-oversized distinction at the InnoDB pool.
It does not mean physical SSD media were read: OS and virtualization caches remained.

Large-table mean lookup latency was **{lookup_ratio:.2f}×** the small-table mean.
Mean scan time was **{scan_ratio:.2f}×**, but the large scan also processes **8× as much
payload**, computes CRC32 for every row, and triggers read-ahead. That ratio is not
an isolated cache-miss penalty. Table size changes B-tree shape and locality too;
a same-table/different-pool experiment would isolate capacity more closely.

![Trial means and variability](figures/cache-pressure-latency.png)

## Complete timing summary

Mean ± sample SD across six trial means. Each lookup mean uses 5,000 queries; each
scan mean uses three scans. The experimental repeat is the trial, not each row,
lookup or scan. SD describes observed spread, not a confidence interval.

{chr(10).join(table)}

All 24 trial/phase observations are in the [CSV](data/cache-pressure-observations.csv).
The [statistics JSON](data/cache-pressure-statistics.json) retains timing distributions,
phase counters, provenance and canonical hashes. Raw evidence retains every timing,
query ID, counter snapshot and separate worker result. No significance test or
independent-machine replication is claimed.

## Why the counter evidence matters

![Footprints and InnoDB read activity](figures/cache-pressure-read-activity.png)

The small table's reads were satisfied without new InnoDB data reads during measured
windows. For the large table, random lookups generated read activity and each full
scan read approximately a table's worth of data. Repeated scans still generated
reads; three scans are not evidence of a fully steady state.

The read-activity chart normalizes lookup-phase pool reads per 1,000 queries; this is
**not a query miss percentage**. A lookup can touch multiple pages, and global counters
can include background work. Scan data-read bytes include prefetch/read-ahead and do
not count only the returned aggregate. `Innodb_buffer_pool_read_requests`, read-ahead,
wait-free, data-read operations/bytes and dirty/free/data page gauges are preserved.
EXPLAIN recorded PRIMARY/const for point queries and ALL for full scans in every trial.

Dirty pages were not equalized: the small trials had roughly 2,450 dirty pages before
lookups, whereas large trials had 6–13. The different load/flush history is a limitation,
not something to omit because the timings look consistent. We did not force checkpoints
or separate server CPU from client/network cost.

## Controls, verification and boundaries

- A new isolated Compose project and volume for every trial. Six rounds alternate
  size order; each size runs first three times. All 12 databases stopped cleanly,
  without recorded OOM kills. The normal lab volume was not used for these trials.
- Same integer-key/1,024-byte binary-payload schema, generation seed and fixed pool.
  Small-table rows are a prefix of the large dataset. Data generation uses SHAKE-256;
  every byte was checked by streamed verification. The host regenerated ordered SHA-256
  hashes and CRC32 scan oracles. Actual table size and pool size were checked.
- Full verification and 1,000 point warmups precede timed random queries. Three scans
  follow the lookup phase. This fixed phase order is post-verification, not cold-cache.
- MariaDB 11.8.9, Python 3.12.15, PyMySQL 1.1.2, WSL2 containers. Recorded power:
  `{full['power_condition']}`. Runner quota: one CPU/512 MiB; isolated DB config:
  two CPUs/2 GiB. Quotas are not dedicated cores. Images and source identities are archived.
- Query cache off, strict/no-substitution mode, autocommit on. Buffer-pool size,
  maximum and shrink minimum fixed at 128 MiB; pool dump/load disabled. No cache
  flushing of the host, VM or storage device was attempted.
- Timing includes execute/fetch and driver/network work. Point answers return a full
  payload; scans return COUNT and SUM(CRC32(payload)). Scan timings are not directly
  comparable with the different SQL in the flight benchmarks. Load timing includes
  generation and is not presented here as server ingest throughput.

Pilot and full runs recorded different DB and runner image identities. Each identity
was constant within its own run; measured source hashes, selected settings, runtime
and server version matched. The cause of the identity change is not established by
these records, so byte-identical images across runs are not claimed. Pilot timings
are excluded, and both sets of identities are retained in derived provenance.

**Practical implication:** test the intended working set against the actual InnoDB
pool instead of extrapolating from a small warm table. These measurements show a
capacity-related change worth planning for; they do not establish a recommended pool
size for every application or justify replacing InnoDB with another engine. This is
one engine on one laptop, not a five-engine equal-budget benchmark, a host-RAM overflow
test, server-side contention measurement, or physical-storage latency measurement.

## Evidence and reproduction

- [Full results](../evidence/cache-pressure/{FULL}/results.json) and [original summary](../evidence/cache-pressure/{FULL}/summary.md).
- [Separate pilot](../evidence/cache-pressure/{PILOT}/results.json).
- Both directories preserve every `trial-NN.json`; all 14 worker files match their host records.
- [Protocol and run commands](cache-pressure-method.md), [recommendations](engine-recommendations.md).

Regenerate this report, data and charts without Docker or new database measurements:

```powershell
python -m pip install -r requirements-report.txt
python scripts/report_cache_pressure_findings.py
```

The generator validates both runs' schedules, controls, data/CRC oracles, footprints,
query streams, plans, counter deltas, clean stops, saved statistics and original
summaries. It compares every archived worker JSON with its host record and refuses
changes that invalidate the narrative. Canonical JSON hashes tolerate Git line-ending
conversion; original evidence and its captured source hashes are not rewritten.
Historical host and worker source fingerprints are verified against the immutable
[measured source snapshot](../provenance/cache-pressure/README.md), including LF/CRLF
representations and pinned Git blob identities. The derived statistics distinguish
that measured source from the current report generator; the current orchestrator
need not be the code that produced these archived timings. Raw evidence is unchanged.
Use `--output-root <dir>` for a separate derived `docs/` tree; no Git history or
network access is required. See [report reproduction](report-reproducibility.md)
for rendering limits.
'''


def build(output_root=None):
    output_root=ROOT if output_root is None else Path(output_root)
    pilot,ps,pw=load(PILOT,'pilot');full,stats,fw=load(FULL,'full')
    require(pilot['source_sha256']==full['source_sha256'] and pilot['power_condition']==full['power_condition'],'Pilot/full controls differ')
    trials=pilot['trials']+full['trials']
    for field in ('runtime','server_version','global_variables','session_variables','innodb_settings','source_sha256'):
        require(all(t[field]==trials[0][field] for t in trials),'Recorded conditions differ: '+field)
    for run in (pilot,full):
        for field in ('db_image_id','runner_image_id'):
            require(len({t[field] for t in run['trials']})==1,'Image identity changed within run')
    rows=observations(full)
    for n,v in [(32768,37.5625),(262144,293.78125)]:
        require(all(r['table_mib']==v for r in rows if r['rows']==n),'Footprint labels require review')
    for field in ('lookup_ms','scan_ms'):
        require(stats['262144'][field]['mean']>stats['32768'][field]['mean'],'Timing direction changed')
    data=output_root/'docs/data';figures=output_root/'docs/figures';data.mkdir(parents=True,exist_ok=True);figures.mkdir(parents=True,exist_ok=True)
    with (data/'cache-pressure-observations.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    provenance=dict(full_run=FULL,excluded_pilot=PILOT,statistical_unit='trial mean; six per size',full_statistics=stats,pilot_statistics=ps,
        canonical_results_sha256={FULL:canonical_hash(full),PILOT:canonical_hash(pilot)},worker_canonical_sha256={FULL:fw,PILOT:pw},
        phase_observations=rows,source_sha256=full['source_sha256'],runtime=trials[0]['runtime'],server_version=trials[0]['server_version'],
        image_identities={r['run_id']:{k:r['trials'][0][k] for k in ('db_image_id','runner_image_id')} for r in (pilot,full)},power_condition=full['power_condition'],
        measured_source_snapshot=dict(revision=MEASURED_SOURCE_REVISION,directory='provenance/cache-pressure',
            manifest_sha256_lf=hashlib.sha256((SOURCE_SNAPSHOT/'manifest.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()),
        report_generator=dict(path='scripts/report_cache_pressure_findings.py',
            sha256_lf=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()))
    (data/'cache-pressure-statistics.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    charts(rows,stats,figures)
    (output_root/'docs/cache-pressure-findings.md').write_text(report(full,stats,rows),encoding='utf-8')
    print('Validated 14 trials and 14 worker files; reported 12 full trials and 24 trial/phase observations.')
    return provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=ROOT,
                        help='Write a separate derived docs tree without changing source/evidence.')
    args=parser.parse_args()
    build(args.output_root)


if __name__=='__main__':main()
