# Offline report reproducibility — October 15, 2026

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

From the repository root, run each command separately. Use a clean checkout or preserve
your report edits first: these scripts regenerate tracked derived reports and figures.
They do not modify the raw evidence or start Docker.

```powershell
python -m venv .venv-report
.\.venv-report\Scripts\python.exe -m pip install -r requirements-report.txt
.\.venv-report\Scripts\python.exe scripts/fetch_openflights.py
.\.venv-report\Scripts\python.exe scripts/report_cpu.py
.\.venv-report\Scripts\python.exe scripts/report_storage_findings.py
.\.venv-report\Scripts\python.exe scripts/report_recovery_findings.py
.\.venv-report\Scripts\python.exe scripts/report_openflights_findings.py
.\.venv-report\Scripts\python.exe scripts/report_memory_findings.py
git diff --stat
```

On Linux use `python3` to create the environment and `.venv-report/bin/python` thereafter.
Matplotlib is a reporting dependency, separate from the database runner. Its direct version
is pinned; transitive packages and font/platform rendering are not completely locked.
Compare parsed statistics and CSV records before interpreting a graphics-only diff.
The generators validate their documented input scope; failures must be investigated rather
than resolved by editing raw measurements to fit expected results.

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
