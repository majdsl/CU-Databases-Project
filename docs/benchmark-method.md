# Milestone 2: warm-read and load baseline

Status: implemented, unit-tested locally; live five-engine benchmark validation pending.
The earlier three-row setup check passed on the team laptop. That does not validate this harness.

## Research question and scope

How do load completion time, primary-key lookup latency and full-table aggregate
latency differ across InnoDB, Aria, MyISAM, MEMORY and MyRocks for identical data
and equivalent logical indexes on one MariaDB server?

This first experiment establishes a reproducible baseline. It cannot decide a universal
winner. Transaction guarantees, crash behaviour, sustained writes/compaction, cold reads,
physical disk footprint and concurrent workloads need separate experiments.

## Dataset and schema decisions

We generate synthetic flight-event records using a recorded seed. They are not
real flights, bookings or measured traffic. This avoids download failures and makes
the exact data repeatable while the harness is developed. No external dataset is
redistributed. An OpenFlights-based worked example and the justification for any
complementary data remain planned work before final submission.

| Column | SQL type | Purpose |
| --- | --- | --- |
| event_id | INT | Unique sequential primary key for lookup and verification |
| route_id | INT | 500 synthetic routes; secondary-index key |
| departure_epoch | INT | UTC seconds during 2026; avoids timezone conversion differences |
| delay_minutes | SMALLINT | Synthetic -15..180 minute delays for aggregation |
| fare_cents | INT | Integer monetary units, avoiding floating-point rounding |
| passengers | SMALLINT | 1..6; aggregate revenue uses fare_cents multiplied by passengers |
| payload | VARCHAR(64) | SHA-256 hex text derived from seed and ID; fixed-length high-entropy payload |

There are no NULLs, BLOB/TEXT columns, auto-increment, generated columns or foreign
keys. Those would introduce cross-engine capability differences in this baseline.
This is a single fact table, not a complete normalized airline application. The main
purpose is isolating storage behaviour while preserving a comprehensible workload.

Every engine uses the same explicit BTREE primary key and composite
(route_id, departure_epoch) secondary index, with utf8mb4_bin collation.
The secondary index incurs maintenance cost even though the initial query set does
not use it; range/secondary-index experiments will follow. SQL index declarations
do not imply identical physical structures: MyRocks uses LSM storage internally.
MEMORY's optional HASH indexes belong in a separate experiment.

The current payload is deliberately hard to compress. Results cannot be generalized
to highly repetitive text. A controlled compressible-versus-high-entropy experiment
is required before making compression recommendations.

The generator and canonical JSON-lines SHA-256 identify the exact dataset. The
result file also records Python and PyMySQL versions and hashes of experiment sources.

## Procedure

1. Validate configuration, acquire a server-wide advisory lock for this harness,
   check MariaDB and all five engines, and record selected global/session settings.
2. Generate rows once, outside timing. Reuse identical rows for every engine and round.
3. For each block of five rounds, shuffle the starting engine order with the seed,
   then cyclically rotate it. Each engine appears in every position once per block.
   This balances position, but does not eliminate all thermal or carry-over effects.
4. Refuse to overwrite an existing benchmark_events table. Create the selected engine's
   schema and verify the actual engine through information_schema.
5. Measure loading in batches of 500 with autocommit enabled. Timing includes driver
   batching, protocol round trips and statement completion. It excludes generation,
   table creation, ANALYZE and data verification. It does not imply equal durable commits.
6. Run ANALYZE, then read every row in primary-key order and compare every value and
   the dataset checksum. Failure invalidates the run. This verification warms caches.
7. Execute up to 50 additional lookup warm-ups and one aggregate warm-up, untimed.
8. Time 200 successful primary-key reads and five full-table aggregates. A round's
   seeded lookup sequence is identical for all engines. Check each answer outside
   the timer. Timings include execute/fetch and network/driver overhead.
9. Record EXPLAIN, SHOW CREATE TABLE, and engine-reported table statistics; drop only
   the table created by this trial; checkpoint the raw output after each trial.
10. Finish all 25 trials and generate summary.md. An incomplete run is marked failed
    and receives no completed report. Partial timings remain available for diagnosis.

