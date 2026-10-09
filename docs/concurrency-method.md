# Concurrent writes: first experiment

Status: first team run completed and uploaded raw data validated on 2026-09-29.
Run 20260929T064106Z-writes-612ad3ec contains 150 trials and 150000 updates;
all expected final-data checksums and summary calculations passed offline checks.
The raw upload has not yet been archived in this repository. A four-client slowdown
in MyISAM/MEMORY is observed; its cause is not established. See the
[CPU diagnostic](cpu-diagnostic.md) before interpreting engine scaling.

## Question and design

How does fixed-work update throughput change at 1, 2 and 4 connected clients,
with separate row partitions versus a shared 16-row hotspot?

Use the same seven-column schema, BTREE index definitions and deterministic 10000-row
synthetic dataset as the baseline. Five engines, five rounds, two patterns and three
client counts produce 150 trials. Each trial recreates and verifies its own table.
The default workload is **1000 total updates per trial**, not 1000 per client.
One SQL statement increments fare_cents by one, using a parameterized primary key.
There are no explicit multi-statement transactions; each session has autocommit enabled.
The complete expected final dataset is computed independently from all key streams.
All rows, including unmodified columns, must match before accepting a trial.

Disjoint clients own separate key partitions. Hotspot clients cycle across the same
16 keys. At the default row/update counts, the per-key update counts are identical
across client counts within each pattern. The patterns deliberately touch different
numbers of rows; compare scaling within each pattern before comparing patterns.

Each thread owns a separate connection. Connections and session configuration happen
before a timed barrier releases all clients. Wall time runs from barrier release until
the last worker finishes its final update. Connection teardown, schema creation,
loading and full verification are excluded. Per-statement client-observed latencies
are retained. Throughput is total acknowledged updates divided by wall time, not the
sum of per-client rates. The summary reports mean and sample SD across five trials.

Engine order uses the baseline's balanced rotation. The six pattern/client conditions
also rotate across rounds, but **five rounds do not perfectly balance six conditions**.
The raw trial sequence preserves their order. No query-cache or cold-cache claim is made.

The harness uses the same advisory lock as the baseline and refuses to replace an
existing benchmark_events table. It drops only a table it successfully created.
A connection/update failure produces a failed checkpoint, no success summary and no
automatic retry: a disconnect can leave an uncertain commit outcome. Do not interpret
failed-run throughput as successful performance. An interruption may leave the table
behind; inspect it before removing it manually. Do not delete the database volume.

## Run

Start Docker Desktop. From the project directory, after pulling this revision:

```powershell
docker compose build runner
docker compose up -d --wait db
docker compose run --rm runner python -m unittest discover -s tests -v
docker compose run --rm runner python -m benchmarks.concurrency
```

Results go to `results/<timestamp>-writes-<id>/results.json` and `summary.md`.
Stop after an error and inspect it. Preserve failed JSON too, if diagnosing failures.
Do not run another benchmark or the setup probe at the same time.

## Interpretation and limits

These are short, fixed-work bursts on one reused server, not sustained saturation or
independent machine replications. The Python runner has one CPU, so client overhead
can limit observed scaling. The database has two CPUs. Background compaction,
checkpoints, OS caching, laptop power state and thermal throttling can affect results.
A follow-up should measure client/server utilization and longer workloads before
attributing a throughput plateau to an engine's locking design.

Equal SQL and autocommit do not imply equal durability. Aria's TRANSACTIONAL table
option concerns crash safety, not support for user transactions. MEMORY loses its
rows on restart. These distinctions must accompany any comparison; this experiment
does not itself measure recovery or rollback. Lock-wait errors are failures, not
silently discarded observations. Raw error types/codes are retained without passwords.

Physical storage measurement is a separate pending experiment: SHOW TABLE STATUS is
not a common physical-byte accounting method across these engines. It will need
isolated volumes, explicit logical/apparent/allocated byte definitions, separate
engine log accounting and stated MyRocks flush/compaction conditions. A zero persistent
MEMORY data footprint must never be described as zero RAM cost.

## References reviewed

- [Aria table options and transaction caveat](https://mariadb.com/docs/server/server-usage/storage-engines/aria/aria-storage-engine.md)
- [MEMORY persistence and index choices](https://mariadb.com/docs/server/server-usage/storage-engines/memory-storage-engine.md)
- [MariaDB explicit locks and transaction interaction](https://mariadb.com/docs/server/reference/sql-statements/transactions/lock-tables.md)

The harness does not issue LOCK TABLES; it measures normal UPDATE behaviour.
