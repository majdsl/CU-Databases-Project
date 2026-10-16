# Cache and durability settings

These are recorded settings, not an equal-memory or equal-durability comparison.
The source is the full October 9 OpenFlights run's [raw results](../evidence/openflights/20261009T160813Z-openflights-6884f225/results.json),
under `global_variables` and `session_variables`. Do not assume this snapshot
describes every historical experiment.

| Feature | Recorded setting | Meaning |
| --- | --- | --- |
| InnoDB | `innodb_buffer_pool_size=134217728` | 128 MiB for data and index pages |
| Aria | `aria_pagecache_buffer_size=134217728` | 128 MiB page cache |
| MyISAM | `key_buffer_size=134217728` | 128 MiB index cache; does not budget OS data-file caching |
| MyRocks | `rocksdb_block_cache_size=134217728` | 128 MiB block cache, not all engine memory |
| MEMORY | Global `max_heap_table_size=16777216`; session `134217728` | Default 16 MiB; benchmark session table limit 128 MiB, not allocated RAM |
| Query cache | `query_cache_type=OFF`, `query_cache_size=0` | Query-result caching disabled |
| Temporary tables | `tmp_table_size=16777216`, `aria_used_for_temp_tables=ON` | Separate from the explicitly selected benchmark table engine |

Equal named cache limits do not mean equal total memory: the caches serve different
purposes and do not measure occupancy or OS caching. The MEMORY session limit is
applied before table creation. Its allocation is measured separately in the
[storage findings](storage-findings.md), using a different synthetic workload.
The database had container limits of 2 CPUs and 2 GiB; the runner had 1 CPU and
512 MiB. These are limits, not dedicated physical cores or per-engine memory budgets.
See the [environment record](benchmark-environment.md).

## Persistence and transaction settings

| Setting | Recorded value | Interpretation |
| --- | --- | --- |
| `innodb_flush_log_at_trx_commit` | `1` | InnoDB commit-flush configuration, not a power-loss test |
| `rocksdb_flush_log_at_trx_commit` | `1` | MyRocks commit-flush configuration, not equivalent total write cost |
| `autocommit` | `ON` | Automatic statement commits where transactions are supported |
| `tx_isolation` | `REPEATABLE-READ` | Does not make nontransactional engines transactional |
| `log_bin` / `binlog_format` / `sync_binlog` | `OFF` / `ROW` / `0` | Binary logging was disabled despite the ROW format setting |
| `innodb_file_per_table` | `ON` | Per-table InnoDB tablespaces enabled |
| `aria_recover_options` | `BACKUP,QUICK` | Recovery configuration, not a successful-recovery guarantee |
| `sql_mode` | `STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION` | Strict data handling and no silent engine fallback |

Autocommit does not make Aria or MyISAM transactional. MEMORY rows do not survive
server restarts. The separate [recovery experiment](recovery-findings.md) interrupted
the process between acknowledged statements, not during an open transaction or host
power failure. Its results do not equalize the persistence costs in this benchmark.

## Interpretation and next experiments

These results compare the recorded configurations on 67,663 historical routes.
Reads were warmed on a reused server. Timings include driver and network work;
server-only latency and client overhead were not separately measured.
No cold-cache, equal-durability, equal-total-memory or steady-state claim is made.
Small lookup differences are not general engine rankings.

A future mechanism experiment should change one setting, verify identical answers,
record plans and settings, and repeat balanced trials. The [MEMORY HASH-versus-BTREE harness](memory-index-method.md) now implements
equality and range access; [verified laptop findings](memory-index-findings.md) now
show the observed plans, counters and timing differences. Larger working sets and sustained
writes need additional cache and compaction observations. These are proposed
extensions, not completed evidence.

References: [InnoDB buffer pool](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-buffer-pool),
[MyISAM key buffer](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/system-variables/optimizing-key_buffer_size),
[Aria](https://mariadb.com/docs/server/server-usage/storage-engines/aria/aria-storage-engine),
[OpenFlights method](openflights-method.md), [recommendations](engine-recommendations.md).
