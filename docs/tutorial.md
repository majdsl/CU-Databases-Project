# Hands-on: one table, five storage engines (about 15 minutes)

This walkthrough lets you *see* the trade-offs our experiments measured, using nothing but SQL. You will create the same table on InnoDB, Aria, MyISAM, MEMORY and MyRocks, inspect what each engine reports, watch a HASH index fall back to a full scan, make Aria's table lock show up in a server counter, and restart the server to empty a MEMORY table.

It is a demonstration, not a benchmark: single runs, one laptop, no controls. For measured results, follow the links at the end of each step.

All SQL is in [`sql/tutorial/`](../sql/tutorial/). It creates only tables named `tut_*` and one procedure, `tut_hammer`, and [`99-cleanup.sql`](../sql/tutorial/99-cleanup.sql) removes them.
The `CREATE OR REPLACE` examples reset any existing objects with these names. Use the
lab database and reserve this prefix for the tutorial; do not use it on other data.

> Do not run this while a benchmark is running: it shares the lab database, and step 6 restarts the server.

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

The MyRocks package is only built for amd64, so this path skips MyRocks. Generate a throwaway password, then start a disposable server with no published port.

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
docker run -d --name engine-tutorial -e MARIADB_RANDOM_ROOT_PASSWORD=1 -e MARIADB_DATABASE=engine_lab -e MARIADB_USER=tutorial -e MARIADB_PASSWORD -v "${PWD}/sql/tutorial:/tutorial:ro" mariadb:11.8
docker exec -it engine-tutorial sh -c 'export MYSQL_PWD=$MARIADB_PASSWORD; exec mariadb --abort-source-on-error -ututorial engine_lab'
```

If the client reports that it cannot connect, wait a few seconds for the server to finish initialising and try again. In Path B, skip step 2 and the two MyRocks-only follow-ups (`03b` and `06b`).
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

This creates `tut_hammer(engine, row_id, seconds)`, which updates **one row** as fast as it can for the given number of seconds, then prints the number of affected-row updates and the observed elapsed time. Invalid parameters
and a nonexistent row are rejected; loop iterations that changed no row are not counted
as successful writes. The last line shows two server counters. Write down `Table_locks_waited`.

**5a. Aria, two sessions, different rows.** Open a second terminal with the same connect command from step 0. Start these within a few seconds of each other:

```sql
-- terminal 1
CALL tut_hammer('aria', 1, 15);
-- terminal 2
CALL tut_hammer('aria', 2, 15);
```

When both finish, read the counters again:

```sql
SHOW GLOBAL STATUS WHERE Variable_name IN ('Table_locks_waited', 'Innodb_row_lock_waits');
```

`Table_locks_waited` should have jumped by a large amount. The two sessions touched **different rows**, but Aria locks the whole table for each update, so they queued behind each other.

**5b. InnoDB, same experiment.**

```sql
-- terminal 1
CALL tut_hammer('innodb', 1, 15);
-- terminal 2
CALL tut_hammer('innodb', 2, 15);
```

`Table_locks_waited` should barely move, and `Innodb_row_lock_waits` should stay near zero. For these primary-key updates, row-level locking permits disjoint writers to proceed.
Zero observed waits in this demo does not rule out other internal, metadata or
range-lock contention in different workloads.

**Try it yourself:** run `CALL tut_hammer('aria', 1, 5);` alone and compare its `updates_per_second` with the concurrent runs. Then point both InnoDB sessions at row 1 and see whether `Innodb_row_lock_waits` moves. MyISAM (`'myisam'`) also uses table locks.

**Measured version:** [write-diagnostics findings](write-diagnostics-findings.md). Across 150 controlled trials, Aria recorded almost one table-lock wait per update with two or four clients, even on disjoint rows, while InnoDB recorded none.

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

Path B: also remove the disposable server with `docker rm -f engine-tutorial`.

## What you just saw, and what to choose

| You saw | Because | So |
| --- | --- | --- |
| Identical SQL on every engine | Storage is chosen per table with `ENGINE=` | You can choose per table, not per database |
| Aria writers can queue on different rows | Table-level locks | Test a row-locking engine for frequent concurrent updates; include durability requirements |
| Disjoint InnoDB primary-key updates proceed in this example | Row-level locks and transactions | Starting point for transactional application data; measure the actual workload |
| HASH range reads the whole table | A hash has no order | Use `USING BTREE` on MEMORY when you query ranges |
| MEMORY empty after a clean restart | Rows live only in RAM | Use it only for rebuildable caches |

The [engine recommendations](engine-recommendations.md) turn these observations, together with the measured costs, into a decision guide.

## Validation and boundaries

The correctness workflow uses `scripts/check_tutorial.py` to run the actual source
files against its disposable MariaDB server. It checks engine identities, generated
row counts, index answers/access plans, concurrent increment totals, invalid routine
inputs, clean-restart row survival and cleanup. It exercises the five-engine sequence
and the common four-engine sequence without creating a MyRocks table.

This is automated **Linux amd64 SQL correctness**, not new performance evidence or
a claim that the PowerShell walkthrough, native ARM or another person's Windows
checkout has been independently reproduced. The four-engine SQL path is also checked
on amd64; that does not validate an ARM host. The custom five-engine image remains
verified only on amd64. A manual test transcript should record its commit, server
version, platform, commands and outputs separately. See [CI scope](ci.md) and the
[team contributions](team-contributions.md).

The [October 26 automated validation record](../evidence/reviews/20261026-tutorial-ci/README.md)
archives the successful SQL checks, tested commit and source hashes. Its counts and
timings are correctness observations, not additional performance measurements.
