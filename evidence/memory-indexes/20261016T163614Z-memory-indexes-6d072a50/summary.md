# MEMORY HASH versus BTREE

Mode: pilot
Warm single-client reads. Statistical unit: trial mean; mean ± sample SD in ms.
Pilot/smoke runs do not support performance conclusions.

| Rows | Index | Equality | Range 10 | Range 1000 |
| ---: | --- | ---: | ---: | ---: |
| 10000 | HASH | 0.2249 ± n/a | 0.4323 ± n/a | 0.4581 ± n/a |
| 10000 | BTREE | 0.1766 ± n/a | 0.1823 ± n/a | 0.2888 ± n/a |
| 100000 | HASH | 0.1818 ± n/a | 2.6625 ± n/a | 2.7102 ± n/a |
| 100000 | BTREE | 0.2086 ± n/a | 0.2237 ± n/a | 0.4073 ± n/a |

Only the secondary index type changes. Same rows and query stream within each round/size pair.
All rows and answers verified; actual indexes, plans and separate session Handler_read deltas saved.
Timings include driver/network overhead. No cold-cache, concurrency or general engine-ranking claim.
Inspect plans and counters before attributing a timing difference to an access method.
