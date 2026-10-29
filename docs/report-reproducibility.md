# Offline report reproducibility — October 15, 2026

For the October 24 reproduction, optimized-Python validation fix and graph revision,
see the [teammate 1 review](teammate-1-review.md).

All four report generators were run from a fresh source archive of main commit
`31369d7e2c6d4279354b44775313e37f93761a5c`, using Python 3.12 and Matplotlib 3.10.8.
The pinned OpenFlights dataset was downloaded and checksum-verified again.
No database experiments were rerun. This verifies reporting from archived evidence,
not independent reproduction of benchmark timings on another machine.

## Results and fixes

| Report | Verification |
| --- | --- |
| CPU | Four archived summaries matched; all 120 condition summaries and both SVG plots regenerated |
| Storage | All 25 full-run trials validated; all numerical statistics matched; two PNG and two SVG plots regenerated |
| Recovery | 60 pilot/full trials and 60 original restart-log checksums validated; the report uses only 50 full-run trials |
| OpenFlights | 30 pilot/full trials validated; the report uses only 25 full-run trials; all derived statistics matched |
| Synthetic baseline | Current formatter reproduced the archived baseline summary |

All 14 chart files regenerated. All six PNGs matched their committed bytes exactly.
Recovery and OpenFlights derived JSON matched; CSV contents matched after normalizing
line endings. The 82-unit-test suite passed locally. Every one of the 148 archived
evidence files retained its original bytes throughout the check.

Two reporting details needed correction:

- Storage provenance hashed raw JSON bytes. Its old hash was confirmed to match the
  CRLF version of the source, while a Linux checkout produced a different hash of the
  same parsed measurements. CPU provenance also depended on raw line endings.
  Both generators now identify results using sorted compact JSON. The storage generator
  records its own source hash after normalizing line endings to LF. Field names explicitly
  distinguish these hashes from raw-byte hashes. Historical benchmark metadata is untouched.
- Storage SVGs embedded timestamps and randomized element IDs. Their timestamps are now
  omitted and their ID salt is fixed. All seven storage outputs matched byte-for-byte
  between LF and CRLF result/generator inputs after the change. The four CPU outputs
  also matched across LF/CRLF result inputs. Original storage statistics and all 120 CPU
  summaries were compared before/after and remained identical.

Only derived provenance and storage SVG metadata/IDs were refreshed. The plots' numerical
content did not change. Recovery restart-log checksums still hash exact original bytes;
their existing `.gitattributes` rule is preserved. Different plotting libraries, fonts
or platforms can still change rendering; identical images are not promised universally.

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

On Linux use `python3` to create the environment and `.venv-report/bin/python` thereafter.
Matplotlib is a reporting dependency, separate from the database runner. Its direct version
is pinned; transitive packages and font/platform rendering are not completely locked.
Compare parsed statistics and CSV records before interpreting a graphics-only diff.
The generators validate their documented input scope; failures must be investigated rather
than resolved by editing raw measurements to fit expected results.

The write-diagnostics report validates its original host/worker hashes against the
reviewed [measured-source snapshot](../provenance/write-diagnostics/README.md), rather
than assuming today's Dockerfile is the one used for the archived experiment.
The derived statistics identify that measured source separately from the current
report generator. Historical measurements and their fingerprints remain unchanged.

## Remaining boundaries

This check does not replace the teammates' independent setup, benchmark and evaluation
reviews. Native Linux bind-mount write permissions for benchmark output and the remaining
host/build details listed in the [tutorial audit](tutorial-audit.md) still need validation.
No new claim about power loss, transaction rollback or larger-scale performance follows
from successful report regeneration.

## MEMORY report follow-up — October 16, 2026

The fifth generator, `scripts/report_memory_findings.py`, validates the four-trial
pilot and 24-trial full run archived in `7246f7e`. It verifies original summaries,
all trial statistics, datasets, query streams/answers, actual indexes/DDL and
recorded plans/handler deltas. Only the full run contributes to the report and charts.
The outputs are 72 CSV observations, JSON statistics/provenance, a findings report
and two charts in PNG and SVG (four files). Matplotlib 3.10.8 is used.
Canonical evidence hashes ignore line endings; historical raw evidence is untouched.

