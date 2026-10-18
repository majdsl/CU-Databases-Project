# Concurrent writes: server CPU and lock counters

Mode: pilot. Trial means are the statistical units; pilot/smoke are correctness checks only.
DB CPU covers a broader container-launch window than throughput. SQL waits are global counters, not all contention.
InnoDB row waits apply only to InnoDB. n/a denotes missing counters or no sample SD. Cache/durability budgets differ.

| Engine | Pattern | Clients | Updates/s mean ± SD | DB average cores mean | Table waits mean | InnoDB row waits mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| InnoDB | disjoint | 1 | 855.34 ± n/a | 0.092 | 0.000 | 0.000 |
| InnoDB | disjoint | 2 | 912.73 ± n/a | 0.113 | 0.000 | 0.000 |
| InnoDB | disjoint | 4 | 1794.17 ± n/a | 0.124 | 0.000 | 0.000 |
| InnoDB | hotspot | 1 | 833.10 ± n/a | 0.091 | 0.000 | 0.000 |
| InnoDB | hotspot | 2 | 923.59 ± n/a | 0.106 | 0.000 | 0.000 |
| InnoDB | hotspot | 4 | 1791.04 ± n/a | 0.121 | 0.000 | 0.000 |
| Aria | disjoint | 1 | 864.55 ± n/a | 0.088 | 0.000 | not applicable |
| Aria | disjoint | 2 | 972.60 ± n/a | 0.112 | 999.000 | not applicable |
| Aria | disjoint | 4 | 960.45 ± n/a | 0.116 | 999.000 | not applicable |
| Aria | hotspot | 1 | 865.07 ± n/a | 0.073 | 0.000 | not applicable |
| Aria | hotspot | 2 | 954.55 ± n/a | 0.092 | 999.000 | not applicable |
| Aria | hotspot | 4 | 955.23 ± n/a | 0.095 | 999.000 | not applicable |
| MyISAM | disjoint | 1 | 6750.97 ± n/a | 0.079 | 0.000 | not applicable |
| MyISAM | disjoint | 2 | 12147.06 ± n/a | 0.085 | 7.000 | not applicable |
| MyISAM | disjoint | 4 | 6403.25 ± n/a | 0.083 | 144.000 | not applicable |
| MyISAM | hotspot | 1 | 6920.79 ± n/a | 0.100 | 0.000 | not applicable |
| MyISAM | hotspot | 2 | 12108.19 ± n/a | 0.112 | 0.000 | not applicable |
| MyISAM | hotspot | 4 | 6546.27 ± n/a | 0.107 | 156.000 | not applicable |
| MEMORY | disjoint | 1 | 7294.06 ± n/a | 0.074 | 0.000 | not applicable |
| MEMORY | disjoint | 2 | 13044.36 ± n/a | 0.076 | 2.000 | not applicable |
| MEMORY | disjoint | 4 | 6384.61 ± n/a | 0.073 | 72.000 | not applicable |
| MEMORY | hotspot | 1 | 7604.57 ± n/a | 0.069 | 0.000 | not applicable |
| MEMORY | hotspot | 2 | 13061.54 ± n/a | 0.110 | 2.000 | not applicable |
| MEMORY | hotspot | 4 | 6519.76 ± n/a | 0.094 | 73.000 | not applicable |
| ROCKSDB | disjoint | 1 | 403.06 ± n/a | 0.074 | 0.000 | not applicable |
| ROCKSDB | disjoint | 2 | 433.44 ± n/a | 0.078 | 0.000 | not applicable |
| ROCKSDB | disjoint | 4 | 845.07 ± n/a | 0.117 | 0.000 | not applicable |
| ROCKSDB | hotspot | 1 | 400.65 ± n/a | 0.071 | 0.000 | not applicable |
| ROCKSDB | hotspot | 2 | 428.41 ± n/a | 0.076 | 0.000 | not applicable |
| ROCKSDB | hotspot | 4 | 869.47 ± n/a | 0.096 | 0.000 | not applicable |
