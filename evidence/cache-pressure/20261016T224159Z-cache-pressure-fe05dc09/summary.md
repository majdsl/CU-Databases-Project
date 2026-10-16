# InnoDB cache-pressure pilot

Run: 20261016T224159Z-cache-pressure-fe05dc09
Fixed 128 MiB buffer pool; post-verification random lookups then full scans.
Mean ± sample SD of trial means, in milliseconds. Pilot/smoke: no performance conclusion.

| Rows | Payload MiB | Lookup ms | Scan ms |
| ---: | ---: | ---: | ---: |
| 32768 | 32.000 | 0.1679 ± n/a | 11.3457 ± n/a |
| 262144 | 256.000 | 0.3129 ± n/a | 655.3800 ± n/a |

Inspect per-phase InnoDB counters and actual table bytes in results.json.
Buffer-pool misses are not proof of physical SSD reads: OS/virtualization caches remain.
One engine; not a five-engine ranking, equal-budget comparison or isolated server CPU time.
CRC32 scan includes checksum computation; load includes payload generation. See docs/cache-pressure-method.md.
