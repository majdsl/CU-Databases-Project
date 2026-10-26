# Correctness CI

**Setup-wrapper validation, October 15, 2026:** [run 38824387276](https://github.com/majdsl/CU-Databases-Project/actions/runs/38824387276)
passed on `ead6f10b1d9ac486898d112d0569926fcf20375a`. The fresh Ubuntu job
ran the documented wrapper, verified writable output, passed all 85 unit tests,
built MariaDB and passed all five engine checks, ending with `SETUP PASS`.
This validates the Linux CI path; independent Windows reproduction remains pending.

The [Correctness workflow](../.github/workflows/correctness.yml) runs on pushes,
pull requests and manual dispatch. **Validated on October 9, 2026:** both push and pull-request runs passed for
branch head `f77f8f5a86ed353aa9d06760688a8c03b4a85339`.
The pull-request event checks GitHub's merge revision; the push checks the branch revision.

- [Push run 37999991984](https://github.com/majdsl/CU-Databases-Project/actions/runs/37999991984)
- [Pull-request run 37999992942](https://github.com/majdsl/CU-Databases-Project/actions/runs/37999992942)

Fresh runner/database builds, all 82 unit tests, healthcheck and all five real engine
round trips passed. The integration server reported MariaDB 11.8.9-MariaDB-ubu2404.
A short [log excerpt](../evidence/environment/20261009-ci-validation.txt) preserves the
unit-test conclusion and engine output; full build logs remain linked in Actions.

Each job starts from a fresh checkout on Ubuntu 24.04. It prepares a disposable
results directory for UID 10001 and runs the README setup wrapper,
`scripts/setup_project.py`, with a unique CI project name. The wrapper:

1. Generates disposable local credentials without printing their values.
2. Downloads the pinned OpenFlights snapshot and verifies its checksum.
3. Builds the pinned Python runner and checks results-mount write access and runs the complete unit suite (currently 115 tests).
4. Builds the custom MariaDB image, including the pinned MyRocks plugin package.
5. Starts a fresh database volume and waits for its healthcheck.
6. Checks all five actual storage engines and verifies parameterized inserts/readback.

The integration check uses the existing `scripts/check_environment.py`: it checks
MariaDB identity, engine availability, actual table engine and exact contents of three
probe rows per engine, including an apostrophe-containing value. A successful check
prints five engine PASS lines and one overall PASS. Unit tests also exercise reporting,
isolation and failure handling with fixtures; they are not new benchmark observations.

## Scope and operation

The workflow also runs a tiny MEMORY HASH/BTREE correctness smoke against the real
server. Its output includes timings, but these are not performance evidence.
The workflow does not run full timing benchmarks or crash experiments. Shared CI host
performance cannot replace the controlled laptop measurements. Passing CI establishes
fresh Linux build/setup and correctness checks for that revision; it does not establish
a Windows tutorial reproduction, power-loss durability or engine recommendations.

Open the repository's **Actions → Correctness** page, select the run and inspect
**Unit tests and five-engine integration**. Check the tested commit, all steps and
the final conclusion. A workflow file alone is not evidence of a passing run.
Fork pull requests can require a maintainer's approval before GitHub runs them.

The token has read-only contents permission. Checkout is pinned to the verified
actions/checkout v7.0.1 commit and does not persist credentials. No repository secrets
are required. Normal `pull_request` events are used; there is no privileged
`pull_request_target` execution. Database logs are printed on failure; credentials
and resolved Compose configuration are not deliberately printed.

Every Compose command selects a project named from the numeric run and attempt IDs.
Cleanup removes only that disposable CI project's containers and volumes, even after
failure. **Do not copy the CI volume-removal command into normal laptop operation**:
use `docker compose stop` there to preserve data.

External registry/package/download outages can fail a fresh build. The database's
transitive packages and the GitHub-hosted runner image are not fully locked; a green
run is not a byte-for-byte reproducibility guarantee. No cached database volume is reused.

References: [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1).

The cache-pressure extension also runs its host orchestrator in smoke mode against
two fresh isolated databases. CI gives its disposable results parent back to the
host user before this host-written output. The smoke covers actual SQL and lifecycle,
not the large-table footprint thresholds or performance. Failed isolated volumes
are retained for inspection during a local run; the hosted CI VM is disposable.

The write-diagnostics smoke exercises all five engines, both write patterns and
1/2/4 clients (30 short trials). It checks staged loading/writing/verification,
real SQL status snapshots, host-read database cgroup CPU counters and isolated
volume lifecycle. Its timings are not performance evidence.

## Offline storage-report regression

A separate `report-validation` job installs `requirements-report.txt` in a temporary
virtual environment and runs the offline `report-tests` suite, both normally
and with optimized Python (`-O`). The suite includes storage-report validation and
the tutorial driver's project-name guard. Hassan Kheder's regression covers row count,
checksum, exit code, OOM, inventory totals and storage deltas, requiring rejection
before any output directory is created. The database image continues to run its
115 lightweight tests without Matplotlib or the archived evidence. The extra offline
test uses archived data; it is not another database experiment. See the
[contribution review](teammate-1-review.md).

## Live tutorial correctness

The main integration job runs `scripts/check_tutorial.py --project "$CI_PROJECT"`
after the other lifecycle smoke checks. The driver rejects normal lab project names
before any Docker call, checks the database's labels and named volume, and refuses
pre-existing tutorial objects. It uses the restricted benchmark account, copies the
SQL to the database container and sources the real files with `--abort-source-on-error`.
No Docker socket, root SQL credentials or new plotting dependencies are added to the
runner image.

The smoke checks all five actual engines and then the common four-engine sequence
without creating a MyRocks table. Each uses 50,000 generated rows per engine and
100,000 rows per MEMORY index variant. It checks deterministic aggregates and row
notes, index identity/access/query answers, six rejected routine inputs, successful
single/concurrent increment totals, persistent data across a clean restart, empty
MEMORY rows and cleanup that preserves an unrelated sentinel table. SQL hashes,
server/host versions and observations are printed between
`TUTORIAL_VALIDATION_JSON_BEGIN` and `TUTORIAL_VALIDATION_JSON_END`; success ends
with `TUTORIAL SMOKE PASS`.

This is Linux amd64 correctness. The four-engine SQL path is checked on amd64 too;
it does not validate a native ARM host or an interactive Windows PowerShell session.
Short writer durations and CI counter output are not performance or engine-ranking
evidence. A tutorial demonstration is separate from the archived repeated benchmarks.
Normal laptop operation should follow the tutorial, not this restart-capable CI driver.
The lightweight database suite remains 115 tests. The offline suite now has two
tests, including the project's restart-target guard; each runs normally and with `-O`.

**Validated October 26, 2026:** [PR run 40395842648](https://github.com/majdsl/CU-Databases-Project/actions/runs/40395842648)
and [push run 40395828223](https://github.com/majdsl/CU-Databases-Project/actions/runs/40395828223)
passed against tutorial source head `1526e565d6aeb177ca177dd4f6e74bfabd92f5d4`.
The [archived validation record](../evidence/reviews/20261026-tutorial-ci/README.md)
retains the tested PR merge revision, real SQL observations and source hashes.
