"""Strict, lossless route projection from a pinned OpenFlights CSV snapshot."""
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/openflights'


def parse_routes(raw):
    rows = []
    for number, fields in enumerate(csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True), 1):
        if len(fields) != 9:
            raise ValueError(f'Route {number}: expected nine fields')
        airline, alid, src, srcid, dst, dstid, codeshare, stops, equipment = fields
        for value, width in [(airline, 3), (src, 4), (dst, 4), (codeshare, 1), (equipment, 64)]:
            if len(value) > width or '\x00' in value:
                raise ValueError(f'Route {number}: string exceeds schema or contains NUL')
        def integer(value, nullable=False):
            if nullable and value == '\\N':
                return None
            if not value.isascii() or not value.isdecimal() or not 0 <= int(value) <= 2147483647:
                raise ValueError(f'Route {number}: invalid integer')
            return int(value)
        stop_count = integer(stops)
        if codeshare not in ('', 'Y') or stop_count > 255:
            raise ValueError(f'Route {number}: unsupported codeshare or stops value')
        rows.append((number, airline, integer(alid, True), src, integer(srcid, True),
                     dst, integer(dstid, True), codeshare, stop_count, equipment))
    if not rows:
        raise ValueError('Empty route dataset')
    return rows


def read_manifest(directory=DATA):
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['schema_version'] != 1:
        raise ValueError('Unsupported dataset manifest')
    return manifest


def validate_bytes(raw, manifest):
    if len(raw) != manifest['bytes'] or hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('OpenFlights file checksum/size mismatch; do not benchmark changed data')
    rows = parse_routes(raw)
    if len(rows) != manifest['rows']:
        raise ValueError('OpenFlights row count mismatch')
    return rows


def load_dataset(directory=DATA):
    manifest = read_manifest(directory)
    path = directory / 'routes.dat'
    if not path.is_file():
        raise ValueError('Missing routes.dat: run python scripts/fetch_openflights.py on the host, then rebuild runner')
    return manifest, validate_bytes(path.read_bytes(), manifest)


def fetch_dataset(directory=DATA):
    manifest = read_manifest(directory)
    path = directory / 'routes.dat'
    if path.exists():
        validate_bytes(path.read_bytes(), manifest)
        return path, 'verified existing file'
    expected_url = ('https://raw.githubusercontent.com/MariaDB/openflights/'
                    + manifest['commit'] + '/data/routes.dat')
    if manifest['url'] != expected_url or len(manifest['commit']) != 40:
        raise ValueError('Unexpected download origin or revision')
    with urlopen(expected_url, timeout=60) as response:
        raw = response.read(manifest['bytes'] + 1)
    validate_bytes(raw, manifest)
    # Exclusive creation refuses a concurrently created or preexisting destination.
    with path.open('xb') as destination:
        destination.write(raw)
    return path, 'downloaded and verified'
