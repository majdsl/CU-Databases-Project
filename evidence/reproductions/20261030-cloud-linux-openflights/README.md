# Managed cloud Linux OpenFlights reproduction — October 30, 2026

Tested `main`: `5afc5f03f697c3ad1ed92feafade0d49e3261cd0`.
Setup, pilot (5 trials) and full (25 trials) passed on managed cloud Linux amd64.
The executor has Debian 13 userspace/nested Docker; the DB image is Ubuntu-based.
This is separate from the original Windows/WSL2 laptop results and Zane's pending
independent physical-laptop package.

Read the [full comparison and limitations](../../../docs/openflights-linux-reproduction.md).

- [Pilot raw data and summary](../../openflights/20261030T184911Z-openflights-329f0869/).
- [Full raw data and summary](../../openflights/20261030T184936Z-openflights-85032cd6/).
- `metadata.json`, `commands.json`: source revision, scope, controls and executed steps.
- `runtime-provenance.json`, `db-controls.txt`, `db-packages.txt`: image/runtime/package evidence.
- `post-run-host.json`: explicitly later, read-only machine snapshot.
- `build/`: exact external adapters; no environment settings were changed or republished.
- `measured-source/`: all 32 cloud fingerprinted files from the tested commit, preserving
  historical source independently of later checkout changes.
- `logs/`: setup, pilot/full and database transcripts. Unit-test fixture failures in
  setup output are expected test cases; the actual suite ended with 140 tests / OK.
- `comparison.json`, `comparison.csv`: full-run means, sample SD and cloud/laptop
  percentage differences; pilots are validated but excluded from comparison statistics.
- `validate.py`: explicit validation, safe with normal/optimized Python; no Docker needed.
- `validation.json`, `preservation.json`, `sha256.json`: archive validation and input preservation.

From the repository root, fetch the checksum-pinned OpenFlights data if needed, then run:

```bash
python3 scripts/fetch_openflights.py
python3 evidence/reproductions/20261030-cloud-linux-openflights/validate.py
python3 -O evidence/reproductions/20261030-cloud-linux-openflights/validate.py
```

`sha256.json` paths are relative to the repository root and cover this record and the
two new raw-result folders; the checksum file excludes itself. Local `.gitattributes` files preserve archived
bytes across Windows/Linux checkout line-ending settings. Raw results/summaries
are unmodified copies. No credentials, `.env`, registry auth, CA contents or full
container environment are included. Existing evidence and both database volumes
were preserved. The new database is stopped cleanly with its volume retained.
