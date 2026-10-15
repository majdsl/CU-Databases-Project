"""Generate storage findings from the verified full run; requires matplotlib."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

RUN = '20261006T120404Z-storage-a5d23142'
ENGINES = ['InnoDB', 'Aria', 'MyISAM', 'ROCKSDB', 'MEMORY']
MIB = 1024 ** 2


def build(source, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    r = json.loads(source.read_text(encoding='utf-8'))
    if r['status'] != 'completed' or r['pilot'] or r['rounds'] != 5 or len(r['trials']) != 25:
        raise ValueError('Expected a completed five-round full run')
    if r['run_id'] != RUN:
        raise ValueError('This report is scoped to the verified October 6 run')
    expected = {(e, i) for e in ENGINES for i in range(1, 6)}
    if {(t['engine'], t['round']) for t in r['trials']} != expected:
        raise ValueError('Missing or duplicate trials')
    records = []
    for t in r['trials']:
        assert t['load']['verified_rows'] == r['rows']
        assert t['load']['verified_dataset_sha256'] == r['dataset_sha256']
        for phase in ('before', 'after'):
            assert t[phase+'_stop']['ExitCode'] == 0 and not t[phase+'_stop']['OOMKilled']
            for metric in ('allocated_bytes', 'apparent_bytes'):
                assert t[phase]['regular_file_'+metric] == sum(f[metric] for f in t[phase]['files'] if f['counted'])
        for metric in ('allocated_bytes', 'apparent_bytes'):
            assert t['delta']['regular_file_'+metric] == t['after']['regular_file_'+metric]-t['before']['regular_file_'+metric]
        status = t['load']['live_engine_reported_table_status']
        records.append(dict(engine=t['engine'], round=t['round'],
            allocated_delta_bytes=t['delta']['regular_file_allocated_bytes'],
            apparent_delta_bytes=t['delta']['regular_file_apparent_bytes'],
            live_data_length_bytes=status['Data_length'], live_index_length_bytes=status['Index_length']))
    docs = output/'docs'; figures = docs/'figures'; data = docs/'data'
    figures.mkdir(parents=True, exist_ok=True); data.mkdir(parents=True, exist_ok=True)
    with (data/'storage-observations.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    stats = {}
    for e in ENGINES:
        rows = [x for x in records if x['engine']==e]
        stats[e] = {key: {'mean':statistics.mean(x[key] for x in rows),
                          'sd':statistics.stdev(x[key] for x in rows),
                          'min':min(x[key] for x in rows), 'max':max(x[key] for x in rows)}
                    for key in list(rows[0])[2:]}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
        'axes.spines.right':False, 'axes.spines.left':False, 'axes.titleweight':'bold',
        'svg.fonttype':'none', 'savefig.facecolor':'white'})
    colors = ['#285F88','#32857E','#AA7037','#7464A7']
    fig,ax=plt.subplots(figsize=(10,5.6));fig.subplots_adjust(left=.14,right=.95,bottom=.34,top=.78)
    values=[stats[e]['allocated_delta_bytes']['mean']/MIB for e in ENGINES[:4]]
    bars=ax.barh(ENGINES[:4],values,color=colors,height=.58)
    ax.invert_yaxis();ax.set_xlim(0,10.7);ax.set_xlabel('Increase in allocated regular-file space (MiB)')
    ax.set_axisbelow(True);ax.xaxis.grid(True,color='#E5E9ED');ax.tick_params(axis='y',length=0)
    for b,v in zip(bars,values): ax.text(v+.12,b.get_y()+b.get_height()/2,f'{v:.3f}',va='center',weight='bold')
    fig.suptitle('Disk growth after loading 10,000 rows',x=.08,y=.94,ha='left',fontsize=19,weight='bold')
    fig.text(.08,.86,'Five fresh-volume trials per engine • MariaDB 11.8.9 • clean shutdown',fontsize=11,color='#4B5966')
    fig.text(.08,.06,'Means shown; allocated-byte sample SD = 0 for every engine in this run.\nIncludes logs, metadata and restart effects; not table-only size or host SSD usage.\nMEMORY is excluded here because its rows are volatile. 1 MiB = 1,048,576 bytes.',fontsize=10,color='#4B5966',linespacing=1.6)
    for ext in ('png','svg'): fig.savefig(figures/f'storage-disk-growth.{ext}',dpi=180)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.5));fig.subplots_adjust(left=.14,right=.95,bottom=.36,top=.73)
    d=stats['MEMORY']['live_data_length_bytes']['mean']/MIB;i=stats['MEMORY']['live_index_length_bytes']['mean']/MIB
    ax.barh(['MEMORY'],[d],color='#287C83',height=.42,label='Data_length')
    ax.barh(['MEMORY'],[i],left=[d],color='#DCAB55',height=.42,label='Index_length')
    ax.text(d/2,0,f'{d:.3f} MiB',ha='center',va='center',color='white',weight='bold')
    ax.text(d+i+.12,0,f'{d+i:.3f} MiB total',va='center',weight='bold')
    ax.set_xlim(0,10.7);ax.set_ylim(-.55,.55);ax.set_xlabel('Engine-reported allocation while the server is running (MiB)')
    ax.tick_params(axis='y',length=0);ax.set_axisbelow(True);ax.xaxis.grid(True,color='#E5E9ED')
    ax.legend(loc='lower left',bbox_to_anchor=(.13,.16),bbox_transform=fig.transFigure,ncol=2,frameon=False)
    fig.suptitle('MEMORY uses RAM for its rows and indexes',x=.08,y=.94,ha='left',fontsize=19,weight='bold')
    fig.text(.08,.85,f'Index allocation: {i:.3f} MiB • identical reported values in all five trials',color='#4B5966')
    fig.text(.08,.04,'Approximate engine allocation, not total process RAM. Rows disappear at shutdown.\nIts 0.121 MiB disk growth is metadata/server overhead, not persistent row storage.',fontsize=10,color='#4B5966',linespacing=1.6)
    for ext in ('png','svg'): fig.savefig(figures/f'storage-memory-allocation.{ext}',dpi=180)
    plt.close(fig)
    lines=['# Storage findings','',
        '**The full run completed 25 verified trials: 10,000 identical rows per trial, five trials per engine.**',
        'Allocated datadir growth was identical across repeats for each engine. These results describe this workload and shutdown procedure, not a general storage-efficiency ranking.','',
        '![Allocated disk growth for the four persistent engines](figures/storage-disk-growth.png)','',
        '## Recorded results','',
        '| Engine | Trials | Mean allocated growth (bytes) | Mean growth (MiB) | Sample SD (bytes) |',
        '| --- | ---: | ---: | ---: | ---: |']
    for e in ENGINES:
        st=stats[e]['allocated_delta_bytes']
        lines.append(f"| {e}{' (overhead only)' if e=='MEMORY' else ''} | 5 | {st['mean']:,.0f} | {st['mean']/MIB:.3f} | {st['sd']:.0f} |")
    lines+=['','The initialized empty-database baseline was 156,749,824 allocated bytes in every trial. Growth is the signed difference between the stopped-server inventories before and after loading. It covers regular files across the entire datadir, including logs and metadata. One MiB is 1,048,576 bytes.','',
        '## What the measurements support','',
        '- In this run, ROCKSDB had the smallest datadir growth among the four persistent engines, followed by MyISAM, Aria and InnoDB. This ordering includes engine and server overhead.',
        '- Allocation did not vary across the five trials at the filesystem block resolution. Apparent file lengths did vary slightly. Zero observed sample SD does not imply zero uncertainty or universal repeatability.',
        '- File inventories help explain the totals: the InnoDB `.ibd` file occupied 9,441,280 allocated bytes in each trial; Aria also grew its log. These are observations of this run, not general requirements of those engines.','',
        '![Live MEMORY allocation](figures/storage-memory-allocation.png)','',
        f"MEMORY reported {stats['MEMORY']['live_data_length_bytes']['mean']:,.0f} data bytes and {stats['MEMORY']['live_index_length_bytes']['mean']:,.0f} index bytes before shutdown ({d+i:.3f} MiB combined). This is approximate engine allocation, not total server RAM. Its disk growth does not represent persistent copies of its rows.",'',
        'ROCKSDB reported zero for live `Data_length` and `Index_length`, despite nonzero disk allocation and recorded SST files. Do not interpret those live statistics as zero storage use. The report therefore uses filesystem measurements for the disk comparison.','',
        '## Method and limits','',
        f"- Full run: `{RUN}`; MariaDB 11.8.9; `{r['power_condition']}`.",
        '- Each trial used a fresh isolated volume. Engine order was balanced across five rounds. All trials shared the same laptop.',
        '- Every loaded row was checked against the generated data before shutdown. Recorded checksums matched across all 25 trials; 50 clean shutdown records and all inventory sums/deltas were checked.',
        '- Measurements include table creation, loading, validation, ANALYZE, and a second startup/shutdown cycle. There was no separate empty-workload control to subtract restart effects.',
        '- MyRocks was not forced into fully compacted steady state. No compression ratio, crash durability equivalence or Windows VHDX/physical SSD size is inferred.',
        '- This uses only 10,000 synthetic rows with the supplied schema/indexes. It does not establish behavior for other data sizes, distributions or long-lived databases.',
        '- The separate pilot was used to validate the procedure and is excluded from these averages.','',
        '## Evidence and reproduction','',
        f'- [Full raw results](../evidence/storage/{RUN}/results.json) and [original summary](../evidence/storage/{RUN}/summary.md).',
        '- [All 25 observations](data/storage-observations.csv), [statistics and provenance](data/storage-statistics.json), and [experiment method](storage-method.md).',
        '- The existing experiment dependencies are unchanged. Regenerating figures additionally requires Matplotlib; viewing the PNG/SVG files needs no installation.',
        '- From the project root, with Matplotlib installed:','',
        '```powershell','python scripts/report_storage_findings.py','```','',
        'This regenerates the report, charts and derived data without rerunning MariaDB.','']
    (docs/'storage-findings.md').write_text('\n'.join(lines),encoding='utf-8')
    provenance={'run_id':r['run_id'],'trials':25,'rows_per_trial':r['rows'],
        'dataset_sha256':r['dataset_sha256'],'source_results_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'matplotlib_version':matplotlib.__version__,'byte_unit':'MiB = 1048576 bytes','statistics':stats}
    (data/'storage-statistics.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print('Generated report, four figure files, and two derived-data files.')

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=root/'evidence/storage'/RUN/'results.json')
    p.add_argument('--output-root',type=Path,default=root)
    args=p.parse_args();build(args.input,args.output_root)
