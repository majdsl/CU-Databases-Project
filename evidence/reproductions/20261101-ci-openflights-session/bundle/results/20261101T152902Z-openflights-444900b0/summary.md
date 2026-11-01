# OpenFlights route comparison

Run: 20261101T152902Z-openflights-444900b0

**PILOT: one round per engine; no variability estimate or ranking.**

Rows per trial: 67663. Power condition: GitHub-hosted shared Ubuntu amd64 VM; physical power and co-tenancy uncontrolled; workflow-validation observations only.
Read statistics summarize round means, not pooled individual queries. Values are mean ± sample SD.

| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |
| --- | ---: | ---: | ---: | ---: |
| InnoDB | 0.7787 ± n/a | 0.1832 ± n/a | 10.7333 ± n/a | 0.1324 ± n/a |
| Aria | 1.6686 ± n/a | 0.1524 ± n/a | 9.1432 ± n/a | 0.1585 ± n/a |
| MyISAM | 0.7007 ± n/a | 0.1959 ± n/a | 9.6566 ± n/a | 0.2299 ± n/a |
| MEMORY | 0.5810 ± n/a | 0.1742 ± n/a | 5.8246 ± n/a | 0.1596 ± n/a |
| ROCKSDB | 0.9009 ± n/a | 0.1718 ± n/a | 17.4332 ± n/a | 0.2068 ± n/a |

Every row and query answer was checked. Raw samples, query streams, plans, actual DDL,
dataset/source hashes and runtime/settings metadata are in results.json.
These are warm reads on a reused server. Timings include driver/network work; durability and
cache budgets are not equalized. No physical-disk, cold-cache or steady-state claim is made.
The routes snapshot is historical reference data, not observed flights or current schedules.
Keep these results separate from synthetic events and the pilot separate from full statistics.
Data: OpenFlights, via MariaDB/openflights; ODbL 1.0. See docs/openflights-method.md.
