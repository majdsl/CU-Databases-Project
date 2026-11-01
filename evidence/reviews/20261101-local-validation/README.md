# Local validation — November 1, 2026

Source at start: `d75c4b7271d9f5877ddb2a37b5f1a2a75febc5e6`. Current working files were tested while documentation and workflow changes were developed separately. No Docker build or database measurement was attempted here. The source advanced to `2da20124ca1e52128d7cb8c3536736ae139239f7` during validation through documentation/workflow commits; the computational inputs were unchanged from the starting revision.

Python 3.12.14; PyMySQL 1.1.2; Matplotlib 3.10.8. Existing OpenFlights download was checked by `scripts/fetch_openflights.py` and verified.

- `.venv/bin/python -m unittest discover -s tests -v`: PASS (146 tests); 1.213 s; log `unit-normal.log`.
- `.venv/bin/python -O -m unittest discover -s tests -v`: PASS (146 tests); 1.824 s; log `unit-optimized.log`.
- `.venv/bin/python -m unittest discover -s report-tests -v`: PASS (102 tests); 187.657 s; log `offline-normal.log`.
- `.venv/bin/python -O -m unittest discover -s report-tests -v`: PASS (102 tests); 191.279 s; log `offline-optimized.log`.
- `.venv/bin/python scripts/check_reports.py --repeat`: PASS; 143.378 s; log `reports-repeat.log`.
- `.venv/bin/python scripts/check_cloud_openflights.py`: PASS; 1.921 s; log `cloud-normal.log`.
- `.venv/bin/python -O scripts/check_cloud_openflights.py`: PASS; 2.49 s; log `cloud-optimized.log`.
- `.venv/bin/python evidence/reviews/20261031-build-evidence/verify.py`: PASS; 0.034 s; log `sealed-build.log`.
- `.venv/bin/python evidence/reviews/20261031-final-guards/verify.py`: PASS; 0.061 s; log `sealed-guards.log`.

All nine validation commands exited zero. No historical evidence or derived tracked reports were changed by this validation. Offline/report checks regenerate in temporary copies; results are validation of existing archived evidence, not independent database timings.
