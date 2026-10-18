# Concurrent writes: server CPU and lock counters

Mode: full. Trial means are the statistical units; pilot/smoke are correctness checks only.
DB CPU covers a broader container-launch window than throughput. SQL waits are global counters, not all contention.
InnoDB row waits apply only to InnoDB. n/a denotes missing counters or no sample SD. Cache/durability budgets differ.

| Engine | Pattern | Clients | Updates/s mean ± SD | DB average cores mean | Table waits mean | InnoDB row waits mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| InnoDB | disjoint | 1 | 856.78 ± 11.28 | 0.133 | 0.000 | 0.000 |
| InnoDB | disjoint | 2 | 938.43 ± 22.61 | 0.171 | 0.000 | 0.000 |
| InnoDB | disjoint | 4 | 1834.47 ± 86.24 | 0.258 | 0.000 | 0.000 |
| InnoDB | hotspot | 1 | 859.87 ± 40.64 | 0.134 | 0.000 | 0.000 |
| InnoDB | hotspot | 2 | 935.54 ± 11.98 | 0.172 | 0.000 | 0.000 |
| InnoDB | hotspot | 4 | 1799.56 ± 14.12 | 0.255 | 0.000 | 0.000 |
| Aria | disjoint | 1 | 877.57 ± 16.44 | 0.140 | 0.000 | not applicable |
| Aria | disjoint | 2 | 955.03 ± 25.25 | 0.180 | 9998.800 | not applicable |
| Aria | disjoint | 4 | 953.34 ± 37.57 | 0.183 | 9999.000 | not applicable |
| Aria | hotspot | 1 | 883.64 ± 13.64 | 0.137 | 0.000 | not applicable |
| Aria | hotspot | 2 | 953.72 ± 32.16 | 0.175 | 9998.800 | not applicable |
| Aria | hotspot | 4 | 964.58 ± 22.65 | 0.181 | 9999.000 | not applicable |
| MyISAM | disjoint | 1 | 6437.04 ± 493.81 | 0.332 | 0.000 | not applicable |
| MyISAM | disjoint | 2 | 12106.95 ± 406.23 | 0.464 | 31.200 | not applicable |
| MyISAM | disjoint | 4 | 6523.47 ± 83.09 | 0.354 | 1553.600 | not applicable |
| MyISAM | hotspot | 1 | 6733.37 ± 135.36 | 0.330 | 0.000 | not applicable |
| MyISAM | hotspot | 2 | 11801.20 ± 750.63 | 0.449 | 42.000 | not applicable |
| MyISAM | hotspot | 4 | 6235.73 ± 266.23 | 0.355 | 1510.000 | not applicable |
| MEMORY | disjoint | 1 | 7302.01 ± 397.93 | 0.292 | 0.000 | not applicable |
| MEMORY | disjoint | 2 | 12391.36 ± 1594.95 | 0.403 | 29.000 | not applicable |
| MEMORY | disjoint | 4 | 6215.54 ± 375.78 | 0.298 | 820.000 | not applicable |
| MEMORY | hotspot | 1 | 7211.81 ± 506.41 | 0.294 | 0.000 | not applicable |
| MEMORY | hotspot | 2 | 12858.50 ± 346.70 | 0.401 | 19.000 | not applicable |
| MEMORY | hotspot | 4 | 6332.64 ± 124.12 | 0.289 | 836.000 | not applicable |
| ROCKSDB | disjoint | 1 | 413.88 ± 14.12 | 0.092 | 0.000 | not applicable |
| ROCKSDB | disjoint | 2 | 453.07 ± 16.12 | 0.119 | 0.000 | not applicable |
| ROCKSDB | disjoint | 4 | 895.81 ± 34.27 | 0.185 | 0.000 | not applicable |
| ROCKSDB | hotspot | 1 | 417.48 ± 12.46 | 0.094 | 0.000 | not applicable |
| ROCKSDB | hotspot | 2 | 456.46 ± 8.03 | 0.118 | 0.000 | not applicable |
| ROCKSDB | hotspot | 4 | 915.75 ± 7.50 | 0.187 | 0.000 | not applicable |
