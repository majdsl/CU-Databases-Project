# InnoDB cache-pressure full

Run: 20261016T224612Z-cache-pressure-ca6cb57e
Fixed 128 MiB buffer pool; post-verification random lookups then full scans.
Mean ± sample SD of trial means, in milliseconds. Pilot/smoke: no performance conclusion.

| Rows | Payload MiB | Lookup ms | Scan ms |
| ---: | ---: | ---: | ---: |
| 32768 | 32.000 | 0.1673 ± 0.0036 | 11.3165 ± 0.3137 |
| 262144 | 256.000 | 0.3265 ± 0.0121 | 664.3568 ± 20.1780 |

Inspect per-phase InnoDB counters and actual table bytes in results.json.
Buffer-pool misses are not proof of physical SSD reads: OS/virtualization caches remain.
One engine; not a five-engine ranking, equal-budget comparison or isolated server CPU time.
CRC32 scan includes checksum computation; load includes payload generation. See docs/cache-pressure-method.md.
