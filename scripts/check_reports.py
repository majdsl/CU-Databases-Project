"""Regenerate all archived reports in a disposable copy; never overwrite the checkout.

Requires the reporting dependencies and checksum-pinned OpenFlights data already
installed/fetched. No Docker, Git metadata or network access is used by this check.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIRECTORIES = ('benchmarks', 'scripts', 'sql', 'docker', 'provenance', 'evidence', 'data/openflights')
INPUT_FILES = ('Dockerfile', 'requirements.txt', 'requirements-report.txt')
REPORTS = {
    'report_cpu.py': ('cpu-measurements.md', 'figures/cpu-chart-data.json',
                      'figures/cpu-morning.svg', 'figures/cpu-evening.svg'),
}
for script, stem, figures in (
        ('report_storage_findings.py', 'storage', ('storage-disk-growth', 'storage-memory-allocation')),
        ('report_recovery_findings.py', 'recovery', ('recovery-row-survival', 'recovery-restart-verification')),
        ('report_openflights_findings.py', 'openflights', ('openflights-load', 'openflights-warm-reads')),
        ('report_memory_findings.py', 'memory-index', ('memory-index-latency', 'memory-index-access-paths')),
        ('report_cache_pressure_findings.py', 'cache-pressure', ('cache-pressure-latency', 'cache-pressure-read-activity')),
        ('report_write_diagnostics_findings.py', 'write-diagnostics',
         ('write-diagnostics-throughput', 'write-diagnostics-cpu', 'write-diagnostics-lock-waits')),
        ('report_rocksdb_compression_findings.py', 'rocksdb-compression',
         ('rocksdb-compression-size', 'rocksdb-compression-timings'))):
    REPORTS[script] = (stem+'-findings.md', 'data/'+stem+'-observations.csv',
                       'data/'+stem+'-statistics.json',
                       *(f'figures/{figure}.{ext}' for figure in figures for ext in ('png', 'svg')))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_name(path, root):
    """Match the portable names in REPORTS on Windows as well as POSIX."""
    return path.relative_to(root).as_posix()


def input_paths(root):
    """Allowlisted project inputs only; local state and symlink targets stay out."""
    root = Path(root)
    paths = []
    for directory in INPUT_DIRECTORIES:
        folder = root / directory
        if not folder.exists():
            continue
        require(not folder.is_symlink(), 'Refusing symlinked report input: '+directory)
        for path in folder.rglob('*'):
            relative = path.relative_to(root)
            if any(part.startswith('.') and part != '.gitattributes' for part in relative.parts):
                continue
            if '__pycache__' in relative.parts or path.suffix in ('.pyc', '.pyo'):
                continue
            require(not path.is_symlink(), 'Refusing symlinked report input: '+str(relative))
            if path.is_file():
                paths.append(relative)
    for name in (*INPUT_FILES, *(p.name for p in root.glob('compose*.yaml'))):
        path = root / name
        if path.exists():
            require(not path.is_symlink() and path.is_file(), 'Invalid report input: '+name)
            paths.append(Path(name))
    return sorted(set(paths))


def copy_inputs(source, target):
    paths = input_paths(source)
    for relative in paths:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, destination)
    return paths


def same_json(actual, expected, location='JSON'):
    """Compare all measurements/provenance with only harmless float roundoff."""
    if type(expected) is float and type(actual) in (int, float):
        require(math.isfinite(actual) and math.isfinite(expected) and
                math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                'Changed number at '+location)
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and actual.keys() == expected.keys(), 'Changed keys at '+location)
        for key in expected:
            same_json(actual[key], expected[key], location+'.'+key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), 'Changed length at '+location)
        for index, (value, reference) in enumerate(zip(actual, expected)):
            same_json(value, reference, f'{location}[{index}]')
    else:
        require(type(actual) is type(expected) and actual == expected, 'Changed value at '+location)


def compare_output(actual, reference, script):
    suffix = actual.suffix
    if suffix == '.json':
        generated = json.loads(actual.read_text(encoding='utf-8-sig'))
        expected = json.loads(reference.read_text(encoding='utf-8-sig'))
        # These fields identify the reporting code, not the measured experiment.
        # Check against the code actually executed before excluding the digest
        # from the comparison to an earlier generated artifact.
        source_hash = hashlib.sha256(script.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        for key in ('generator_lf_sha256', 'generator_source_sha256_lf'):
            if key in generated:
                require(generated[key] == source_hash, 'Incorrect current generator provenance')
                generated.pop(key)
                expected.pop(key, None)
        if 'report_generator' in generated:
            require(generated['report_generator']['sha256_lf'] == source_hash,
                    'Incorrect current report-generator provenance')
            generated['report_generator'] = {k: v for k, v in generated['report_generator'].items() if k != 'sha256_lf'}
            if 'report_generator' in expected:
                expected['report_generator'] = {k: v for k, v in expected['report_generator'].items() if k != 'sha256_lf'}
        same_json(generated, expected, str(reference))
    elif suffix == '.csv':
        with actual.open(encoding='utf-8', newline='') as left, reference.open(encoding='utf-8', newline='') as right:
            generated, expected = list(csv.reader(left)), list(csv.reader(right))
        require(len(generated) == len(expected), 'Changed CSV row count: '+str(reference))
        for row, (values, originals) in enumerate(zip(generated, expected)):
            require(len(values) == len(originals), 'Changed CSV columns: '+str(reference))
            for column, (value, original) in enumerate(zip(values, originals)):
                if value == original:
                    continue
                try:
                    same_json(float(value), float(original), f'{reference}:{row}:{column}')
                except ValueError as error:
                    raise ValueError('Changed CSV cell: '+str(reference)) from error
    elif suffix == '.md':
        require(actual.read_text(encoding='utf-8') == reference.read_text(encoding='utf-8'),
                'Changed report narrative: '+str(reference))
    elif suffix == '.svg':
        require(ET.parse(actual).getroot().tag.endswith('svg'), 'Invalid SVG: '+str(actual))
    elif suffix == '.png':
        from PIL import Image
        with Image.open(actual) as image:
            require(image.format == 'PNG' and min(image.size) > 0, 'Invalid PNG: '+str(actual))
            image.verify()
    else:
        raise ValueError('Unexpected report output: '+str(actual))


def regenerate(source=ROOT, repeat=False):
    """Execute current source, check fresh outputs and preserve all original inputs."""
    source = Path(source).resolve()
    require((source/'data/openflights/routes.dat').is_file(),
            'Missing pinned dataset: run python scripts/fetch_openflights.py first')
    paths = input_paths(source)
    before = {str(path): digest(source/path) for path in paths}
    outputs = {}
    try:
        with tempfile.TemporaryDirectory(prefix='cu-report-check-') as temporary:
            scratch = Path(temporary)
            copy_inputs(source, scratch)
            (scratch/'docs/data').mkdir(parents=True)
            (scratch/'docs/figures').mkdir()
            environment = dict(os.environ, MPLCONFIGDIR=str(scratch/'matplotlib'),
                               XDG_CACHE_HOME=str(scratch/'cache'), PYTHONDONTWRITEBYTECODE='1')
            optimization = ['-'+'O'*min(sys.flags.optimize, 2)] if sys.flags.optimize else []
            for script, names in REPORTS.items():
                command = [sys.executable, *optimization, str(scratch/'scripts'/script)]
                subprocess.run(command, cwd=scratch, env=environment, check=True)
                for name in names:
                    path = scratch/'docs'/name
                    require(path.is_file() and path.stat().st_size > 0, 'Missing generated output: '+name)
                    reference = source/'docs'/name
                    require(reference.is_file(), 'Missing reference report output: '+name)
                    compare_output(path, reference, scratch/'scripts'/script)
                    outputs[name] = digest(path)
                if repeat:
                    subprocess.run(command, cwd=scratch, env=environment, check=True)
                    for name in names:
                        require(digest(scratch/'docs'/name) == outputs[name], 'Nondeterministic repeat: '+name)
            expected = set(outputs)
            actual = {output_name(path, scratch/'docs') for path in (scratch/'docs').rglob('*') if path.is_file()}
            require(actual == expected, 'Unexpected or missing generated report files')
            # Generators must not mutate their copied inputs either.
            require(before == {str(path): digest(scratch/path) for path in paths}, 'A generator changed report inputs')
    finally:
        require(before == {str(path): digest(source/path) for path in paths}, 'Original report inputs changed')
    return dict(reports=len(REPORTS), outputs=len(outputs), evidence_files=sum(
        Path(path).parts[0] == 'evidence' for path in before),
        optimization=sys.flags.optimize, repeat=repeat, input_sha256=before, output_sha256=outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat', action='store_true', help='Require byte-identical repeated outputs in this environment')
    args = parser.parse_args()
    result = regenerate(repeat=args.repeat)
    print(f"REPORT CHECK PASS: {result['reports']} reports, {result['outputs']} outputs; inputs preserved; optimization={result['optimization']}")


if __name__ == '__main__':
    main()
