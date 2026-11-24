# OpenFlights route comparison

Run: 20261115T223047Z-openflights-3073fafb

**FULL: five balanced engine-order rounds; statistical unit = one trial/round.**

Rows per trial: 67663. Power condition: AC connected; Energy Saver off; only PowerShell, Ubuntu, and one browser window open.
Read statistics summarize round means, not pooled individual queries. Values are mean ± sample SD.

| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |
| --- | ---: | ---: | ---: | ---: |
| InnoDB | 0.7957 ± 0.0100 | 0.1317 ± 0.0071 | 8.3209 ± 0.0359 | 0.1232 ± 0.0054 |
| Aria | 1.2865 ± 0.0209 | 0.1381 ± 0.0031 | 6.6367 ± 0.0735 | 0.1484 ± 0.0160 |
| MyISAM | 0.5176 ± 0.0100 | 0.1288 ± 0.0021 | 9.4288 ± 0.0624 | 0.1480 ± 0.0220 |
| MEMORY | 0.4230 ± 0.0094 | 0.1319 ± 0.0103 | 4.2018 ± 0.1442 | 0.1119 ± 0.0030 |
| ROCKSDB | 0.8217 ± 0.0107 | 0.1391 ± 0.0103 | 14.3955 ± 0.2072 | 0.1689 ± 0.0482 |

Every row and query answer was checked. Raw samples, query streams, plans, actual DDL,
dataset/source hashes and runtime/settings metadata are in results.json.
These are warm reads on a reused server. Timings include driver/network work; durability and
cache budgets are not equalized. No physical-disk, cold-cache or steady-state claim is made.
The routes snapshot is historical reference data, not observed flights or current schedules.
Keep these results separate from synthetic events and the pilot separate from full statistics.
Data: OpenFlights, via MariaDB/openflights; ODbL 1.0. See docs/openflights-method.md.