The scan query sums non-indexed data columns and therefore requires row access;
it is not COUNT(*) alone, which some engines can answer using stored row counts.

## Controls, units and interpretation

- Default: 10000 rows, five rounds, 200 lookups and five scans per engine per round.
  These are small validation measurements, not final scale or steady-state results.
- Same server/version, driver, data, encoding, schema, batch size and query stream.
- Database container: 2 CPU quota and 2 GiB memory limit. Runner: 1 CPU quota and
  512 MiB limit. CPU quotas are not dedicated cores; the two containers share the host.
- Session: autocommit enabled, strict SQL and NO_ENGINE_SUBSTITUTION, query cache off,
  max_heap_table_size 128 MiB set before creating any MEMORY table.
- Engine caches are recorded as configured, not normalized to equal memory budgets.
  This is the initial configured-default comparison; equal-budget and tuned profiles
  are later experiments. Final methodology must account for OS cache as well.
- Load is seconds. Point and aggregate latency are milliseconds measured with
  perf_counter_ns. No Python sleeps are included in timings.
- For each read metric, compute a mean within each round, then report mean, sample
  standard deviation, min and max across round means. Do not pool all queries and
  claim thousands of independent repetitions. Raw samples support later distribution plots.
- Table status fields are engine-reported metadata, **not comparable physical disk
  size measurements**. MEMORY allocation must never be plotted as persistent disk size.
- Loading fresh MyRocks tables on a reused server does not isolate background
  compaction or guarantee steady state. Dropping a table does not necessarily reclaim
  its files immediately. Balanced order does not remove this limitation.
- Client and server run on the same laptop/WSL host. Its scheduling, host caches,
  power management and background load affect results. Do not generalize absolute times.

## Reproduce on Windows PowerShell

Start Docker Desktop. From this checkout, generate .env only if it is absent
using python scripts/init_env.py (the generator preserves existing credentials).

```powershell
docker compose build runner
docker compose up -d --wait db
docker compose run --rm runner python -m unittest discover -s tests -v
docker compose run --rm runner python -m benchmarks.run
```

On a fresh checkout, build both services with docker compose build db runner first.
Do not run the setup check or a second benchmark concurrently with measurements.
Keep the laptop plugged in, record its power mode, and pause heavy background work.

Each run writes results/<UTC-timestamp>-<random-id>/results.json and summary.md
through a bind mount. The JSON preserves configuration, checksums, metadata, raw
samples, engine order, query plans and status. These local results are ignored by Git.
Review selected raw runs and commit them to a separate evidence directory before
submission; do not leave final findings available only on one laptop.

Ubuntu users may need to create a writable results directory and use
docker compose run --rm --user "$(id -u):$(id -g)" runner python -m benchmarks.run
so the non-root container user can write to their bind mount. That command is for
a Linux shell, not PowerShell. No root-run benchmark is required.

## Troubleshooting and safe behaviour

- Only DB_NAME=engine_lab is accepted. The harness uses the existing non-root account.
- Existing benchmark_events causes a refusal, not an automatic DROP. After a killed
  run, inspect whether the table belongs to that experiment before manually removing it.
- Never remove the database volume to retry the benchmark. Do not regenerate passwords.
- Permission errors under /results refer to the result-folder mount; inspect ownership.
- A MEMORY table-full error is a real limit, not a zero-time result or an automatic skip.
- Stop a failed run and inspect its error and partial JSON. Do not compare incomplete runs.

## Milestones still required for the complete project

1. Live baseline run, fresh-environment reproduction, and independent teammate run.
2. Fully identify Python base/built images and OS packages; automate correctness in CI.
3. Larger datasets and cache-budget profiles; range queries and alternative MEMORY indexes.
4. Concurrent writes, contention, transaction/rollback semantics and repeated crash recovery.
5. Physical storage measurement with engine-specific accounting and compaction handling.
6. Charts, uncertainty, explained mechanisms, limitations and actionable recommendations.

## References

- [Assignment and rubric](https://mariadb.org/bachelor_hackathon_2026-09/)
- [MEMORY limits and indexes](https://mariadb.com/docs/server/server-usage/storage-engines/memory-storage-engine)
- [MyRocks compression](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/myrocks-and-data-compression)
