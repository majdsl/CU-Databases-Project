# Concurrent update results

Run: 20260929T164329Z-writes-17d5c81f

Fixed total updates per trial; autocommit; warm data; no automatic retries.
Throughput includes worker scheduling and server/client overhead. Durability is not equivalent.

| Engine | Pattern | Clients | Trials | Mean updates/s | Sample SD |
| --- | --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 5 | 600.41 | 29.02 |
| InnoDB | disjoint | 2 | 5 | 754.80 | 56.68 |
| InnoDB | disjoint | 4 | 5 | 1487.65 | 184.13 |
| InnoDB | hotspot | 1 | 5 | 595.15 | 40.46 |
| InnoDB | hotspot | 2 | 5 | 770.72 | 56.82 |
| InnoDB | hotspot | 4 | 5 | 1322.52 | 460.19 |
| Aria | disjoint | 1 | 5 | 607.87 | 18.46 |
| Aria | disjoint | 2 | 5 | 718.04 | 9.08 |
| Aria | disjoint | 4 | 5 | 714.68 | 5.98 |
| Aria | hotspot | 1 | 5 | 610.73 | 10.48 |
| Aria | hotspot | 2 | 5 | 721.59 | 15.01 |
| Aria | hotspot | 4 | 5 | 708.91 | 7.95 |
| MyISAM | disjoint | 1 | 5 | 2980.38 | 36.74 |
| MyISAM | disjoint | 2 | 5 | 5478.62 | 119.58 |
| MyISAM | disjoint | 4 | 5 | 2042.99 | 85.45 |
| MyISAM | hotspot | 1 | 5 | 2891.32 | 177.79 |
| MyISAM | hotspot | 2 | 5 | 5379.04 | 264.19 |
| MyISAM | hotspot | 4 | 5 | 1999.10 | 50.20 |
| MEMORY | disjoint | 1 | 5 | 3102.37 | 224.61 |
| MEMORY | disjoint | 2 | 5 | 5495.48 | 275.76 |
| MEMORY | disjoint | 4 | 5 | 1949.71 | 123.96 |
| MEMORY | hotspot | 1 | 5 | 3105.38 | 286.56 |
| MEMORY | hotspot | 2 | 5 | 5596.88 | 284.26 |
| MEMORY | hotspot | 4 | 5 | 1887.78 | 68.19 |
| ROCKSDB | disjoint | 1 | 5 | 300.89 | 15.09 |
| ROCKSDB | disjoint | 2 | 5 | 341.95 | 25.08 |
| ROCKSDB | disjoint | 4 | 5 | 623.80 | 139.52 |
| ROCKSDB | hotspot | 1 | 5 | 304.75 | 13.34 |
| ROCKSDB | hotspot | 2 | 5 | 340.44 | 20.63 |
| ROCKSDB | hotspot | 4 | 5 | 674.55 | 56.48 |

## Runner CPU diagnostics

Window includes worker setup and teardown; it differs from the throughput interval.
Average cores is CPU seconds / wall seconds, not a percentage of the whole machine.
These counters cover the runner only, not MariaDB or the Windows host.

| Engine | Pattern | Clients | Mean runner cores | Trials with throttling / observed |
| --- | --- | --- | --- | --- |
| InnoDB | disjoint | 1 | 0.120 | 0/5 |
| InnoDB | disjoint | 2 | 0.158 | 0/5 |
| InnoDB | disjoint | 4 | 0.447 | 0/5 |
| InnoDB | hotspot | 1 | 0.116 | 0/5 |
| InnoDB | hotspot | 2 | 0.158 | 0/5 |
| InnoDB | hotspot | 4 | 0.437 | 2/5 |
| Aria | disjoint | 1 | 0.117 | 0/5 |
| Aria | disjoint | 2 | 0.142 | 0/5 |
| Aria | disjoint | 4 | 0.154 | 1/5 |
| Aria | hotspot | 1 | 0.119 | 0/5 |
| Aria | hotspot | 2 | 0.143 | 0/5 |
| Aria | hotspot | 4 | 0.155 | 1/5 |
| MyISAM | disjoint | 1 | 0.455 | 0/5 |
| MyISAM | disjoint | 2 | 0.945 | 2/5 |
| MyISAM | disjoint | 4 | 1.058 | 5/5 |
| MyISAM | hotspot | 1 | 0.458 | 0/5 |
| MyISAM | hotspot | 2 | 0.949 | 0/5 |
| MyISAM | hotspot | 4 | 1.044 | 5/5 |
| MEMORY | disjoint | 1 | 0.504 | 0/5 |
| MEMORY | disjoint | 2 | 1.012 | 5/5 |
| MEMORY | disjoint | 4 | 1.045 | 5/5 |
| MEMORY | hotspot | 1 | 0.501 | 0/5 |
| MEMORY | hotspot | 2 | 1.016 | 5/5 |
| MEMORY | hotspot | 4 | 1.021 | 5/5 |
| ROCKSDB | disjoint | 1 | 0.063 | 0/5 |
| ROCKSDB | disjoint | 2 | 0.077 | 1/5 |
| ROCKSDB | disjoint | 4 | 0.232 | 3/5 |
| ROCKSDB | hotspot | 1 | 0.064 | 0/5 |
| ROCKSDB | hotspot | 2 | 0.076 | 0/5 |
| ROCKSDB | hotspot | 4 | 0.233 | 1/5 |