Validation for this addition: all seven generated files reproduced byte-for-byte
on a second run. All 152 archived evidence files retained their bytes. The 94-unit-test
suite passed locally. Deliberately incomplete runs, changed plans, changed counters
and missing diagnostics were rejected by the report validator. Both charts were
visually inspected. These checks validate the report, not new performance observations.

## Cache-pressure report follow-up — October 17, 2026

The sixth generator, `scripts/report_cache_pressure_findings.py`, validates two
pilot and 12 full trials archived in `d662bb6`, including all 14 worker files,
regenerated SHA-256/CRC oracles, schedules, query streams, clean stops, footprints,
counter deltas, original summaries and statistics. Only full observations enter
the charts. Outputs are 24 CSV trial/phase observations, provenance/statistics JSON,
a findings report and two charts in PNG/SVG. Pilot and full image identities differ
and are retained separately; no byte-identical cross-run image claim is made.

Validation: two consecutive regeneration runs produced matching bytes for all seven
derived files; all 170 archived evidence files remained unchanged. The 106-unit-test
suite passed locally. Deliberately incomplete runs, altered counter deltas, mismatched
footprint metadata and changed source hashes were rejected. Both figures were
visually inspected. Rendering remains dependent on plotting libraries and fonts.

## Write-diagnostics report follow-up — October 18, 2026

The seventh generator, `scripts/report_write_diagnostics_findings.py`, validates
30 pilot and 150 full trials archived in `b5eefc3`, including all 540 raw stage
files. It regenerates row hashes, checks worker counts, schedules, runner/DB CPU
arithmetic, SQL deltas, source/settings metadata, original summaries and clean
stops. Only the full run enters the 150-row CSV and 30 condition summaries.
Three figures in PNG/SVG cover throughput, CPU windows and table-lock waits.
Pilot/full image identities differ and remain separately recorded.

```powershell
python -m pip install -r requirements-report.txt
python scripts/report_write_diagnostics_findings.py
```

Two consecutive generations matched all nine derived files byte-for-byte; all
714 archived evidence files retained their original bytes. The 544 write-diagnostic
files in the GitHub source snapshot matched the team's reviewed ZIP uploads after
JSON parsing/newline normalization. Incomplete runs, altered CPU arithmetic, wrong
update counts, changed final hashes and incorrect source identities were rejected.
All 115 unit tests passed locally, the new local documentation links resolved, and
all three figures were visually inspected. This validates reporting, not new
measurements or independent-machine performance reproduction.

## MyRocks compression report — October 28, 2026

The eighth generator, `scripts/report_rocksdb_compression_findings.py`, validates
the four-trial pilot and 32-trial full run archived in `7dd87e4`. It regenerates the
SHA-256/CRC32 oracles and verifies all raw worker/inventory files, exact query streams,
CF/SST codecs and controls, source hashes, command-log checksums/lifecycle, clean
stops, owned cleanup, original summaries and statistics. All 76 archived JSON files
matched the reviewed upload bytes; their local `-text` rule preserves the command
hashes. Pilot and full image IDs differ and are retained separately; images are
fixed within each run and pilot data are excluded from all full statistics.

The seven outputs are a 32-row observation CSV, statistics/provenance JSON,
findings and two charts in PNG/SVG. Full statistics use eight trial observations
per condition, averaging read samples within each trial first. Paired descriptive
codec ratios are retained by round. Source hashes accept LF or CRLF source files;
raw JSON hashes, canonical-JSON hashes and normalized-summary hashes are explicit.
The validator allows only `1e-12` relative/absolute floating-point roundoff, including
a roughly `1.1e-16` SD difference between the measured host and reporting Python.
It does not edit the archived statistics to force byte equality.

All 823 pre-existing evidence files retained their Git blob hashes throughout this
addition. The 79-file raw compression archive remains unchanged; an index README
is added beside it. Team contribution sections are also preserved exactly.

Six new offline tests cover wrong settings/runtime/source, incomplete runs, corrupt
raw files, altered command bytes/network namespace and changed statistics. They
also generate the report twice, require all seven output files to match, and
check that the evidence retains its bytes. The complete 13-test offline suite
runs normally and under `-O` through the existing CI discovery command. Both figures
were visually inspected with Matplotlib 3.10.8. This verifies the reporting path,
not an additional database run or second-host performance reproduction.
