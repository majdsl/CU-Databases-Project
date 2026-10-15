# Concurrent update results

Run: 20260929T082232Z-writes-75f6c965

Fixed total updates per trial; autocommit; warm data; no automatic retries.
Throughput includes worker scheduling and server/client overhead. Durability is not equivalent.

| Engine | Pattern | Clients | Trials | Mean updates/s | Sample SD |
| --- | --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 5 | 400.67 | 29.84 |
| InnoDB | disjoint | 2 | 5 | 534.55 | 19.71 |
| InnoDB | disjoint | 4 | 5 | 994.12 | 80.34 |
| InnoDB | hotspot | 1 | 5 | 404.02 | 24.95 |
| InnoDB | hotspot | 2 | 5 | 530.11 | 27.33 |
| InnoDB | hotspot | 4 | 5 | 1001.61 | 73.84 |
| Aria | disjoint | 1 | 5 | 346.86 | 106.30 |
| Aria | disjoint | 2 | 5 | 439.53 | 137.67 |
| Aria | disjoint | 4 | 5 | 493.86 | 12.29 |
| Aria | hotspot | 1 | 5 | 382.86 | 51.46 |
| Aria | hotspot | 2 | 5 | 475.40 | 60.60 |
| Aria | hotspot | 4 | 5 | 476.50 | 59.47 |
| MyISAM | disjoint | 1 | 5 | 1770.38 | 17.92 |
| MyISAM | disjoint | 2 | 5 | 3581.34 | 133.56 |
| MyISAM | disjoint | 4 | 5 | 1571.64 | 59.36 |
| MyISAM | hotspot | 1 | 5 | 1759.15 | 30.63 |
| MyISAM | hotspot | 2 | 5 | 3555.59 | 93.24 |
| MyISAM | hotspot | 4 | 5 | 1614.47 | 35.86 |
| MEMORY | disjoint | 1 | 5 | 1868.79 | 45.32 |
| MEMORY | disjoint | 2 | 5 | 3613.99 | 162.35 |
| MEMORY | disjoint | 4 | 5 | 1570.68 | 54.53 |
| MEMORY | hotspot | 1 | 5 | 1873.49 | 15.83 |
| MEMORY | hotspot | 2 | 5 | 3691.61 | 153.73 |
| MEMORY | hotspot | 4 | 5 | 1566.47 | 35.65 |
| ROCKSDB | disjoint | 1 | 5 | 198.93 | 15.51 |
| ROCKSDB | disjoint | 2 | 5 | 211.49 | 41.33 |
| ROCKSDB | disjoint | 4 | 5 | 439.75 | 50.32 |
| ROCKSDB | hotspot | 1 | 5 | 196.26 | 23.46 |
| ROCKSDB | hotspot | 2 | 5 | 216.94 | 30.60 |
| ROCKSDB | hotspot | 4 | 5 | 436.56 | 49.54 |

## Runner CPU diagnostics

Window includes worker setup and teardown; it differs from the throughput interval.
Average cores is CPU seconds / wall seconds, not a percentage of the whole machine.
These counters cover the runner only, not MariaDB or the Windows host.

| Engine | Pattern | Clients | Mean runner cores | Trials with throttling / observed |
| --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 0.106 | 0/5 |
| InnoDB | disjoint | 2 | 0.152 | 1/5 |
| InnoDB | disjoint | 4 | 0.409 | 5/5 |
| InnoDB | hotspot | 1 | 0.108 | 0/5 |
| InnoDB | hotspot | 2 | 0.152 | 1/5 |
| InnoDB | hotspot | 4 | 0.402 | 2/5 |
| Aria | disjoint | 1 | 0.093 | 0/5 |
| Aria | disjoint | 2 | 0.130 | 1/5 |
| Aria | disjoint | 4 | 0.158 | 1/5 |
| Aria | hotspot | 1 | 0.103 | 0/5 |
| Aria | hotspot | 2 | 0.141 | 0/5 |
| Aria | hotspot | 4 | 0.151 | 2/5 |
| MyISAM | disjoint | 1 | 0.438 | 0/5 |
| MyISAM | disjoint | 2 | 0.927 | 3/5 |
| MyISAM | disjoint | 4 | 1.034 | 5/5 |
| MyISAM | hotspot | 1 | 0.442 | 0/5 |
| MyISAM | hotspot | 2 | 0.910 | 2/5 |
| MyISAM | hotspot | 4 | 1.031 | 5/5 |
| MEMORY | disjoint | 1 | 0.477 | 1/5 |
| MEMORY | disjoint | 2 | 0.974 | 5/5 |
| MEMORY | disjoint | 4 | 1.030 | 5/5 |
| MEMORY | hotspot | 1 | 0.470 | 1/5 |
| MEMORY | hotspot | 2 | 0.974 | 5/5 |
| MEMORY | hotspot | 4 | 1.030 | 5/5 |
| ROCKSDB | disjoint | 1 | 0.056 | 1/5 |
| ROCKSDB | disjoint | 2 | 0.064 | 0/5 |
| ROCKSDB | disjoint | 4 | 0.204 | 2/5 |
| ROCKSDB | hotspot | 1 | 0.054 | 0/5 |
| ROCKSDB | hotspot | 2 | 0.067 | 1/5 |
| ROCKSDB | hotspot | 4 | 0.193 | 0/5 |
