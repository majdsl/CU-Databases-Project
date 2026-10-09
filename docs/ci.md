# Correctness CI

The [Correctness workflow](../.github/workflows/correctness.yml) runs on pushes,
pull requests and manual dispatch. **Implementation added; the first GitHub-hosted
run must pass before CI is recorded as validated.**

Each job starts from a fresh checkout on Ubuntu 24.04 and:

1. Generates disposable local credentials without printing their values.
2. Downloads the pinned OpenFlights snapshot and verifies its checksum.
3. Builds the pinned Python runner and runs the complete unit suite (currently 82 tests).
4. Builds the custom MariaDB image, including the pinned MyRocks plugin package.
5. Starts a fresh database volume and waits for its healthcheck.
6. Checks all five actual storage engines and verifies parameterized inserts/readback.

The integration check uses the existing `scripts/check_environment.py`: it checks
MariaDB identity, engine availability, actual table engine and exact contents of three
probe rows per engine, including an apostrophe-containing value. A successful check
prints five engine PASS lines and one overall PASS. Unit tests also exercise reporting,
isolation and failure handling with fixtures; they are not new benchmark observations.

## Scope and operation

The workflow does not run timing benchmarks or crash experiments. Shared CI host
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
