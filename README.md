A project for area 6, "Choosing the right storage engine" for the [MariaDB student database projects, 2026-09](https://mariadb.org/bachelor_hackathon_2026-09/).

# CU Databases Project: storage engine comparison

**Status: five-engine setup and first team load/read baseline validated; first concurrent-write run validated; CPU-limit diagnostic completed with four archived runs and generated charts; isolated storage pilot and full 25-trial run verified, with findings and charts. Crash recovery and final engine recommendations remain pending.**
The comparison uses Python and MariaDB with InnoDB, Aria, MyISAM, MEMORY and MyRocks (SQL engine name ROCKSDB).
Five engines alone do not establish depth: the final project must explain measured trade-offs and failure behaviour.

## First benchmark (milestone 2)

The baseline uses 10000 reproducible synthetic flight events and five balanced-order
rounds across all five engines. It measures load completion, warm point lookups and
full-table aggregates. It saves every timing and verifies every loaded row.

After completing first-run setup below:

```powershell
docker compose run --rm runner python -m unittest discover -s tests -v
docker compose run --rm runner python -m benchmarks.run
```

Results appear in a new subfolder of `results/` on your computer. Open its
`summary.md` for the table and preserve `results.json` for raw measurements.
A small baseline does not establish engine recommendations. See the
[benchmark method](docs/benchmark-method.md) for schema rationale, controlled variables,
statistical units, workload limitations and troubleshooting.

## Verified experiments

The [first measured baseline](evidence/baseline/20260923T121610Z-92b1c313/README.md)
contains the original raw results, summary and review notes. It covers five repeated
trials per engine on 10000 synthetic rows, not a general engine ranking.

The [concurrent-write experiment](docs/concurrency-method.md) compares 1, 2 and 4
clients with disjoint rows and a shared hotspot, with full final-data verification.
The first team run completed 150 trials with verified final data. The [CPU findings and charts](docs/cpu-findings.md) show that runner quota
affected throughput; engine-level scaling conclusions remain limited.

The [storage findings and charts](docs/storage-findings.md) cover the verified October 6 full run:
25 fresh-volume trials, 10,000 identical rows per trial, matching checksums and 50 clean
shutdown records. Allocated datadir growth includes logs, metadata and restart effects;
MEMORY's live RAM allocation is reported separately. The pilot is excluded from the full-run
statistics. See the [storage method](docs/storage-method.md) and [archived evidence](evidence/storage/).
Clean shutdowns are not crash-recovery tests.

## Findings with evidence

Start with [CPU findings and charts](docs/cpu-findings.md): four archived runs,
power conditions kept separate, complete tables, uncertainty and reproduction steps.
Then read [storage findings and charts](docs/storage-findings.md), including the measured
file allocation, live MEMORY allocation and limits on interpretation.
The raw code and data are on this development branch; they must reach main before submission.

## Reproduce the storage experiment

After first-run setup, use host Python from the repository root. Run each command separately.
Keep host conditions stable and replace the power-condition text if your settings differ.

```powershell
python -m unittest discover -s tests -p test_storage.py -v
python scripts/run_storage.py --pilot --power-condition "plugged in; battery saver off"
```

Review the pilot results before running the full five-round experiment:

```powershell
python scripts/run_storage.py --power-condition "plugged in; battery saver off"
```

The script uses `compose.storage.yaml` with unique temporary projects and volumes, leaving
the normal database separate. Successful temporary volumes are removed after evidence is saved;
failed-trial volumes are retained for diagnosis. Results are saved under `results/`.
The archived full run is `20261006T120404Z-storage-a5d23142`; rerunning is not required to view it.

Charts are already committed. Optional regeneration requires Matplotlib on the host:

```powershell
python scripts/report_storage_findings.py
```

This reads archived evidence and does not rerun the database experiment.

## Remaining work before submission

- Design and run controlled crash-recovery experiments in disposable instances. Measure
  acknowledged-write survival, restart/recovery behavior and any required repair; distinguish
  transactional behavior and MEMORY volatility. Do not crash the normal project database.
- Review OpenFlights integration and complementary data coverage against the area-6 brief;
  explain why the current synthetic workload was chosen and what it cannot represent.
- Turn the measured trade-offs into workload-specific recommendations and explain the
  storage, locking and durability mechanisms, with evidence and limitations.
- Add correctness CI and check reproduction from a clean checkout. Pin the Python image
  and document the machine/VM configuration; preserve historical run metadata.
- Add the team roster and actual contributions, finish the tutorial, then review and merge
  the project into `main`. See [evidence plan](docs/evidence-plan.md).

## First run (Windows PowerShell)

Requirements: Git, running Docker Desktop with Linux containers and Compose, and local Python 3.9+ for credential generation. Run from the repository root:

```powershell
python scripts/init_env.py
docker compose build db runner
docker compose up -d --wait db
docker compose run --rm runner
```

The runner must print five engine PASS lines followed by an overall PASS.
A team-run check passed for all five engines; see [setup validation](docs/setup-validation.md) for the tested commit, output and limitations.
Running again repeats the check. The probe table is dropped after each successful creation;
an interrupted run may leave it behind, in which case inspect and remove only
`engine_lab.setup_probe` before retrying. Do not use this setup against an existing database.

The .env file contains generated credentials and is already excluded by the repository's
.gitignore. Keep it locally; do not paste it into chat or commit it.
The generator preserves an existing .env. Database initialization credentials apply on
first creation of the volume; changing .env later does not change existing database passwords.

If local Python is unavailable, generate credentials using a container:
```powershell
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim python scripts/init_env.py
```

## What the setup verifies

The runner uses a non-root database account restricted to engine_lab.
It checks the server is MariaDB, checks engine availability, creates an identical
probe schema for each engine, verifies the actual engine in information_schema,
and inserts and reads back three rows using parameterized values.
The apostrophe-containing value checks that data is passed as parameters.
The explicit BTREE primary index avoids MEMORY's default index-type difference.

This small single-table probe is **not the benchmark data model**. It has an integer
primary key and bounded character data so all five engines can use the same schema.
The initial benchmark schema and synthetic dataset are documented in docs/benchmark-method.md; larger-scale and failure experiments remain pending.

MariaDB data stays in a Docker named volume; no database port is exposed on the host.
The database is capped at 2 CPUs and 2 GiB; the runner at 1 CPU and 512 MiB.
These are initial development limits, not a finalized experimental configuration.
The Compose healthcheck waits for InnoDB initialization before the runner starts.
Query cache is disabled and NO_ENGINE_SUBSTITUTION prevents silent engine fallback.

## Versions and verification status

The MariaDB image digest is pinned to the image downloaded during setup:
`sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112`.
The separately tested setup container reported MariaDB 11.8.9-MariaDB-ubu2404.
The four-engine Compose stack passed on the team laptop on September 16 and 22, 2026,
based on shared terminal output. The five-engine build also passed on September 22, 2026, based on team-provided terminal output (see docs/setup-validation.md).

PyMySQL 1.1.2 is pinned with its wheel SHA-256 from
[PyPI](https://pypi.org/project/PyMySQL/1.1.2/).
The Python 3.12-slim base tag is not yet digest-pinned.
Final benchmark reproducibility requires locking that image and recording runtime metadata.

## Stop and troubleshoot

`docker compose stop` stops this stack and preserves data.
`docker compose logs --tail=60 db` shows database startup diagnostics.
`docker compose ps` shows service health.
The earlier standalone cu-mariadb-check container is separate; stop it before measurements
using `docker stop cu-mariadb-check`.
No cleanup command that deletes volumes is part of normal setup.

## Files

- compose.yaml: database, runner, healthcheck and development resource limits.
- Dockerfile / requirements.txt: Python runner and dependency.
- scripts/init_env.py: local random credentials.
- scripts/check_environment.py: real database integration check.
- sql/: five explicit identical probe schemas differing only by engine.
- benchmarks/: seeded generation, baseline harness, and report statistics.
- tests/: unit checks for reproducibility, integrity and reporting.
- sql/benchmark/: identical benchmark schemas across all five engines.
- docs/benchmark-method.md: first experiment design and limitations.
- compose.storage.yaml / scripts/run_storage.py: isolated storage experiment.
- benchmarks/storage.py: verified loading and stopped-server file inventory.
- docs/storage-findings.md / docs/figures/: storage interpretation and charts.
- scripts/report_storage_findings.py: reproduce storage charts and derived data.
- evidence/storage/: verified pilot and full raw results.
- docs/evidence-plan.md: remaining work mapped to the rubric.

## Team and collaboration

Constructor University database course, Fall 2026.
Team roster and contributions will be supplied by the team before submission.
Use task branches and pull requests; verify the runnable project is merged into main
before submission, because the published evaluator evaluates main.

## References

- [Assignment and current evaluation prompt](https://mariadb.org/bachelor_hackathon_2026-09/)
- [MariaDB storage engines](https://mariadb.com/docs/server/server-usage/storage-engines)
- [Official image healthcheck](https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/using-healthcheck-sh)

## MyRocks setup

The custom database image in docker/mariadb installs exactly
`mariadb-plugin-rocksdb=1:11.8.9+maria~ubu2404` on the pinned base image.
This candidate was confirmed in the team's amd64 Ubuntu 24.04 container.
The build checks that mariadb-server-core remains at the matching version.
Other transitive OS packages are not fully locked; preserve the built image digest
and package manifest before final experiments. Other architectures are unverified.

The package's rocksdb.cnf is replaced with explicit startup configuration, so
MyRocks loads on both new and existing database volumes. It uses a 128 MiB block
cache for initial development and ROW binary-log format. These are not finalized
benchmark settings. The Python check requires ROCKSDB availability and verifies
the actual engine and row contents, just as it does for the other four engines.

To update an existing checkout on this branch:

```powershell
git pull --ff-only
docker compose build db runner
docker compose up -d --wait db
docker compose run --rm runner
```

The database container will be recreated using the existing named data volume.
Keep .env unchanged. Do not delete the volume to troubleshoot startup failures;
inspect `docker compose logs --tail=80 db` instead. If the build fails, stop and
inspect the error before running the remaining commands.

Reference: [MariaDB MyRocks installation](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/getting-started-with-myrocks).
