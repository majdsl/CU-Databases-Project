# Storage footprint pilot

Run: 20261006T115445Z-storage-bdfbdd47

10000 identical synthetic rows; 1 fresh-volume trial(s) per engine.
Every dataset verified before shutdown. Bytes below are not interchangeable metrics.

| Engine | Round | Before allocated bytes | After allocated bytes | Allocated delta bytes | Apparent delta bytes |
| --- | --- | --- | --- | --- | --- |
| InnoDB | 1 | 156749824 | 166322176 | 9572352 | 9503012 |
| ROCKSDB | 1 | 156749824 | 157974528 | 1224704 | 1169889 |
| MEMORY | 1 | 156749824 | 156876800 | 126976 | 65306 |
| Aria | 1 | 156749824 | 160661504 | 3911680 | 3850013 |
| MyISAM | 1 | 156749824 | 158076928 | 1327104 | 1261563 |

Allocated bytes are Linux filesystem blocks for regular files in the entire isolated datadir.
The delta includes table creation, logs, metadata, and startup/shutdown side effects; it is not table-only size.
Apparent bytes are file lengths. Neither metric is Windows VHDX size or total physical SSD usage.
Negative deltas are retained: log removal or truncation can outweigh new allocations.
MEMORY loses its rows at shutdown: its disk delta measures metadata/overhead, not stored row data.

## Live engine-reported allocation (before shutdown)

| Engine | Round | Data_length | Index_length | Interpretation |
| --- | --- | --- | --- | --- |
| InnoDB | 1 | 1589248 | 278528 | Engine-reported statistics; not a filesystem measurement |
| ROCKSDB | 1 | 0 | 0 | Engine-reported statistics; not a filesystem measurement |
| MEMORY | 1 | 8388576 | 760000 | Approximate RAM allocation |
| Aria | 1 | 1097728 | 335872 | Engine-reported statistics; not a filesystem measurement |
| MyISAM | 1 | 919772 | 276480 | Engine-reported statistics; not a filesystem measurement |

No forced MyRocks compaction or claim of steady-state storage. No compression-ratio claim.
Fresh volumes isolate trials; all trials still share the same host and filesystem.
A pilot verifies the procedure; one observation per engine is insufficient for a stable ranking.
Full file inventories, checksums, settings, image IDs and source hashes are in results.json.
See docs/storage-method.md for protocol and limitations.
