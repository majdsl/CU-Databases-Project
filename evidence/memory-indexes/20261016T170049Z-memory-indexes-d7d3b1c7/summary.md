# MEMORY HASH versus BTREE

Mode: full
Warm single-client reads. Statistical unit: trial mean; mean ± sample SD in ms.
Pilot/smoke runs do not support performance conclusions.

| Rows | Index | Equality | Range 10 | Range 1000 |
| ---: | --- | ---: | ---: | ---: |
| 10000 | HASH | 0.1935 ± 0.0053 | 0.4257 ± 0.0157 | 0.4758 ± 0.0137 |
| 10000 | BTREE | 0.1916 ± 0.0037 | 0.2010 ± 0.0142 | 0.3133 ± 0.0117 |
| 100000 | HASH | 0.1934 ± 0.0081 | 2.5974 ± 0.1162 | 2.7059 ± 0.3523 |
| 100000 | BTREE | 0.1928 ± 0.0038 | 0.1921 ± 0.0060 | 0.4197 ± 0.0390 |

Only the secondary index type changes. Same rows and query stream within each round/size pair.
All rows and answers verified; actual indexes, plans and separate session Handler_read deltas saved.
Timings include driver/network overhead. No cold-cache, concurrency or general engine-ranking claim.
Inspect plans and counters before attributing a timing difference to an access method.
