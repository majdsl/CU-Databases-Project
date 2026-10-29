# Hands-on: one table, five storage engines (about 15 minutes)

This walkthrough lets you *see* the trade-offs our experiments measured, using nothing but SQL. You will create the same table on InnoDB, Aria, MyISAM, MEMORY and MyRocks, inspect what each engine reports, watch a HASH index fall back to a full scan, inspect per-case lock counters, compare COMMIT/ROLLBACK guarantees, and restart the server to empty a MEMORY table.

It is a demonstration, not a benchmark: single runs, one laptop, no controls. For measured results, follow the links at the end of each step.

All SQL is in [`sql/tutorial/`](../sql/tutorial/). It creates only tables named `tut_*` and one procedure, `tut_hammer`, and [`99-cleanup.sql`](../sql/tutorial/99-cleanup.sql) removes them.
The `CREATE OR REPLACE` examples reset any existing objects with these names. Use the
lab database and reserve this prefix for the tutorial; do not use it on other data.

> Run this separately from performance measurements. Path A uses the lab database
> and restarts it; Path B creates a separate stock server that still consumes host resources.

## 0. Start a MariaDB client

### Path A: the project's five-engine lab (Linux amd64 Docker)

After `python scripts/setup_project.py` has printed `SETUP PASS`, run this from the repository root (PowerShell or bash):

```powershell
docker compose up -d --wait db
docker compose exec db mkdir -p /tutorial
docker compose cp sql/tutorial/. db:/tutorial/
docker compose exec db sh -c 'export MYSQL_PWD=$MARIADB_PASSWORD; exec mariadb --abort-source-on-error -ubenchmark engine_lab'
```

The password comes from the container's own environment (generated earlier into your `.env`), so nothing is typed or stored in the repository. To open a **second terminal** later, run the last command again.

### Path B: ARM laptops or a quick try (stock image, four engines)

**Validated October 27, 2026:** the automated stock-image path passed on native
Linux amd64 and ARM64 CI runners and from Windows PowerShell with Docker Desktop's
WSL2 Linux amd64 engine, using MariaDB 11.8.9 and the six common SQL files present in that historical revision. The transaction lesson below extends the current file sequence.
The [validation record](stock-tutorial-validation.md) includes commands, image IDs,
source hashes, restart results and cleanup. This covers four engines; MyRocks is
part of Path A. The Windows record covers the Python CLI; interactive SQL walkthroughs
and macOS shell reproduction remain separate.

For an automated check from a clean checkout, with Python 3.9+ and running Docker
Linux containers, run from the repository root:

```powershell
python scripts/check_stock_tutorial.py
```

On Linux use `python3`. The command generates temporary credentials, creates its
own unused container and volume, waits for health, runs the tutorial checks and
removes only those owned resources. It saves `validation.json`, `commands.json`
and `transcript.txt` under a new `results/` directory and ends with
`STOCK TUTORIAL PASS`. It does not read or change the lab's `.env`.

To work through the SQL interactively instead, use the following manual setup.

The custom five-engine image is verified only on amd64, so this path skips MyRocks. Generate a throwaway password, then start a disposable server with no published port.

PowerShell:

```powershell
$env:MARIADB_PASSWORD = python -c "import secrets; print(secrets.token_hex(16))"
```

bash:

```bash
export MARIADB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))")
```

Then (either shell):

```powershell
docker run -d --name engine-tutorial --network none -e MARIADB_RANDOM_ROOT_PASSWORD=1 -e MARIADB_DATABASE=engine_lab -e MARIADB_USER=tutorial -e MARIADB_PASSWORD -v "${PWD}/sql/tutorial:/tutorial:ro" mariadb@sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112
docker exec engine-tutorial healthcheck.sh --connect --innodb_initialized
docker exec -it engine-tutorial sh -c 'export MYSQL_PWD=$MARIADB_PASSWORD; exec mariadb --abort-source-on-error -ututorial engine_lab'
```

Run these commands separately. If the healthcheck fails while initialization is
still in progress, wait a few seconds and repeat it; connect only after it succeeds.
An existing `engine-tutorial` name must be inspected before proceeding; do not reuse
an unrelated server. In Path B, skip step 2 and the MyRocks-only follow-ups (`03b`, `05c` and `06b`).
The common scripts run without expected errors. Stop and inspect any SQL error; do not continue past it.

