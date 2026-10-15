"""Fetch exactly the reviewed OpenFlights route snapshot; Python standard library only."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.openflights_data import fetch_dataset

if __name__ == '__main__':
    try:
        path, status = fetch_dataset()
        print(f'OpenFlights: {status}: {path}')
    except Exception as error:
        print('FAILED:', str(error), file=sys.stderr)
        sys.exit(1)
