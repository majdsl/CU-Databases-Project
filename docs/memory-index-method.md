# MEMORY: HASH versus BTREE

Status: October 16 laptop pilot and full run are archived and validated. The full
run has 24 trials; see [findings and charts](memory-index-findings.md).
[CI run 38830141972](https://github.com/majdsl/CU-Databases-Project/actions/runs/38830141972)
passed 94 unit tests, five-engine checks and the real MEMORY index smoke at commit
`8d2a8f4`. Do not treat CI smoke timings as benchmark evidence.

## Question and controlled change

Does changing only a MEMORY secondary index alter the access path and elapsed time for
equality versus range queries? MariaDB supports both HASH and BTREE on MEMORY; HASH
supports equality access, whereas BTREE can support ranges. We test that mechanism
with observed plans and session row-access counters, without assuming a timing winner.

Both variants use the same fixed SQL schema:

```sql
CREATE TABLE memory_index_probe (
  id INT NOT NULL,
  k INT NOT NULL,
  v INT NOT NULL,
  PRIMARY KEY (id) USING BTREE,
  KEY probe_k (k) USING HASH
) ENGINE=MEMORY;
```

The alternative changes only the last `HASH` to `BTREE`. The primary key remains
BTREE. `id` preserves insertion order and enables complete row verification; `k`
is a seeded permutation of 1..N, avoiding correlation with insertion order. Each
key occurs once, although the secondary index is declared nonunique in both cases.
`v=(id*17)%1009` is a nonindexed payload: summing it requires matching row values,
not merely counting index entries. This is synthetic diagnostic data, not flights.

Each query returns `COUNT(*)` and `COALESCE(SUM(v),0)`. Equality returns one row's
contribution; inclusive ranges return exactly 10 or 1,000 rows. Python independently
calculates every expected answer. Values are parameterized. No optimizer hints or
forced indexes are used: the optimizer's actual choice is part of the observation.

## Protocol

- Sizes: 10,000 and 100,000 rows. The same generated dataset is used in every trial
  for a size. This is a warm RAM-index experiment, not an out-of-memory test.
- Full: six rounds per size, two variants per round, 24 table trials total.
  HASH runs first three times and BTREE first three times at each size. Size order
  alternates each round. Schedule is deterministic and recorded, not random allocation.
- Pilot: one round per size, four trials. It checks correctness only; no variability
  estimate or performance conclusion is justified.
- Full: 100 queries per workload per trial; pilot: 20. Query streams vary by round
  but are identical within each size/round pair. Six trial means are the statistical
  units; summary reports mean and sample SD, never pooled-query uncertainty.
- Each trial creates a fresh table, checks actual MEMORY engine and both index types,
  loads in batches of 500, and reads back every row in primary-key order. The verified
  dataset hash is saved. Full verification warms the table; each workload also receives
  up to five warmup queries before timing.
- Workload order is always equality, range 10, range 1,000 for both variants. This
  fixed order is a limitation. Single client, reused server, fixed session settings:
  128 MiB `max_heap_table_size`, query cache off, strict mode and no substitution.
- Loading time is saved separately. Query timing includes execution and result fetch,
  driver and network overhead. Python answer checking follows the timed interval.
- After each workload, capture EXPLAIN with named fields and replay its first query
  separately between two `SHOW SESSION STATUS` snapshots. Save `Handler_read_*`
  deltas. These are logical handler requests, not CPU time, disk reads or rows returned;
  status observation can have overhead. They are not part of the timed query samples.
- Record actual DDL, indexes, query parameters/answers, table status, runtime,
  server/session variables and source hashes. Engine-reported table bytes are not
  process RSS. No server-only latency or total-memory claim is made.

Inspect whether the range plan uses `probe_k` and how handler requests scale with
N and selectivity. HASH may scan the table for a range; the optimizer may also
choose a scan for a broad BTREE range. Do not label a plan an index range scan solely
because the DDL contains BTREE. Equality timings may be dominated by client overhead.
The 1,000-row range is 10% at 10k and 1% at 100k; report those selectivities, not a
constant-percentage scaling claim. Duplicate-heavy keys, writes, concurrency,
composite-prefix access, sorting and memory exhaustion are outside this experiment.

## Run on the laptop

Finish setup first. Do not run another benchmark at the same time. Keep the power
conditions stable and replace the label with the actual conditions.

```powershell
docker compose build runner
docker compose run --rm runner python -m benchmarks.memory_indexes --pilot --power-condition "plugged in; battery saver off"
```

Read `results/<run-id>/summary.md` and preserve `results.json`. Review all four trials,
actual index types, verified row counts, plans and handler deltas before proceeding:

```powershell
docker compose run --rm runner python -m benchmarks.memory_indexes --full --power-condition "plugged in; battery saver off"
```

For a new run, inspect the full evidence before drawing conclusions. Keep pilot
and full runs separate. This command uses the existing dedicated `engine_lab` database
and the shared benchmark lock. A pre-existing `memory_index_probe` table is never
modified. Successful trial tables are dropped; failed tables and partial results are
retained. Inspect the failure before retrying; never delete the database volume.
No server restart or crash is performed.

CI runs `--smoke --power-condition CI-correctness-only` on its disposable database:
1,000/2,000 rows, two rounds, three queries per workload. This exercises the real SQL,
actual index checks, integrity validation and output path. Its timings are explicitly
not performance evidence. Unit tests cover known answers, boundaries, schedule balance,
index substitution, pre-existing tables, corrupt data, counter resets and incomplete
report rejection.

References: [MEMORY](https://mariadb.com/docs/server/server-usage/storage-engines/memory-storage-engine),
[index types](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/optimization-and-indexes/storage-engine-index-types).
