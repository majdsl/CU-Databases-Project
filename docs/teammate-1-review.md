# Hassan Kheder: reproduction, testing, debugging and graph revision

**Contributor:** [Hassan Kheder (Hassan457-123)](https://github.com/Hassan457-123), teammate 1.
Review date: October 24, 2026. Source reviewed: `cfd9f26` on main.
The team supplied this work as an AI-assisted contribution. It records archived-report
reproduction, code debugging and test/figure review, rather than a fresh database benchmark.

| Task | Completed work |
| --- | --- |
| Reproduction | Ran all seven report generators against archived evidence using Python 3.12.14 and Matplotlib 3.10.8. Downloaded the pinned OpenFlights snapshot with the project's checksum-verifying fetcher. Repeated generation; numerical reports were unchanged. |
| Testing | Original 115 tests passed. Added one test with six corrupted-evidence cases; all 116 tests passed with both normal Python and `python -O`. SHA-256 checks confirmed all 714 archived evidence files remained unchanged. |
| Debugging | Replaced storage-report `assert` checks with explicit `ValueError` failures. Optimized Python previously removed row-count, checksum, clean-shutdown, inventory and delta validation. Invalid inputs now fail before report output is created. |
| Graph revision | Clarified the MEMORY allocation legend as “Row data (Data_length)” and “Indexes (Index_length)”; regenerated PNG/SVG and generator provenance. Visually checked the revised graph, OpenFlights warm reads and write-diagnostic CPU panels for readable labels and layout. Measurements and conclusions did not change. |

## Reproduce these checks

Run from the repository root with the documented dependencies installed:

```sh
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
python -m unittest discover -s report-tests -v
python -O -m unittest discover -s report-tests -v
python scripts/fetch_openflights.py
python scripts/report_cpu.py
python scripts/report_storage_findings.py
python scripts/report_recovery_findings.py
python scripts/report_openflights_findings.py
python scripts/report_memory_findings.py
python scripts/report_cache_pressure_findings.py
python scripts/report_write_diagnostics_findings.py
```

Storage and recovery CSV regeneration produces newline-only checkout differences;
compare parsed records or normalize CRLF/LF before treating these as data changes.
Those incidental CSV differences are excluded from this contribution.

Docker is unavailable in this review environment. Fresh MariaDB setup, five-engine
integration, Windows reproduction and new timing/crash experiments were **not run**.
Archived-report reproduction does not establish independent-machine performance,
power-loss durability or transaction equivalence. These checks do not confirm the
team roster or replace the remaining tasks in the [evidence plan](evidence-plan.md).

## Integration review

The submitted seven-file patch and both unit-test logs were reviewed against main.
The patch applied cleanly. A maintainer independently reran all seven report generators,
verified the storage numerical results were unchanged, and passed the submitted
116-test suite in normal and optimized Python. All 714 archived evidence files
retained their bytes. The revised allocation graph was visually inspected.

The submitted report test needs the full checkout, archived storage evidence and
Matplotlib, which are intentionally excluded from the database runner. It was moved
unchanged to `report-tests/test_storage_findings.py`; its six invalid-evidence cases
now run in a dedicated CI job with reporting dependencies, normally and with `-O`.
The lightweight Docker suite remains 115 tests; the offline report suite adds one
test with six subcases. No reporting files, plotting packages or raw benchmark
archives were added to the database image.

[Submitted test logs and archive provenance](../evidence/reviews/20261024-hassan/README.md)
preserve the reviewed evidence. The original patch author field was `Codex`; this
review records Hassan's contribution as confirmed by the project owner, without
claiming that the original commit was authored through his GitHub account. Full-team
contribution documentation and reevaluation remain pending the other teammate's work.
