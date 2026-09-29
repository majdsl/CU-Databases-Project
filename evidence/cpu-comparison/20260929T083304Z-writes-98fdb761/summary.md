# Concurrent update results

Run: 20260929T083304Z-writes-98fdb761

Fixed total updates per trial; autocommit; warm data; no automatic retries.
Throughput includes worker scheduling and server/client overhead. Durability is not equivalent.

| Engine | Pattern | Clients | Trials | Mean updates/s | Sample SD |
| --- | --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 5 | 411.09 | 8.34 |
| InnoDB | disjoint | 2 | 5 | 560.63 | 12.34 |
| InnoDB | disjoint | 4 | 5 | 1087.67 | 19.07 |
| InnoDB | hotspot | 1 | 5 | 421.13 | 6.65 |
| InnoDB | hotspot | 2 | 5 | 563.85 | 9.31 |
| InnoDB | hotspot | 4 | 5 | 1087.05 | 28.38 |
| Aria | disjoint | 1 | 5 | 409.29 | 9.31 |
| Aria | disjoint | 2 | 5 | 506.70 | 11.96 |
| Aria | disjoint | 4 | 5 | 490.20 | 8.83 |
| Aria | hotspot | 1 | 5 | 410.61 | 6.92 |
| Aria | hotspot | 2 | 5 | 498.79 | 19.36 |
| Aria | hotspot | 4 | 5 | 499.37 | 2.56 |
| MyISAM | disjoint | 1 | 5 | 1759.84 | 43.04 |
| MyISAM | disjoint | 2 | 5 | 3494.40 | 76.49 |
| MyISAM | disjoint | 4 | 5 | 2536.15 | 49.75 |
| MyISAM | hotspot | 1 | 5 | 1728.60 | 20.88 |
| MyISAM | hotspot | 2 | 5 | 3641.39 | 216.88 |
| MyISAM | hotspot | 4 | 5 | 2496.51 | 48.97 |
| MEMORY | disjoint | 1 | 5 | 1854.53 | 35.49 |
| MEMORY | disjoint | 2 | 5 | 3716.78 | 120.54 |
| MEMORY | disjoint | 4 | 5 | 2429.71 | 99.95 |
| MEMORY | hotspot | 1 | 5 | 1861.76 | 28.71 |
| MEMORY | hotspot | 2 | 5 | 3783.89 | 142.29 |
| MEMORY | hotspot | 4 | 5 | 2429.39 | 70.73 |
| ROCKSDB | disjoint | 1 | 5 | 210.15 | 6.59 |
| ROCKSDB | disjoint | 2 | 5 | 232.41 | 8.29 |
| ROCKSDB | disjoint | 4 | 5 | 454.07 | 12.98 |
| ROCKSDB | hotspot | 1 | 5 | 203.00 | 7.75 |
| ROCKSDB | hotspot | 2 | 5 | 235.92 | 7.36 |
| ROCKSDB | hotspot | 4 | 5 | 464.48 | 6.73 |

## Runner CPU diagnostics

Window includes worker setup and teardown; it differs from the throughput interval.
Average cores is CPU seconds / wall seconds, not a percentage of the whole machine.
These counters cover the runner only, not MariaDB or the Windows host.

| Engine | Pattern | Clients | Mean runner cores | Trials with throttling / observed |
| --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 0.112 | 0/5 |
| InnoDB | disjoint | 2 | 0.162 | 0/5 |
| InnoDB | disjoint | 4 | 0.454 | 0/5 |
| InnoDB | hotspot | 1 | 0.114 | 0/5 |
| InnoDB | hotspot | 2 | 0.163 | 0/5 |
| InnoDB | hotspot | 4 | 0.423 | 0/5 |
| Aria | disjoint | 1 | 0.110 | 0/5 |
| Aria | disjoint | 2 | 0.148 | 0/5 |
| Aria | disjoint | 4 | 0.157 | 0/5 |
| Aria | hotspot | 1 | 0.111 | 0/5 |
| Aria | hotspot | 2 | 0.145 | 0/5 |
| Aria | hotspot | 4 | 0.159 | 0/5 |
| MyISAM | disjoint | 1 | 0.444 | 0/5 |
| MyISAM | disjoint | 2 | 0.915 | 0/5 |
| MyISAM | disjoint | 4 | 1.631 | 0/5 |
| MyISAM | hotspot | 1 | 0.443 | 0/5 |
| MyISAM | hotspot | 2 | 0.934 | 0/5 |
| MyISAM | hotspot | 4 | 1.622 | 0/5 |
| MEMORY | disjoint | 1 | 0.471 | 0/5 |
| MEMORY | disjoint | 2 | 0.996 | 0/5 |
| MEMORY | disjoint | 4 | 1.640 | 0/5 |
| MEMORY | hotspot | 1 | 0.468 | 0/5 |
| MEMORY | hotspot | 2 | 1.020 | 0/5 |
| MEMORY | hotspot | 4 | 1.623 | 0/5 |
| ROCKSDB | disjoint | 1 | 0.059 | 0/5 |
| ROCKSDB | disjoint | 2 | 0.071 | 0/5 |
| ROCKSDB | disjoint | 4 | 0.205 | 0/5 |
| ROCKSDB | hotspot | 1 | 0.057 | 0/5 |
| ROCKSDB | hotspot | 2 | 0.072 | 0/5 |
| ROCKSDB | hotspot | 4 | 0.213 | 0/5 |
