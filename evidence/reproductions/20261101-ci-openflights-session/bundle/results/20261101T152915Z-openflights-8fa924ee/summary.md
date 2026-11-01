# OpenFlights route comparison

Run: 20261101T152915Z-openflights-8fa924ee

**FULL: five balanced engine-order rounds; statistical unit = one trial/round.**

Rows per trial: 67663. Power condition: GitHub-hosted shared Ubuntu amd64 VM; physical power and co-tenancy uncontrolled; workflow-validation observations only.
Read statistics summarize round means, not pooled individual queries. Values are mean ± sample SD.

| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |
| --- | ---: | ---: | ---: | ---: |
| InnoDB | 0.8262 ± 0.0728 | 0.1534 ± 0.0128 | 10.6915 ± 0.0413 | 0.1416 ± 0.0228 |
| Aria | 1.7278 ± 0.1278 | 0.1609 ± 0.0218 | 9.0866 ± 0.0866 | 0.1694 ± 0.0238 |
| MyISAM | 0.6893 ± 0.0080 | 0.1465 ± 0.0008 | 9.7023 ± 0.0589 | 0.1811 ± 0.0188 |
| MEMORY | 0.5553 ± 0.0109 | 0.1462 ± 0.0127 | 5.8358 ± 0.0584 | 0.1219 ± 0.0203 |
| ROCKSDB | 0.9266 ± 0.1082 | 0.1599 ± 0.0175 | 17.6211 ± 0.0528 | 0.1635 ± 0.0096 |

Every row and query answer was checked. Raw samples, query streams, plans, actual DDL,
dataset/source hashes and runtime/settings metadata are in results.json.
These are warm reads on a reused server. Timings include driver/network work; durability and
cache budgets are not equalized. No physical-disk, cold-cache or steady-state claim is made.
The routes snapshot is historical reference data, not observed flights or current schedules.
Keep these results separate from synthetic events and the pilot separate from full statistics.
Data: OpenFlights, via MariaDB/openflights; ODbL 1.0. See docs/openflights-method.md.
