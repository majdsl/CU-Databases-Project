# Reproduce the current reports

**Current entry point:** `scripts/check_reports.py --repeat` checks all **eight
reports / 55 derived outputs** in a temporary copy. It compares statistics, CSV
records and report text with the checked-in findings, validates image formats,
and checks repeatability in the same environment. It preserves the checkout,
raw measurements and historical source fingerprints; it runs no SQL or Docker.

The dependency installation and checksum-pinned dataset fetch below need internet
access on first use. After that, the report check is offline. Start from the
repository root. To produce new database measurements instead, follow the
[README quick start](../README.md#start-here).

The October validation counts and later generator additions are retained in the
[dated reporting history](report-reproducibility-history.md). They describe their
own revisions; use the commands below for today's reporting path.

## Reproduce on Windows PowerShell

Reporting requires **Python 3.10 or newer** for Matplotlib 3.10.8; Python 3.12 is the
tested reporting version. The Python 3.9+ minimum for the standard-library setup
wrapper and stock tutorial is separate from this optional reporting environment.

For a safe check of all eight reports, run these commands separately from the repository root:

```powershell
python -m venv .venv-report
.\.venv-report\Scripts\python.exe -m pip install -r requirements-report.txt
.\.venv-report\Scripts\python.exe scripts/fetch_openflights.py
.\.venv-report\Scripts\python.exe scripts/check_reports.py --repeat
```

The checker snapshots
the current source/evidence into a temporary directory, regenerates and validates
every report there, and leaves tracked reports and raw evidence in place. The check
runs without Docker and includes a second generation to detect nondeterministic output.
It uses current files, including uncommitted edits, and needs no Git history. It verifies
statistics, CSV values and report text against the checked-in results, validates image
formats, and requires identical outputs between repeated runs in the same environment.
Different plotting libraries/fonts can change graphics across environments; they are
not required to match committed image bytes. Success ends with `REPORT CHECK PASS`.

To intentionally refresh the tracked reports and figures instead, use the individual
commands below after setting up that same environment. Preserve your report edits first.
These scripts do not modify raw evidence or start Docker.

```powershell
.\.venv-report\Scripts\python.exe scripts/report_cpu.py
.\.venv-report\Scripts\python.exe scripts/report_storage_findings.py
.\.venv-report\Scripts\python.exe scripts/report_recovery_findings.py
.\.venv-report\Scripts\python.exe scripts/report_openflights_findings.py
.\.venv-report\Scripts\python.exe scripts/report_memory_findings.py
.\.venv-report\Scripts\python.exe scripts/report_cache_pressure_findings.py
.\.venv-report\Scripts\python.exe scripts/report_write_diagnostics_findings.py
.\.venv-report\Scripts\python.exe scripts/report_rocksdb_compression_findings.py
git diff --stat
```

## Reproduce on Linux or macOS

Use the same pinned reporting environment and safe checker:

```bash
python3 -m venv .venv-report
.venv-report/bin/python -m pip install -r requirements-report.txt
.venv-report/bin/python scripts/fetch_openflights.py
.venv-report/bin/python scripts/check_reports.py --repeat
```

For intentional regeneration, use `.venv-report/bin/python` with the individual
scripts listed above. Linux CI exercises this path; a native macOS walkthrough
remains pending. Successful regeneration does not establish cross-host timing results.

## Output and evidence boundaries

Matplotlib is a reporting dependency, separate from the database runner. Its direct version
is pinned; transitive packages and font/platform rendering are not completely locked.
Compare parsed statistics and CSV records before interpreting a graphics-only diff.
The generators validate their documented input scope; failures must be investigated rather
than resolved by editing raw measurements to fit expected results.

The write-diagnostics and cache-pressure reports validate their original host/worker
hashes against reviewed [write-diagnostics](../provenance/write-diagnostics/README.md)
and [cache-pressure](../provenance/cache-pressure/README.md) measured-source snapshots,
rather than assuming today's Dockerfile or orchestrator produced the archived experiment.
Their derived statistics identify measured source separately from the current report
generator. Historical measurements and their fingerprints remain unchanged. Both
generators accept `--output-root <dir>` for a separate derived `docs/` tree.

The compression report also uses three already archived files for the original
`benchmarks/openflights.py`, `benchmarks/run.py` and `benchmarks/recovery.py`.
Their bytes in the [write-diagnostics source snapshot](../provenance/write-diagnostics/README.md)
match every recorded fingerprint in both compression runs. The report pins each
LF-normalized SHA-256 before accepting the recorded LF/CRLF representation; a
missing or altered snapshot is rejected. This permits current SQL maintenance
without changing historical measurements, their hashes or the existing snapshot.

## Remaining boundaries

This check does not replace the teammates' independent setup, benchmark and evaluation
reviews. The [October 30 cloud reproduction](openflights-linux-reproduction.md) now validates
fresh setup/output writes on that Debian-userspace/nested-Docker executor. Ordinary native
Linux users should follow the [output-access prerequisite](setup.md#native-linux-output-prerequisite);
the container write probe remains authoritative. Independent physical-host walkthroughs
and unrecorded historical host/build details remain separate gaps.
No new claim about power loss, transaction rollback or larger-scale performance follows
from successful report regeneration.

The separately archived cloud pilot/full comparison has its own current portable guard:

```powershell
python scripts/check_cloud_openflights.py
python -O scripts/check_cloud_openflights.py
```

The guard uses the pinned dataset and preserves archived bytes. It validates all four
laptop/cloud runs, full-run comparisons, measured-source fingerprints and archive checksums.
It is also run in offline CI. The original archived validator remains unchanged; the
current entry point handles Windows/POSIX checksum paths and creates no files in the archive.

