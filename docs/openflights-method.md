# OpenFlights route comparison

**Status: ingestion and harness implemented; local unit checks and full-source parsing passed.
The real Docker pilot and full benchmark remain pending. No OpenFlights timing result is claimed yet.**

## Why add this experiment?

Area 6 of the [assignment](https://mariadb.org/bachelor_hackathon_2026-09/) names OpenFlights
and asks for complementary data where it does not illustrate the relevant properties.
The earlier experiments use seeded synthetic events. This comparison adds actual OpenFlights
reference records; it does not rename synthetic events as real flights.

The question is how the same route table and query stream behave across InnoDB, Aria,
MyISAM, MEMORY and MyRocks (SQL name ROCKSDB): loading, warm primary-key reads, full scans
and secondary-index candidate queries. One Python harness executes the same SQL and
verification for every engine. It reuses the existing schedule, timing, metadata and
statistics helpers; per-engine schemas differ only in ENGINE.

## Immutable source and profile

Source: [MariaDB/openflights at revision 1608b8d](https://github.com/MariaDB/openflights/tree/1608b8d24f30d153175dcc16bfe50e56dcc9256e),
file `data/routes.dat`, supplied by [OpenFlights](https://openflights.org/data.html).
The checked revision is a reproducibility pin, not a claim that the route network is current.
Attribution, [ODbL license](../data/openflights/LICENSE) and a
[download manifest](../data/openflights/manifest.json) are committed. No upstream SQL is executed.

The source was downloaded and parsed locally on October 9, 2026:

| Check | Observed value |
| --- | ---: |
| Raw bytes | 2,309,485 |
| Route records (all nine fields) | 67,663 |
| Missing airline IDs (`\N`) | 479 |
| Missing source / destination airport IDs (`\N`) | 220 / 221 |
| Distinct non-null source airport IDs | 3,320 |
| Minimum / maximum records per non-null source | 1 / 915 |
| Exact duplicate nine-field records | 0 |
| Repeated airline-ID/source-ID/destination-ID combinations beyond first occurrence | 84 |
| Nonzero stop counts | 11 records, each with one stop |
| Maximum equipment-string length | 35 characters |

Raw-file SHA-256: `2b2a73310b0d8e4c3993042ee1e3827ee3c368730edd23441b4dfd79591839d2`.
Canonical transformed-row SHA-256: `ea46aabb9533882cf36baa761b285ef8f8829915ff1b3a689fc8315206532441`.
Canonical rows use the shared `row_bytes` JSON-lines representation, with integer values and
JSON null. The full-scan oracle is `(67663, 11, 305336)` for count, sum of stops and sum of
equipment character lengths. This profile is dataset validation, not a database benchmark.

## Schema and transformation

| Column | Type | Meaning |
| --- | --- | --- |
| route_row_id | INT NOT NULL | One-based position in the pinned CSV, explicit primary key |
| airline | VARCHAR(3) NOT NULL | Original airline code |
| airline_id | INT NULL | Original ID; `\N` becomes NULL |
| source_code / destination_code | VARCHAR(4) NOT NULL | Original airport codes |
| source_id / destination_id | INT NULL | Original IDs; `\N` becomes NULL |
| codeshare | VARCHAR(1) NOT NULL | Original empty string or Y |
| stops | TINYINT UNSIGNED NOT NULL | Parsed integer number of stops |
| equipment | VARCHAR(64) NOT NULL | Original equipment list, including spacing |

All five tables have explicit BTREE primary keys and a nonunique BTREE
`(source_id, destination_id)` index, with utf8mb4 and utf8mb4_bin collation.
The source row ID preserves repeated route combinations without imposing a unique route key.
No foreign keys, auto-increment, TEXT/BLOB or engine-specific alternative indexes are used.
The VARCHAR bounds are checked before any database write; strict SQL prevents silent truncation.
This is a common-capability projection, not a copy of the upstream multi-table schema.
Equivalent SQL indexes do not imply identical physical engine structures.

All 67,663 records are included in both pilot and full runs. Missing IDs, empty codeshare
values and repeated route combinations are preserved. No joins silently exclude orphan/missing
references. Airports, airlines, country and aircraft tables are not loaded in this first
comparison; it does not measure relational joins or full OpenFlights application behavior.

## Workload and verification

Each trial creates `engine_lab.openflights_routes` only if it does not exist, verifies the
actual engine, and inserts the complete dataset in 500-row batches with autocommit ON.
Load timing covers driver batching and execute completion; it excludes generation, DDL,
ANALYZE and validation, and does not imply equivalent durable commit guarantees.

After ANALYZE, the harness reads every row in primary-key order and verifies every value
and the full canonical digest. That read warms the data. Additional untimed warmups are
up to 50 point queries, one full scan and up to 20 source queries.

| Measured workload per trial | Count | Answer verified against Python oracle |
| --- | ---: | --- |
| Primary-key lookup of all columns | 200 | Exact row for seeded existing row ID |
| Full-table aggregate | 5 | COUNT(*), SUM(stops), SUM(CHAR_LENGTH(equipment)) |
| Source-airport aggregate | 100 | COUNT(*) and SUM(stops) for seeded non-null source ID |

Both aggregate queries access non-indexed values; the full scan is not a metadata-only
COUNT(*). Source IDs are sampled uniformly from the 3,320 distinct non-null sources,
not proportional to route counts and not from observed user traffic. The source query
is eligible for the secondary index; saved EXPLAIN output determines what plan was actually used.
Missing-source rows remain in the full scan and primary-key workload.

All engines in a round receive the same rows and query streams. The seeds, raw timings,
source result counts, EXPLAIN plans, actual DDL, global/session settings, dataset/source hashes,
server version and runner runtime/cgroup limits are saved in `results.json`.
The timed execute/fetch includes database, protocol and Python-driver overhead; answer
comparison is outside the timer. Query failures abort without retry or fabricated timings.

The pilot has one round across five engines (five trials). The full run has five cyclically
balanced engine-order rounds (25 trials, 1,691,575 loaded and verified rows in total).
For reads, calculate the mean within each trial, then mean, sample SD, median, range and
nearest-rank p95 across the five round means. Do not pool queries as independent repetitions.
Five rounds offer limited uncertainty information; pilot SD is unavailable, not zero.

## Controls and limits

- Use the normal Compose development limits: DB 2 CPU quota / 2 GiB, runner 1 CPU quota /
  512 MiB. These are quotas, not dedicated cores. Record the actual power condition and
  avoid other measurement runs or heavy host work at the same time.
- Query cache is OFF, strict/no-substitution mode is set, and session MEMORY maximum
  table size is 128 MiB. Engine cache sizes and durability settings are recorded, not equalized.
- Tables are fresh each trial but the server and its volume are reused. Engine/OS cache,
  prior trials, MyRocks background work and host scheduling remain possible influences.
- These are warm-read completion times, not cold-cache, physical-disk-size, steady-state
  compression or crash-recovery measurements. The row count may fit in caches.
- Keep these findings separate from the synthetic baseline: the schema, data size and
  distributions differ. Timing differences between datasets cannot be attributed to engine
  behavior alone. Final recommendations must state which measured workload supports them.

## Why keep the synthetic dataset?

OpenFlights routes describe a reference network. The nine route fields do not contain
event timestamps, measured delays, fares, passenger counts, an update stream or a record
of acknowledged commits. The seeded event dataset complements this with controlled
update/hotspot distributions and exact post-crash expectations. Its artificial high-entropy
payload and scale are explicit limitations, not claims about real airline traffic.
OpenFlights covers real reference-data distribution and strings; synthetic experiments
isolate concurrency and failure behavior. Neither alone supports all production workloads.

## Run one command at a time

On the host, from the repository root, with Docker Desktop's Linux engine running:

```powershell
python scripts/fetch_openflights.py
docker compose build runner
docker compose run --rm --no-deps runner python -m unittest discover -s tests -v
docker compose up -d --wait db
docker compose run --rm runner python -m benchmarks.openflights --pilot --power-condition "plugged in; battery saver off"
```

The fetcher is standard-library Python; a verified existing file works offline.
The runner image copies the downloaded file, and the benchmark verifies it again before
connecting. Rebuild the runner after downloading. On a fresh checkout, follow the README's
credential/setup steps and build both db and runner first; keep an existing `.env` unchanged.

Review the pilot's raw results and summary before the full run:

```powershell
docker compose run --rm runner python -m benchmarks.openflights --full --power-condition "plugged in; battery saver off"
```

Replace the power description if your actual settings differ. Results are written under
`results/<timestamp>-openflights-<id>/`. Archive reviewed evidence separately before final
recommendations. Do not report the local unit-test fixtures as real engine measurements.

## Failure behavior

Only DB_NAME=engine_lab is accepted. The existing shared experiment advisory lock prevents
cooperating harnesses from overlapping on that server. An existing openflights_routes table
is refused before CREATE/INSERT/DROP; successful trials remove only their own verified table.
A failed or interrupted trial preserves its table for inspection and writes a failed checkpoint
without a success summary. Inspect that table and partial results before retrying; never
delete the database volume to clear an error. This harness never issues crash commands.

Remaining validation: real Docker pilot, repeated full run, evidence review and findings.
OpenFlights integration alone does not complete CI, fresh-checkout reproduction, image pinning,
workload recommendations, team contributions or the final reviewed merge to main.
