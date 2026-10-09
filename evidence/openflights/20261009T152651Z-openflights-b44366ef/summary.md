# OpenFlights route comparison

Run: 20261009T152651Z-openflights-b44366ef

**PILOT: one round per engine; no variability estimate or ranking.**

Rows per trial: 67663. Power condition: plugged in; battery saver off.
Read statistics summarize round means, not pooled individual queries. Values are mean ± sample SD.

| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |
| --- | ---: | ---: | ---: | ---: |
| InnoDB | 1.1456 ± n/a | 0.2327 ± n/a | 11.0203 ± n/a | 0.2132 ± n/a |
| Aria | 2.1459 ± n/a | 0.3980 ± n/a | 12.4747 ± n/a | 0.3692 ± n/a |
| MyISAM | 0.8001 ± n/a | 0.2602 ± n/a | 10.4284 ± n/a | 0.2536 ± n/a |
| MEMORY | 0.6575 ± n/a | 0.2231 ± n/a | 5.9590 ± n/a | 0.1866 ± n/a |
| ROCKSDB | 1.2290 ± n/a | 0.2363 ± n/a | 18.4722 ± n/a | 0.2459 ± n/a |

Every row and query answer was checked. Raw samples, query streams, plans, actual DDL,
dataset/source hashes and runtime/settings metadata are in results.json.
These are warm reads on a reused server. Timings include driver/network work; durability and
cache budgets are not equalized. No physical-disk, cold-cache or steady-state claim is made.
The routes snapshot is historical reference data, not observed flights or current schedules.
Keep these results separate from synthetic events and the pilot separate from full statistics.
Data: OpenFlights, via MariaDB/openflights; ODbL 1.0. See docs/openflights-method.md.