## 1. The same table on four engines

```sql
source /tutorial/01-create-tables.sql
```

Each `CREATE TABLE` is identical except for `ENGINE=`. Rows come from MariaDB's built-in [SEQUENCE engine](https://mariadb.com/docs/server/server-usage/storage-engines/sequence-storage-engine): `seq_1_to_50000` is a virtual table, so no data file is needed. The client prints how long each `INSERT` took. The final query should show 50,000 rows in every table.

**What to notice:** the SQL you write does not change. Only the storage underneath does. MEMORY needed one extra line, `SET SESSION max_heap_table_size`, because its tables are capped in RAM.

## 2. Add MyRocks (Path A only)

```sql
source /tutorial/02-myrocks.sql
```

MyRocks is a plugin that this project's image installs and loads ([`docker/mariadb/`](../docker/mariadb/)). The SQL is the same again; only the engine name is `ROCKSDB`.

## 3. Same rows, different self-descriptions

```sql
source /tutorial/03-compare.sql
```

You will likely see:

| Engine | What to look for |
| --- | --- |
| InnoDB | `TABLE_ROWS` is an **estimate**, not exactly 50,000. Data is stored in 16 KiB pages clustered by the primary key, so the footprint includes page overhead. |
| Aria | `ROW_FORMAT` is `Page`. `SHOW CREATE TABLE` adds options you never wrote, such as `PAGE_CHECKSUM`. These belong to Aria's crash-safe format. |
| MyISAM | Exact row count, separate data and index files, `Dynamic` rows because of the `VARCHAR`. |
| MEMORY | `Fixed` rows: every `VARCHAR` occupies its full width in RAM. `data_mib` is RAM allocated, not disk. |
| ROCKSDB | `Data_length` and `Index_length` may show **0**. These metadata fields are not a reliable disk-footprint measurement for this setup: our [storage findings](storage-findings.md) recorded zero **despite existing SST files**. Zero does not establish that data has not reached disk; inspect engine/filesystem evidence instead. |

The common file scans the four common engines. On **Path A**, complete the fifth scan:

```sql
source /tutorial/03b-myrocks-compare.sql
```

Compare the client times as observations from this demonstration, not a ranking.

**Measured version:** [OpenFlights findings](openflights-findings.md) (67,663 real routes, 25 trials).

## 4. Why MEMORY's index type matters

```sql
source /tutorial/04-index-types.sql
```

[`ANALYZE SELECT`](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/analyze-and-explain-statements/analyze-statement) runs the query and reports what really happened. Compare two columns:

| Query | BTREE index | HASH index |
| --- | --- | --- |
| `airport_id = 100` | `type=ref`, `r_rows` about 20 | `type=ref`, `r_rows` about 20 |
| `airport_id BETWEEN 100 AND 109` | `type=range`, `r_rows` about 200 | `type=ALL`, `r_rows` about **100,000** |

A hash can find one value, but it cannot be walked in order, so the range query has to read the whole table. MEMORY creates HASH indexes **by default**, which is why the project's shared schemas say `USING BTREE` explicitly.

**Measured version:** [MEMORY index findings](memory-index-findings.md). HASH ranges were up to 13.5 times slower at 100,000 rows, with handler counters confirming the full scans.

## 5. See table-level locking happen

```sql
source /tutorial/05-lock-demo.sql
```

This creates `tut_hammer(engine, row_id, seconds)`, which updates **one row** as fast as it can for the given number of seconds, then prints the number of affected-row updates, elapsed time, and server-side procedure start/finish timestamps with microsecond precision. Invalid parameters
and a nonexistent row are rejected; loop iterations that changed no row are not counted
as successful writes. The last line shows two server counters. Write down `Table_locks_waited`.

**5a. Aria, two sessions, different rows.** Open a second terminal with the same connect command from step 0. Wait until **both sessions are connected and ready**, then start the two calls
as close together as possible. The 30-second duration gives more opportunity for
overlap; it does not synchronize or guarantee it. Record the counters before and
after both calls finish:

```sql
-- terminal 1
CALL tut_hammer('aria', 1, 30);
-- terminal 2
CALL tut_hammer('aria', 2, 30);
```

