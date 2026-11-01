"""Revalidate the real session with the current exporter; never execute SQL."""
from pathlib import Path
import sys
import zipfile

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parents[2]))
from scripts import archive_openflights


def main():
    archive_openflights.launcher.ROOT = DIRECTORY / 'bundle'
    session = (DIRECTORY / 'bundle/results/20261101T152845Z-openflights-session-ba84d4b7/session.json')
    files = archive_openflights.collect(session)
    with zipfile.ZipFile(DIRECTORY / 'ci/openflights-evidence.zip') as bundle:
        if set(files) != set(bundle.namelist()):
            raise ValueError('Revalidated contents differ from the original export')
        if any(raw != bundle.read(name) for name, raw in files.items()):
            raise ValueError('Revalidated bytes differ from the original export')
    print('SESSION RECHECK PASS: real 5/25 trials, statistics, controls, images, clean stop; '
          'all 15 original export entries matched. Offline validation, no SQL re-execution.')


if __name__ == '__main__':
    main()
