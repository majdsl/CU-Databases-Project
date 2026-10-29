# Reproducibility and tutorial maintenance validation

Validated locally on October 29, 2026 against the working changes based on
`f90e813d4ce8fc2de76c611a98986f29820a9325`. This is a development check, not a new
controlled benchmark or a claim that GitHub Actions has run the changed revision.

## What changed and why

- The write-diagnostics report now verifies the actual measured source snapshot
  rather than comparing historical fingerprints with today's Dockerfile. The
  [snapshot manifest](../provenance/write-diagnostics/manifest.json) is pinned and
  tamper-checked; original measurement hashes are retained. Current generator
  provenance is a separate field in derived statistics.
- `scripts/check_reports.py --repeat` runs every report twice in a temporary copy of
  current files. It checks numerical data, report text, valid images, deterministic
  repeated outputs and preservation of source/evidence inputs. It handles Windows
  output separators and excludes local credentials, results and Git metadata.
- New local credential files are created with POSIX mode `0600` before secret bytes
  are written, while existing files and symlinks are preserved. Windows directory
  ACL requirements are documented separately.
- Each tutorial concurrency case now records validated counter baselines/deltas
  and server-side procedure intervals. No particular wait count or overlap is
  required. Procedure overlap is distinct from simultaneous statement-level locks.
- The [transaction lesson](tutorial.md#5c-commit-and-rollback-depend-on-the-engine)
  runs identical two-row transfers with exact rollback/commit checks across all five
  engines, independently of the archived autocommit timing experiments.

## Checks and results

Host: native Linux amd64, Python 3.12.14, Docker 28.4.0 and MariaDB
11.8.9-MariaDB-ubu2404. Reporting used Matplotlib 3.10.8 and the existing pinned
OpenFlights snapshot. The Python reporting minimum is now stated separately as 3.10.

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 132 passed |
| Same lightweight suite with `-O` | 132 passed |
| `python -m unittest discover -s report-tests -v` | 40 passed |
| Same offline suite with `-O` | 40 passed |
| All-eight-report regression inside each offline run | 55 derived outputs, two generations each, preserved inputs |
| Native-amd64 stock tutorial | Four engines; SQL, indexes, concurrent totals, per-case observations, transactions, clean restart and owned cleanup passed |
| Disposable five-engine tutorial | Five-engine sequence followed by common four-engine sequence; SQL and cleanup passed |
| Historical archive preservation | All 824 pre-existing evidence files retained their SHA-256 |
| Write-report measurement preservation | All old statistics/provenance fields and all six charts unchanged; two separately named provenance fields added |

The offline suite includes historical-source tampering, changed/missing recorded
fingerprints, source archives without Git, LF/CRLF conversion, corrupted measurements,
private creation under permissive umasks, preservation of existing files/symlinks,
missing/reset counters, inconsistent SQL timestamps, changed transaction outcomes,
and Windows/POSIX report-path normalization. These checks exercise failures rather
than merely requiring that a process exits successfully.

The stock driver saves source/SQL hashes and guarded resource identities; the lab
driver prints its source hashes and exact assertions between the existing JSON
markers. Both include the new transaction-check helper in their source records.
Only resources created for these disposable checks were removed; the normal lab
database and credentials were preserved.

## Reproduce the relevant checks

Use Python 3.10+ with `requirements-report.txt` installed in an isolated environment,
plus `requirements.txt` for host-side lightweight tests. From the repository root:

```bash
python scripts/fetch_openflights.py
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
python -m unittest discover -s report-tests -v
python -O -m unittest discover -s report-tests -v
python scripts/check_stock_tutorial.py
```

The complete report test already invokes repeated safe report regeneration; a
separate `python scripts/check_reports.py --repeat` is useful when only reporting
changed. On Linux, use `python3` or the isolated environment's Python executable.
The five-engine tutorial driver is restricted to disposable `cu-ci-<run>-<attempt>`
projects as described in [CI](ci.md); it must not restart an ordinary lab database.

The managed cloud builds used a local override outside the checkout to mount its
proxy CA as a BuildKit secret and make copied files readable in the image. Those
environment-specific adaptations did not modify the repository Dockerfiles or
disable TLS, checksum or package-signature verification.

## Interpretation boundaries

These checks validate reproduction and deterministic SQL behavior. They do not
replace the controlled laptop measurements, independently reproduce their timings,
test power loss, or add steady-state compaction/cold-cache results. Historical
pilot/full image differences remain documented in [image provenance](image-provenance.md).
Native Windows/ARM64 execution of these new changes was not performed here; Windows
path behavior is covered by an offline regression, and the existing CI matrix will
exercise supported platforms when the changes are submitted.
