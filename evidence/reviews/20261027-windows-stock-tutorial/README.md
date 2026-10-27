# Windows stock-tutorial validation — October 27, 2026

Majd Salimoun ran `python scripts/check_stock_tutorial.py` from Windows PowerShell
in the existing project checkout. Python 3.10.11 used Docker Desktop's WSL2 Linux
amd64 engine (Docker 29.8.0) and the pinned official MariaDB 11.8.9 image. The run
ended with **`STOCK TUTORIAL PASS: amd64`** and removed its own container and volume.

This is a Windows CLI and Docker Desktop correctness record for the four-engine
automated Path B. It adds to the [native Linux amd64/ARM64 CI records](../20261027-stock-tutorial-ci/README.md).
It does not establish an interactive SQL walkthrough, a fresh Windows setup-wrapper
installation, a second-machine benchmark or a cross-platform performance ranking.

## Files and provenance

The owner supplied `stock-tutorial-windows.zip`, containing the saved directory
`20261027T145000Z-cu-stock-66441a85eb19`. With the owner's approval, the absolute
Windows project mount path is replaced by `<PROJECT_DIR>/sql/tutorial` in the
published command and transcript copies. This hides the Windows username and
local folder location. Test observations, SQL and source fingerprints are retained;
`validation.json` and `source-commit.txt` are unchanged. Windows CRLF line endings
are preserved in all four files.

- [validation.json](validation.json): host, Docker, image, source and SQL identities;
  observed query plans, update counts, restart and cleanup outcomes.
- [commands.json](commands.json): all 119 Docker command records, including SQL
  input and outputs; the absolute host mount path is masked and private inspection
  output was omitted by the runner. The path placeholder is descriptive, not a
  literal command to paste into a terminal.
- [transcript.txt](transcript.txt): the runner's saved log, embedded validation JSON
  and final PASS line. This is the generated log, not a complete interactive terminal capture.
- [source-commit.txt](source-commit.txt): `e6767a5c14c862d686bcd9adda0945103db2d556`,
  captured by the owner with `git rev-parse HEAD` after the successful run.

[provenance.json](provenance.json) records the uploaded ZIP hash, each original
member name, original and published file sizes/SHA-256 hashes, the two path
replacements, and the source-identity comparison. The archive's
[Git attributes](.gitattributes) preserve the published files without newline conversion.
The original ZIP and unredacted command/transcript copies are excluded from
publication. No generated credentials or raw Docker inspection payloads are included.

The original `validation.json` has `commit: null`: only GitHub Actions supplies that
field automatically. The later commit record is kept separately. All nine recorded
file hashes (two Python scripts, the workflow and six SQL files) exactly match that
commit after converting its LF source files to Windows CRLF. Git blob and both
SHA-256 forms are recorded. Source fingerprints, query outputs and validation
observations are unchanged; the only command/transcript edits mask the host path.
No working-tree status was supplied, so this comparison applies to the nine hashed
files rather than asserting that the entire checkout was clean.

## Checks reviewed

The command list and transcript agree, and their embedded validation matches the
standalone JSON. All 119 record numbers are present. Six nonzero command exits are
the deliberately rejected invalid routine inputs (`SQLSTATE 45000`); no unexpected
command failure is present.

The run verifies four actual engines with 50,000 deterministic rows each, two
100,000-row MEMORY index variants, equality/range answers and plans, invalid inputs,
single/concurrent update totals, persistent rows after a clean restart, empty MEMORY
rows, and SQL cleanup preserving an unrelated sentinel. Both owned-resource removal
flags are true. Short writer durations, lock counters and command elapsed times
are correctness observations; they do not extend the repeated benchmark findings.

Reproduction and scope: [platform validation guide](../../../docs/stock-tutorial-validation.md).