When both finish, read the counters again:

```sql
SHOW GLOBAL STATUS WHERE Variable_name IN ('Table_locks_waited', 'Innodb_row_lock_waits');
```

`Table_locks_waited` may increase when the SQL execution windows overlap. The two sessions touched **different rows**, but Aria locks the whole table for each update, so they queued behind each other.

**5b. InnoDB, same experiment.** Again, ready both sessions and start together.

```sql
-- terminal 1
CALL tut_hammer('innodb', 1, 30);
-- terminal 2
CALL tut_hammer('innodb', 2, 30);
```

Compare the counter deltas with Aria rather than treating a particular wait count as a required result. Disjoint InnoDB writers can finish with no recorded row-lock waits. For these primary-key updates, row-level locking permits disjoint writers to proceed.
Zero observed waits in this demo does not rule out other internal, metadata or
range-lock contention in different workloads.

**Try it yourself:** run `CALL tut_hammer('aria', 1, 5);` alone and compare its `updates_per_second` with the concurrent runs. Then point both InnoDB sessions at row 1 and see whether `Innodb_row_lock_waits` moves. MyISAM (`'myisam'`) also uses table locks.

**Measured version:** [write-diagnostics findings](write-diagnostics-findings.md). Across 150 controlled trials, Aria recorded almost one table-lock wait per update with two or four clients, even on disjoint rows, while InnoDB recorded none.

### 5c. COMMIT and ROLLBACK depend on the engine

In the same client, run:

```sql
source /tutorial/05b-transactions.sql
```

On **Path A**, also run:

```sql
source /tutorial/05c-myrocks-transactions.sql
```

The scripts create separate two-row `tut_tx_*` tables with balances 100/100. Each
engine receives the same statements: begin, add 25 to one row, subtract 25 from
the other, and roll back. A second transfer starts from a reset baseline and commits.
The scripts refuse an existing transaction-demo table and remove their own tables
when finished. Step7's cleanup also removes these reserved names after an interrupted run.

| Observation | InnoDB / MyRocks | Aria / MyISAM / MEMORY |
| --- | --- | --- |
| Before the transfer | `1:100,2:100` | `1:100,2:100` |
| Inside the transaction | `1:125,2:75` | `1:125,2:75` |
| After `ROLLBACK` | `1:100,2:100` | `1:125,2:75` |
| After the separate `COMMIT` example | `1:125,2:75` | `1:125,2:75` |

Nontransactional engines can produce warning1196 on `ROLLBACK`: their writes cannot
be rolled back. This is the behavior being demonstrated, not an expected SQL error.
Aria's crash-safe `TRANSACTIONAL` option does not provide multi-statement transactions.
The automated tutorial verifies actual engine identities and every row-pair outcome
from these exact source files. An invariant such as total balance200 alone would miss
the difference; the individual balances are checked.

This lesson demonstrates rollback/commit semantics in a live server. It does not
test interrupted transactions, isolation levels, foreign keys or power-loss durability,
and its client timings do not rank engines. Use a transactional engine when related
updates must roll back together; consider nontransactional data only when that
requirement is deliberately absent.

## 6. Restart the server

Leave the client (`exit`), restart the server, and reconnect.

Path A:

```powershell
docker compose restart db
docker compose up -d --wait db
docker compose exec db sh -c 'export MYSQL_PWD=$MARIADB_PASSWORD; exec mariadb --abort-source-on-error -ubenchmark engine_lab'
```

Path B:

```powershell
docker restart engine-tutorial
docker exec engine-tutorial healthcheck.sh --connect --innodb_initialized
docker exec -it engine-tutorial sh -c 'export MYSQL_PWD=$MARIADB_PASSWORD; exec mariadb --abort-source-on-error -ututorial engine_lab'
```

Then:

```sql
source /tutorial/06-after-restart.sql
```

On **Path A**, also run:

```sql
source /tutorial/06b-myrocks-after-restart.sql
```

Every persistent engine still has 50,000 rows, and the `hits` counters from step 5 are intact. **`tut_memory` has 0 rows**, even though this was a clean restart. Its definition survived; its data never left RAM.

**Measured version:** [recovery findings](recovery-findings.md). MEMORY was empty after all ten clean and forced restarts. The four persistent engines kept every acknowledged row, and MyISAM logged crashed-table warnings after every forced stop.

