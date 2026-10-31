# Stock-MariaDB tutorial: platform validation

**Validated October 27, 2026:** the four-engine stock-image tutorial passed on
native Linux amd64 and ARM64 GitHub runners, and from Windows PowerShell with
Docker Desktop's WSL2 Linux amd64 engine. It uses the official MariaDB 11.8.9
image, independently of the custom MyRocks lab build.

| Platform | Host machine | Server version | Result |
| --- | --- | --- | --- |
| Linux amd64 | `x86_64` | `11.8.9-MariaDB-ubu2404` | All checks passed; owned container/volume removed |
| Linux ARM64 | `aarch64` | `11.8.9-MariaDB-ubu2404` | All checks passed; owned container/volume removed |
| Windows PowerShell / Docker Desktop WSL2 | `AMD64` host; Linux amd64 engine | `11.8.9-MariaDB-ubu2404` | All checks passed; owned container/volume removed |

The [archived commands, validation JSON and transcripts](../evidence/reviews/20261027-stock-tutorial-ci/README.md)
come from [PR run 40421200797](https://github.com/majdsl/CU-Databases-Project/actions/runs/40421200797),
source head `ed7ee7a1f754e085f33d4327a2cd3c1f73741bd6`, tested merge revision
`9d8509de9edd8daa76bba80aed34a642c6250260`. Both jobs verified native host/Docker/image
architecture agreement. The workflow continues checking both platforms on pushes,
pull requests and manual dispatch.

These October 27 records cover the six common SQL files present at those revisions.
The current reproduction command below uses seven common files, including the later
transaction demonstration (`05b-transactions.sql`). The historical records do not
claim to validate SQL added after their tested revisions; current CI runs the
expanded sequence.

The [Windows archive](../evidence/reviews/20261027-windows-stock-tutorial/README.md)
comes from the owner's existing checkout at recorded commit
`e6767a5c14c862d686bcd9adda0945103db2d556`, using Python 3.10.11 and Docker 29.8.0.
All 119 command records, validation JSON and the saved transcript agree. The nine
recorded source hashes match that commit with Windows CRLF line endings; provenance
preserves both source hash forms and records original/published file hashes.
The public command/transcript copies mask the Windows username and absolute project
path; observations and validation are unchanged. The commit was recorded after
the run; the original local validation's `commit` field remains null.

## Reproduce from a clean checkout

Requirements: this repository, Python 3.9+, Docker CLI and a running Linux Docker
engine. No Compose build, plotting packages, downloaded dataset or existing `.env`
is needed. From the repository root:

```powershell
python scripts/check_stock_tutorial.py
```

On Linux use `python3`. The script uses an unused random project name, creates its
own credentials in memory and starts a fresh database. Success ends with
`STOCK TUTORIAL PASS: amd64` or `STOCK TUTORIAL PASS: arm64` and the saved output path.
Inspect `validation.json`, `commands.json` and `transcript.txt` in that directory.
For a manual record, preserve `git rev-parse HEAD` alongside the source hashes;
the `commit` field is supplied automatically in GitHub Actions.

## What the check establishes

- The pinned official image starts from a new named volume and reaches a healthy state.
- The seven current common SQL files mounted read-only match the checkout's SHA-256 hashes.
- InnoDB, Aria, MyISAM and MEMORY are the actual table engines, with 50,000 rows each.
  Row checks compare IDs, generated fields and notes with their deterministic formulas.
- Both MEMORY index variants hold 100,000 rows. Equality returns 20 rows and range
  returns 200; plans show `ref` for equality, BTREE `range` and HASH `ALL` for ranges.
- Six invalid procedure calls fail. Single and two-writer update totals match
  the affected rows, including disjoint and same-row cases.
- A two-row transfer rolls back on InnoDB and remains applied on the three
  non-transactional engines, with exact balances checked.
- A clean restart preserves the persistent engines' rows and updates; MEMORY empties.
- SQL cleanup removes tutorial objects and preserves an unrelated sentinel.
- The script removes only the container and volume with this invocation's ownership
  labels, after checking their identities. Existing names are refused before creation.

Five offline failure-path tests additionally cover resource collisions, foreign
ownership, architecture mismatch, invalid project names and credential-safe logs.
They form part of the complete offline suite, which CI runs normally and with
optimized Python (`-O`). See [CI scope](ci.md) for the current checks and dated
validation records.

## Image and scope

Both jobs selected the same official multi-platform index:

```text
mariadb@sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112
```

The Linux CI amd64 image ID was `sha256:cc7f5fdd7c8fff6867e8ac4df3e7e0faf6c56aebe621a13565479a9a94e4bf13`;
the ARM64 ID was `sha256:3853ff4da2eb76058a3a112ae8026e5a094990c5341f1aedd76a903fd171176e`.
Different platform images are expected under one index. The full selected metadata
and common SQL hashes are preserved in each platform's JSON record, including the
metadata returned by Docker Desktop in the Windows run.

The database runs with a two-CPU/1-GiB cap and no network or published port. This
is a repeatable correctness demonstration. Its one-second writer calls and timings
are not a comparison of CPU architectures, an engine ranking or a second-laptop
performance replication. The Windows record validates the Python CLI with Docker
Desktop's Linux containers in an existing checkout. Interactive SQL walkthroughs,
fresh Windows setup-wrapper installation and macOS remain separate from this check.
The custom five-engine build remains verified only on amd64; Path B deliberately uses four engines.

References: [GitHub standard runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[MariaDB image healthcheck](https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/using-healthcheck-sh),
[hands-on tutorial](tutorial.md).
