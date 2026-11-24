# OpenFlights route comparison

Run: 20261115T222419Z-openflights-e0ab128c

**PILOT: one round per engine; no variability estimate or ranking.**

Rows per trial: 67663. Power condition: AC connected; Energy Saver off; only PowerShell, Ubuntu, and one browser window open.
Read statistics summarize round means, not pooled individual queries. Values are mean ± sample SD.

| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |
| --- | ---: | ---: | ---: | ---: |
| InnoDB | 0.7863 ± n/a | 0.1317 ± n/a | 8.2035 ± n/a | 0.1255 ± n/a |
| Aria | 1.2669 ± n/a | 0.1329 ± n/a | 6.6389 ± n/a | 0.1433 ± n/a |
| MyISAM | 0.5256 ± n/a | 0.1360 ± n/a | 9.2595 ± n/a | 0.1296 ± n/a |
| MEMORY | 0.4454 ± n/a | 0.1317 ± n/a | 4.0078 ± n/a | 0.1510 ± n/a |
| ROCKSDB | 0.7986 ± n/a | 0.1360 ± n/a | 14.1138 ± n/a | 0.1493 ± n/a |

Every row and query answer was checked. Raw samples, query streams, plans, actual DDL,
dataset/source hashes and runtime/settings metadata are in results.json.
These are warm reads on a reused server. Timings include driver/network work; durability and
cache budgets are not equalized. No physical-disk, cold-cache or steady-state claim is made.
The routes snapshot is historical reference data, not observed flights or current schedules.
Keep these results separate from synthetic events and the pilot separate from full statistics.
Data: OpenFlights, via MariaDB/openflights; ODbL 1.0. See docs/openflights-method.md.
