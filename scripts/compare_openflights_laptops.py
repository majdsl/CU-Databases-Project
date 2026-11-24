"""View the two laptop runs offline; optionally verify the private handoff without publishing it."""
import argparse
import csv
from dataclasses import asdict
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import openflights as bench

ARCHIVE = ROOT / 'evidence/reproductions/20261115-zein-wsl2-openflights'
FIRST = ROOT / 'evidence/openflights/20261009T160813Z-openflights-6884f225'
RUNS = {'pilot': '20261115T222419Z-openflights-e0ab128c', 'full': '20261115T223047Z-openflights-3073fafb'}
HANDOFF = 'af4ba9377c6cf4ede5fa0f21067567c25296e04e7421afec119dff0320f2129d'
ROUTES = 'ea46aabb9533882cf36baa761b285ef8f8829915ff1b3a689fc8315206532441'
METRICS = {'load_s': 'load_seconds', 'lookup_ms': 'lookup_ms', 'scan_ms': 'scan_ms', 'source_ms': 'source_ms'}
PUBLIC_FILES = tuple(stage + '/' + name for stage in RUNS for name in ('results.json', 'summary.md'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_run(raw, summary, run_id, pilot):
    run = json.loads(raw)
    require(run['experiment'] == 'openflights_routes_v1' and run['run_id'] == run_id
            and run['config'] == asdict(bench.Config(pilot=pilot)), 'Wrong experiment, run ID or stage')
    require(run['rows'] == 67663 and run['dataset_sha256'] == ROUTES, 'Route data differ')
    stats = bench.summarize(run)  # Rechecks schedule, row digests, sample counts and the trial means.
    require(stats == run['statistics'] and bench.markdown(run).splitlines() == summary.decode('utf-8').splitlines(),
            'Raw trials do not reproduce the supplied statistics or summary: ' + run_id)
    return run


def rounded(run):
    return {engine: {key + '_' + label: format(stats[source][stat], '.4f')
                     for key, source in METRICS.items() for label, stat in (('mean', 'mean'), ('sd', 'sample_sd'))}
            for engine, stats in run['statistics'].items()}


def published():
    with (ARCHIVE / 'full-summary.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    require([r['engine'] for r in rows] == list(bench.ENGINES), 'Missing or out-of-order published engines')
    fields = {key + '_' + label for key in METRICS for label in ('mean', 'sd')}
    result = {}
    for row in rows:
        engine = row.pop('engine')
        require(set(row) == fields and all(math.isfinite(float(v)) and float(v) >= 0 for v in row.values()),
                'Invalid published values: ' + engine)
        result[engine] = row
    return result


def checked_handoff(path, original, second):
    # Check exact identity before reading any private or compressed member. Do not extract the ZIP.
    require(path.stat().st_size == 115943, 'Unexpected handoff size')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == HANDOFF, 'Handoff SHA-256 differs')
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        names = bundle.namelist()
        require(len(set(names)) == len(names) == 30, 'Unexpected handoff contents')
        sums = bundle.read('SHA256SUMS.txt').decode().splitlines()
        require(len(sums) == 29 and sorted(sums) == sorted(
            hashlib.sha256(bundle.read(n)).hexdigest() + '  ' + n for n in names if n != 'SHA256SUMS.txt'),
            'Internal checksums differ')
        public = {n: bundle.read('openflights/' + n) for n in PUBLIC_FILES}
    stages = {stage: read_run(public[stage + '/results.json'], public[stage + '/summary.md'], rid, stage == 'pilot')
              for stage, rid in RUNS.items()}
    full = stages['full']
    for field in ('source_sha256', 'dataset', 'runtime', 'server_version', 'global_variables',
                  'session_variables', 'power_condition', 'cache_condition'):
        require(stages['pilot'][field] == full[field], 'Pilot/full differ on ' + field)
    require(original['dataset'] == full['dataset'] and original['scan_oracle'] == full['scan_oracle'],
            'Full-run data differ between laptops')
    for a, b in zip(original['trials'], full['trials']):
        for field in ('engine', 'round', 'position', 'lookup_ids', 'source_ids', 'source_result_counts'):
            require(a[field] == b[field], 'Full workloads differ on ' + field)
    require(rounded(full) == second, 'Recalculated second-laptop figures differ from the published CSV')
    return public


def save_public(files, destination):
    require(set(files) == set(PUBLIC_FILES), 'Unexpected public file list')
    destination.mkdir(parents=True, exist_ok=False)
    for name in PUBLIC_FILES:
        path = destination / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(files[name])


def table(first, second):
    yield '| Engine | Original load (s) | Second load (s) | Original scan (ms) | Second scan (ms) |'
    yield '| --- | ---: | ---: | ---: | ---: |'
    for engine in bench.ENGINES:
        cells = [r[engine][metric + '_mean'] + ' ± ' + r[engine][metric + '_sd']
                 for metric in ('load_s', 'scan_ms') for r in (first, second)]
        yield '| ' + ' | '.join([engine, *cells]) + ' |'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', type=Path, help='Verify the exact reviewed ZIP and recompute both stages')
    parser.add_argument('--save-to', type=Path, help='With --handoff, write four public files to a new directory')
    args = parser.parse_args()
    if args.save_to and not args.handoff:
        parser.error('--save-to requires --handoff')
    original = read_run((FIRST / 'results.json').read_bytes(), (FIRST / 'summary.md').read_bytes(), FIRST.name, False)
    second = published()
    if args.handoff:
        files = checked_handoff(args.handoff, original, second)
        if args.save_to:
            save_public(files, args.save_to)
        print('Handoff verified: 29 checksums, five pilot trials and 25 full trials.')
    else:
        print('Original laptop: recalculated from raw trials. Second laptop: published rounded summary.')
    print('Mean ± sample SD across five full trials per engine on each laptop. No Docker or SQL.\n')
    print('\n'.join(table(rounded(original), second)))


if __name__ == '__main__':
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError, zipfile.BadZipFile) as error:
        sys.exit('Comparison failed: ' + str(error))
