"""Verify every file and checksum in an OpenFlights evidence export."""
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile


def safe(name):
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and str(p) == name


def verify(target):
    if target.is_file():
        with zipfile.ZipFile(target) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or any(not safe(n) for n in names):
                raise ValueError('Unsafe or duplicate ZIP entries')
            if any(stat.S_ISLNK(info.external_attr >> 16) for info in z.infolist()):
                raise ValueError('Symlink ZIP entry')
            data = {name: z.read(name) for name in names}
    else:
        data = {}
        for path in target.rglob('*'):
            if path.is_symlink():
                raise ValueError('Symlink in extracted bundle')
            if path.is_file():
                name = path.relative_to(target).as_posix()
                if not safe(name):
                    raise ValueError('Unsafe bundle path')
                data[name] = path.read_bytes()
    entries = {}
    for line in data['SHA256SUMS.txt'].decode('utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch('[0-9a-f]{64}', digest) or not safe(name) or name in entries:
            raise ValueError('Invalid checksum entry')
        entries[name] = digest
    if not entries or set(entries) != set(data) - {'SHA256SUMS.txt'}:
        raise ValueError('Checksum coverage differs from bundle contents')
    for name, digest in entries.items():
        if hashlib.sha256(data[name]).hexdigest() != digest:
            raise ValueError('Checksum mismatch: ' + name)
    print('BUNDLE CHECKSUMS PASS: ' + str(len(entries)) + ' files; integrity only, not authenticity or SQL re-execution.')


if __name__ == '__main__':
    try:
        if len(sys.argv) > 2:
            raise ValueError('Usage: python verify.py [archive.zip or extracted-directory]')
        verify(Path(sys.argv[1]).absolute() if len(sys.argv) == 2 else Path(__file__).resolve().parent)
    except Exception as error:
        print('FAILED: ' + str(error), file=sys.stderr)
        sys.exit(1)