## 7. Clean up

```sql
source /tutorial/99-cleanup.sql
```

Path B's manual setup: remove only that disposable tutorial server and its anonymous
database volume with `docker rm -f -v engine-tutorial`. The automated command already
removes its own labelled container and named volume.

## What you just saw, and what to choose

| You saw | Because | So |
| --- | --- | --- |
| Identical SQL on every engine | Storage is chosen per table with `ENGINE=` | You can choose per table, not per database |
| Aria writers can queue on different rows | Table-level locks | Test a row-locking engine for frequent concurrent updates; include durability requirements |
| Disjoint InnoDB primary-key updates proceed in this example | Row-level locks and transactions | Starting point for transactional application data; measure the actual workload |
| HASH range reads the whole table | A hash has no order | Use `USING BTREE` on MEMORY when you query ranges |
| MEMORY empty after a clean restart | Rows live only in RAM | Use it only for rebuildable caches |
| A transfer rolls back on InnoDB/MyRocks, but remains on Aria/MyISAM/MEMORY | Transaction guarantees come from the engine | Require transactional tables for related updates that must roll back together |

The [engine recommendations](engine-recommendations.md) turn these observations, together with the measured costs, into a decision guide.

## When to pick which engine

| Workload or requirement | Starting choice | Main cost or condition |
| --- | --- | --- |
| Authoritative application records, atomic updates or foreign keys | **InnoDB** | Budget for its pages/logs and test the real working set and contention. |
| A reference cache that fits RAM and can be rebuilt from a durable source | **MEMORY** | Rows disappear at restart; choose BTREE for ranges and plan repopulation. |
| Persistent reference scans without application transaction requirements | **Evaluate Aria** | Table-level write contention and slower loading can matter. |
| Rebuildable batch-loaded data where load speed dominates | **Compare MyISAM with Aria** | Accept non-transactional semantics and the recovery/repair implications. |
| Persistent data where disk allocation is a constraint | **Evaluate MyRocks** | Test sustained ingestion, scan costs, compaction and required isolation before adopting it. |

These are requirements-based starting points supported by the linked project
measurements and documented features, not a ranking from this one demonstration.
The [decision guide](engine-recommendations.md) gives the full evidence and limits.

## Validation and boundaries

The correctness workflow uses `scripts/check_tutorial.py` to run the actual source
files against its disposable MariaDB server. It checks engine identities, generated
row counts, index answers/access plans, concurrent increment totals, invalid routine
inputs, exact commit/rollback outcomes, clean-restart row survival and cleanup.
Each concurrent case records parsed before/after lock counters, their nonnegative
deltas, and overlap of the two server-side procedure execution intervals. An overlap
shows both procedure calls were executing during a shared interval; it does not prove
their individual UPDATE statements held locks simultaneously. Counter magnitudes are
observations, not fixed pass thresholds or per-statement attribution. Missing/reset
counters and inconsistent timestamps fail the check. It exercises the five-engine sequence
and the common four-engine sequence without creating a MyRocks table.

Path A's automated checks cover **Linux amd64 SQL correctness** in the custom
five-engine image. Path B's separate `scripts/check_stock_tutorial.py` jobs cover
**native Linux amd64 and ARM64** using the pinned official image and four engines.
An [archived Windows run](../evidence/reviews/20261027-windows-stock-tutorial/README.md)
also validates the Python CLI with Docker Desktop/WSL2 Linux amd64 in the owner's checkout.
Both run the shared checks in `scripts/tutorial_checks.py`; Path B also verifies
image/platform identity, mounted SQL hashes, fresh startup and owned-resource removal.

These are correctness observations. They do not reproduce controlled benchmark
timings on a second laptop or validate the interactive PowerShell/macOS walkthrough.
The custom five-engine image remains verified only on amd64. A separate manual
transcript should record its commit, server version, platform, commands and outputs.
See [stock-image validation](stock-tutorial-validation.md), [CI scope](ci.md) and the
[team contributions](team-contributions.md).

The [October 26 automated validation record](../evidence/reviews/20261026-tutorial-ci/README.md)
archives the successful SQL checks, tested commit and source hashes. Its counts and
timings are correctness observations, not additional performance measurements.
