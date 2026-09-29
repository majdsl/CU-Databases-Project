# Concurrent update results

Run: 20260929T162946Z-writes-18a13d6d

Fixed total updates per trial; autocommit; warm data; no automatic retries.
Throughput includes worker scheduling and server/client overhead. Durability is not equivalent.

| Engine | Pattern | Clients | Trials | Mean updates/s | Sample SD |
| --- | --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 5 | 582.02 | 42.84 |
| InnoDB | disjoint | 2 | 5 | 754.64 | 18.43 |
| InnoDB | disjoint | 4 | 5 | 1523.62 | 32.39 |
| InnoDB | hotspot | 1 | 5 | 608.32 | 12.33 |
| InnoDB | hotspot | 2 | 5 | 765.41 | 12.36 |
| InnoDB | hotspot | 4 | 5 | 1490.89 | 40.39 |
| Aria | disjoint | 1 | 5 | 584.07 | 7.96 |
| Aria | disjoint | 2 | 5 | 702.28 | 13.39 |
| Aria | disjoint | 4 | 5 | 689.21 | 34.60 |
| Aria | hotspot | 1 | 5 | 569.30 | 52.17 |
| Aria | hotspot | 2 | 5 | 706.47 | 21.40 |
| Aria | hotspot | 4 | 5 | 704.24 | 10.91 |
| MyISAM | disjoint | 1 | 5 | 2884.29 | 23.21 |
| MyISAM | disjoint | 2 | 5 | 5423.64 | 96.08 |
| MyISAM | disjoint | 4 | 5 | 3134.82 | 59.63 |
| MyISAM | hotspot | 1 | 5 | 2868.65 | 45.75 |
| MyISAM | hotspot | 2 | 5 | 5370.83 | 188.43 |
| MyISAM | hotspot | 4 | 5 | 3143.19 | 40.39 |
| MEMORY | disjoint | 1 | 5 | 3138.03 | 124.82 |
| MEMORY | disjoint | 2 | 5 | 5715.21 | 204.48 |
| MEMORY | disjoint | 4 | 5 | 3063.37 | 55.40 |
| MEMORY | hotspot | 1 | 5 | 3164.27 | 148.89 |
| MEMORY | hotspot | 2 | 5 | 5324.09 | 713.34 |
| MEMORY | hotspot | 4 | 5 | 3138.99 | 58.31 |
| ROCKSDB | disjoint | 1 | 5 | 301.43 | 5.13 |
| ROCKSDB | disjoint | 2 | 5 | 340.54 | 21.45 |
| ROCKSDB | disjoint | 4 | 5 | 655.80 | 68.95 |
| ROCKSDB | hotspot | 1 | 5 | 302.15 | 3.11 |
| ROCKSDB | hotspot | 2 | 5 | 348.79 | 5.60 |
| ROCKSDB | hotspot | 4 | 5 | 682.81 | 22.03 |

## Runner CPU diagnostics

Window includes worker setup and teardown; it differs from the throughput interval.
Average cores is CPU seconds / wall seconds, not a percentage of the whole machine.
These counters cover the runner only, not MariaDB or the Windows host.

| Engine | Pattern | Clients | Mean runner cores | Trials with throttling / observed |
| --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 0.118 | 0/5 |
| InnoDB | disjoint | 2 | 0.162 | 0/5 |
| InnoDB | disjoint | 4 | 0.469 | 0/5 |
| InnoDB | hotspot | 1 | 0.119 | 0/5 |
| InnoDB | hotspot | 2 | 0.160 | 0/5 |
| InnoDB | hotspot | 4 | 0.481 | 0/5 |
| Aria | disjoint | 1 | 0.117 | 0/5 |
| Aria | disjoint | 2 | 0.142 | 0/5 |
| Aria | disjoint | 4 | 0.153 | 0/5 |
| Aria | hotspot | 1 | 0.120 | 0/5 |
| Aria | hotspot | 2 | 0.145 | 0/5 |
| Aria | hotspot | 4 | 0.160 | 0/5 |
| MyISAM | disjoint | 1 | 0.453 | 0/5 |
| MyISAM | disjoint | 2 | 0.950 | 0/5 |
| MyISAM | disjoint | 4 | 1.630 | 0/5 |
| MyISAM | hotspot | 1 | 0.458 | 0/5 |
| MyISAM | hotspot | 2 | 0.953 | 0/5 |
| MyISAM | hotspot | 4 | 1.622 | 0/5 |
| MEMORY | disjoint | 1 | 0.501 | 0/5 |
| MEMORY | disjoint | 2 | 1.048 | 0/5 |
| MEMORY | disjoint | 4 | 1.626 | 0/5 |
| MEMORY | hotspot | 1 | 0.506 | 0/5 |
| MEMORY | hotspot | 2 | 1.053 | 0/5 |
| MEMORY | hotspot | 4 | 1.628 | 0/5 |
| ROCKSDB | disjoint | 1 | 0.065 | 0/5 |
| ROCKSDB | disjoint | 2 | 0.080 | 0/5 |
| ROCKSDB | disjoint | 4 | 0.239 | 0/5 |
| ROCKSDB | hotspot | 1 | 0.064 | 0/5 |
| ROCKSDB | hotspot | 2 | 0.078 | 0/5 |
| ROCKSDB | hotspot | 4 | 0.226 | 0/5 |
