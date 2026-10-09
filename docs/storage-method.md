# Isolated storage footprint experiment

Status: implementation prepared; local unit tests passed. A real Docker/MariaDB
pilot is still required on the project laptop. There are no storage results yet.

## Question and scope

For the same synthetic rows and matching schema/index definitions, what changes
in Linux filesystem allocation after table creation, loading, validation, ANALYZE,
and a clean database shutdown? What allocation does each engine report while live?

These are separate measurements. They do not establish equal durability, an engine's
minimal possible footprint, steady-state compaction size, or Windows physical disk use.
This is a storage experiment, not a throughput benchmark.

## Protocol

`scripts/run_storage.py` runs on the host using Python's standard library. It uses
`compose.storage.yaml` by itself, never as an override of `compose.yaml`.

1. Generate a unique Compose project name for each engine/trial. Refuse existing
   resources under that name. Each project has its own network and named volume.
2. Build the separate storage DB and runner image tags once for the run, from the
   existing project Dockerfiles. Record the actual image IDs used.
3. Initialize the fresh server, wait for health, stop it with a 120-second grace
   period, and require a zero exit code with no OOM. Snapshot the empty-database
   datadir's regular-file lengths and filesystem blocks from a read-only mount.
4. Restart that isolated server. Refuse any pre-existing tables in `engine_lab`.
   Use the existing per-engine SQL files, strict mode and engine substitution checks.
5. Generate the same seeded rows, load in batches of 500 using autocommit, and compare
   every row in primary-key order. Verify the SHA-256 against the host's dataset.
6. Run ANALYZE and save live SHOW TABLE STATUS, actual DDL, server settings and version.
7. Stop cleanly again and take the second file inventory. Compute signed after-minus-
   before changes without clamping negative values.
8. Checkpoint the evidence before removing this trial's disposable Compose project
   and volume. The ordinary `cu-engine-lab` project is not addressed by these commands.
   On failure, stop and preserve the isolated volume plus partial JSON for diagnosis.

The default is 10,000 rows and five balanced engine-order rounds (25 fresh volumes,
used sequentially). `--pilot` selects one round, five trials. A pilot establishes that
the procedure works; it is not sufficient for a stable engine ranking. Do not combine
pilot and full-run observations as if they had a prespecified common design.

## Metrics

| Measurement | Meaning | Limits |
| --- | --- | --- |
| Regular-file apparent bytes | Sum of file lengths, hardlinks counted once | Sparse holes count in length |
| Regular-file allocated bytes | Sum of Linux `st_blocks * 512`, hardlinks counted once | Guest filesystem allocation, not Windows SSD/VHDX size |
| Signed allocation delta | After-load snapshot minus initialized empty-DB snapshot | Includes logs, metadata and a second start/stop cycle; not table-only size |
| Live Data_length / Index_length | Values reported by each engine after ANALYZE | Engine-specific semantics and possible stale/approximate statistics |
| MEMORY live allocation | Approximate allocation for in-memory rows/indexes | Not total server RSS, and not persistent disk data |

File inventories retain paths and both byte counters. Directories, symlinks, sockets
and other nonregular files are excluded; excluded nonregular paths are listed. No
file contents are copied. Disk measurements are made only after the server stops.

MEMORY rows disappear at shutdown. Its stopped-database disk delta is metadata and
server overhead, **not** the footprint of persistent copies of those rows. Do not
rank it as a zero-byte disk-storage alternative. Report its live allocation separately.

There is no forced MyRocks flush or full compaction step. The measurement is the
observed post-clean-shutdown footprint under the installed settings. WAL, SST and
metadata files, if present, remain in the full inventory. No SST-only, compression
ratio or steady-state space-amplification claim is made.

All trials use the same host. Fresh volumes remove prior-table history, not host
variation. Startup/log changes have no separate empty-workload control, so do not
attribute all datadir changes to the rows themselves. Allocation granularity matters
at this small scale. Record charger/power mode with `--power-condition` and retain
both raw snapshots, not just their differences. No speed ranking is inferred.

## Evidence and recovery

Each run writes `results/<UTC>-storage-<id>/results.json`. A completed run also has
`summary.md`. JSON includes each load's verified row count/checksum, file inventories,
clean-stop evidence, settings, runtime metadata, image IDs and source hashes.
Passwords and Docker container environment contents are not recorded.

The host checkpoints before and after cleanup. A failed run has status `failed`, no
success summary, and an `active_project` when isolated resources may remain. Do not
manually delete any normal database volume. Inspect the reported isolated project
before deciding on cleanup. An interrupted host process can leave that isolated
server running; this is not an automatic-resume implementation.

## Validation completed here

Unit tests cover namespace rejection, existing-resource refusal, live/unclean-server
snapshot refusal, loader isolation, protection of pre-existing tables, evidence
retention on failure, sparse files, hardlinks, symlinks, signed deltas, and report
labels/completeness. Existing baseline tests check the reused generator/validator.
These are not live database integration tests. The pilot on the laptop is still
required before treating any run as validated evidence.

## Sources

- MariaDB, [SHOW TABLE STATUS](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/show/show-table-status): engine-specific fields and MEMORY allocation.
- MariaDB, [MEMORY](https://mariadb.com/docs/server/server-usage/storage-engines/memory-storage-engine): volatile rows.
- MariaDB, [MyRocks and Data Compression](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/myrocks-and-data-compression): RocksDB file context.
- Python, [os.stat_result](https://docs.python.org/3/library/os.html#os.stat_result): file length and allocated block counters.
- Docker, [compose stop](https://docs.docker.com/reference/cli/docker/compose/stop/): stopping and grace timeout.
