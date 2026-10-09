# OpenFlights route comparison

Run: 20261009T160813Z-openflights-6884f225

**FULL: five balanced engine-order rounds; statistical unit = one trial/round.**

Rows per trial: 67663. Power condition: plugged in; battery saver off.
Read statistics summarize round means, not pooled individual queries. Values are mean ± sample SD.

| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |
| --- | ---: | ---: | ---: | ---: |
| InnoDB | 1.1840 ± 0.0383 | 0.2413 ± 0.0057 | 11.4745 ± 0.4860 | 0.2173 ± 0.0085 |
| Aria | 2.0078 ± 0.0305 | 0.2479 ± 0.0069 | 9.7694 ± 0.4150 | 0.2441 ± 0.0112 |
| MyISAM | 0.7932 ± 0.0213 | 0.2374 ± 0.0091 | 10.3507 ± 0.3222 | 0.2524 ± 0.0137 |
| MEMORY | 0.6906 ± 0.0410 | 0.2337 ± 0.0073 | 5.7458 ± 0.3325 | 0.2080 ± 0.0119 |
| ROCKSDB | 1.2440 ± 0.0182 | 0.2491 ± 0.0079 | 18.8477 ± 0.3985 | 0.2578 ± 0.0197 |

Every row and query answer was checked. Raw samples, query streams, plans, actual DDL,
dataset/source hashes and runtime/settings metadata are in results.json.
These are warm reads on a reused server. Timings include driver/network work; durability and
cache budgets are not equalized. No physical-disk, cold-cache or steady-state claim is made.
The routes snapshot is historical reference data, not observed flights or current schedules.
Keep these results separate from synthetic events and the pilot separate from full statistics.
Data: OpenFlights, via MariaDB/openflights; ODbL 1.0. See docs/openflights-method.md.
