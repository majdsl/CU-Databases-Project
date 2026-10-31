# Correctness CI

**Main validation, October 29, 2026:**
[run 40883972632](https://github.com/majdsl/CU-Databases-Project/actions/runs/40883972632)
passed all four jobs for `8fd722cbd0b429b1f28e8b4c02b378d17d486e56`: fresh five-engine
setup/integration, the expanded offline suite in normal/optimized Python, and stock
tutorials on native Linux amd64 and ARM64. That revision passed 132 lightweight and
40 offline tests, including all eight report generators with repeated output checks,
per-case tutorial lock observations and exact transaction outcomes. These are
correctness/reproduction checks, separate from the archived laptop performance runs.

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

The five-engine integration job starts from a fresh checkout on Ubuntu 24.04. It prepares a disposable
results directory for UID 10001 and runs the README setup wrapper,
`scripts/setup_project.py`, with a unique CI project name. The wrapper:

1. Generates disposable local credentials without printing their values.
2. Downloads the pinned OpenFlights snapshot and verifies its checksum.
3. Builds the pinned Python runner, checks results-mount write access and runs the complete lightweight unit suite.
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

## Offline report and tutorial guards

A separate `report-validation` job installs `requirements-report.txt` in a temporary
virtual environment and runs the offline `report-tests` suite, both normally
and with optimized Python (`-O`). The suite includes storage-report validation and
the tutorial drivers' project/ownership/credential guards. Hassan Kheder's regression covers row count,
checksum, exit code, OOM, inventory totals and storage deltas, requiring rejection
before any output directory is created. The database image continues to run its
lightweight suite without Matplotlib or the archived evidence. The offline
regression uses archived data; it is not another database experiment. See the
[contribution review](teammate-1-review.md).

Six compression-report tests validate the real archived pilot/full files and
trial-level statistics, reject changed settings/source identities, incomplete runs,
altered raw workers/inventories/command bytes and a wrong network namespace, and
require rejection before output creation. They distinguish tiny floating-point
roundoff from material statistic changes. Two generations must produce the same
seven files and leave raw evidence untouched. These tests use the reporting
environment; the lightweight runner does not require Matplotlib.

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
single/concurrent increment totals, per-case lock-counter deltas and server-side
procedure interval overlap, exact commit/rollback outcomes, persistent data across
a clean restart, empty MEMORY rows and cleanup that preserves an unrelated sentinel table. SQL hashes,
server/host versions and observations are printed between
`TUTORIAL_VALIDATION_JSON_BEGIN` and `TUTORIAL_VALIDATION_JSON_END`; success ends
with `TUTORIAL SMOKE PASS`.

This lab-image job is Linux amd64 correctness. Its four-engine sequence also runs
inside that lab image. The separate stock-image jobs below cover native ARM64;
interactive Windows PowerShell reproduction remains separate.
Short writer durations and CI counter output are not performance or engine-ranking
evidence. A tutorial demonstration is separate from the archived repeated benchmarks.
Normal laptop operation should follow the tutorial, not this restart-capable CI driver.
At `62ca1fa`, the lightweight database suite had 140 tests, including immutable image selection,
retagging/collision checks and worker-control drift rejection. Its offline suite had
47 tests covering storage/compression reports, immutable write-diagnostic and
cache-pressure source provenance, private
credential creation, tutorial guards/counters/transaction outcomes, Windows output-path
normalization, and complete report regeneration. Each runs normally and with `-O`.
The all-report regression generates all eight reports twice in a temporary copy and
checks that source/evidence inputs retain their hashes. The CI job first fetches the
checksum-pinned OpenFlights data; reporting itself is offline. It exercises the current
working files rather than accidentally testing an older Git archive.

The current offline job also runs `scripts/check_cloud_openflights.py` normally
and with `-O`. It checks the separately archived laptop/cloud pilot/full data,
comparison JSON/CSV, measured source and all sealed archive checksums. Its current
entry point canonicalizes Windows/POSIX paths and rejects missing checksums or a
maintenance `--write` request without changing the archived validator. Corruption
guards exercise changed samples/digests, comparisons, source and checksum coverage.

Host-launcher guards in `report-tests/` additionally verify immutable OpenFlights
image selection, retagging resistance, actual container/volume ownership, pre-workload
source/server/SQL controls, failed-stage preservation and local Docker endpoint
selection. These host-only checks do not require adding the launcher to the runner
image or changing historical Dockerfile provenance. Current test totals are printed
by the workflow; dated records retain their original counts.

The fresh disposable CI results directory stays owned by the host user and grants
group 10001 write access, so host orchestrators and the container runner can both
create output without an ownership flip between steps. This CI-only preparation
does not make results writable by everyone or alter any existing user directory.

The integration job runs `scripts/run_openflights.py --smoke` separately. It prepares
unique DB/runner images, selects immutable IDs, checks actual containers and all five
engines, and cleanly stops its isolated database while retaining its volume. It does
not run timed OpenFlights trials. Performance pilot/full runs still require a person
to prepare, review the pilot, and explicitly invoke full with the same session.

**Validated October 26, 2026:** [PR run 40395842648](https://github.com/majdsl/CU-Databases-Project/actions/runs/40395842648)
and [push run 40395828223](https://github.com/majdsl/CU-Databases-Project/actions/runs/40395828223)
passed against tutorial source head `1526e565d6aeb177ca177dd4f6e74bfabd92f5d4`.
The [archived validation record](../evidence/reviews/20261026-tutorial-ci/README.md)
retains the tested PR merge revision, real SQL observations and source hashes.

## Native stock-image tutorial

The `stock-tutorial` matrix runs on `ubuntu-24.04` (amd64) and `ubuntu-24.04-arm`
(ARM64). It runs `scripts/check_stock_tutorial.py` against the official MariaDB
index pinned by digest, using the current common SQL files and shared assertions
as the lab tutorial. No MyRocks package or Python plotting dependency is installed
in that database image.

Each job verifies that host, Docker engine and selected image architectures match.
The runner refuses existing resource names, creates a uniquely labelled container
and named volume, uses the official healthcheck, verifies the read-only SQL mount's
hashes, and checks all four real engines, index access, invalid inputs, single and
concurrent updates, clean restart and SQL cleanup. It checks ownership before
restarting or removing resources. No database port is published. Generated passwords
stay in the child process environment; credential-bearing Docker inspection output
is omitted from logs.

The runner saves JSON validation/commands and a transcript under `results/` and
prints the command records plus `STOCK_TUTORIAL_VALIDATION_JSON_BEGIN/END` and
`STOCK TUTORIAL PASS`. The [October 27 archived record](../evidence/reviews/20261027-stock-tutorial-ci/README.md)
retains native amd64 and ARM64 output from
[PR run 40421200797](https://github.com/majdsl/CU-Databases-Project/actions/runs/40421200797).
Read [the validation guide](stock-tutorial-validation.md) for tested revisions,
image identities and the scope of the claims. These are correctness checks, with
short writer calls, separate from the controlled performance experiments.

## MyRocks compression correctness

The integration job additionally runs `scripts/run_rocksdb_compression.py --smoke`
with four fresh disposable databases: no compression/ZSTD crossed with two
deterministic payload profiles. Each has only 256 rows. The host builds each image
once and runs by immutable ID. The worker verifies the actual CF options, codec
properties for table-mapped SSTs, exact rows, point/aggregate answers and stable
SST layout. A read-only helper inventories the owned volume after a verified clean
stop; cleanup checks the identities of all three containers and the volume.

The 17 new lightweight tests cover data corruption, ignored compression options,
SST coverage/inventory, nonfinite/incomplete results, image/source identity, resource
collisions and foreign ownership, live snapshots, private logs, remote contexts,
failed-trial preservation and balanced full scheduling. They also pass with `-O`.
The driver prints a record between `COMPRESSION_VALIDATION_JSON_BEGIN/END` for
inspection. This smoke validates the configuration and lifecycle on Linux amd64;
its timings and file sizes are not new laptop performance findings. The
[measurement protocol](rocksdb-compression-method.md) specifies the separate pilot/full runs.

**Validated October 27, 2026:** [PR run 40577805344](https://github.com/majdsl/CU-Databases-Project/actions/runs/40577805344)
passed all four jobs for source head `c430b938753e028da05a9ad071779b1b03ddb15e`.
The [archived compression record](../evidence/reviews/20261027-rocksdb-compression-ci/README.md)
retains the tested merge revision, effective options, actual SST metadata and
stopped-volume inventory. This entry records the October 27 compression check;
later code and report-validation changes have separate validation records above.
