# Storage footprint experiment

Run: 20261006T120404Z-storage-a5d23142

10000 identical synthetic rows; 5 fresh-volume trial(s) per engine.
Every dataset verified before shutdown. Bytes below are not interchangeable metrics.

| Engine | Round | Before allocated bytes | After allocated bytes | Allocated delta bytes | Apparent delta bytes |
| --- | --- | --- | --- | --- | --- |
| InnoDB | 1 | 156749824 | 166322176 | 9572352 | 9503031 |
| ROCKSDB | 1 | 156749824 | 157974528 | 1224704 | 1169934 |
| MEMORY | 1 | 156749824 | 156876800 | 126976 | 65311 |
| Aria | 1 | 156749824 | 160661504 | 3911680 | 3850012 |
| MyISAM | 1 | 156749824 | 158076928 | 1327104 | 1261514 |
| ROCKSDB | 2 | 156749824 | 157974528 | 1224704 | 1169930 |
| MEMORY | 2 | 156749824 | 156876800 | 126976 | 65312 |
| Aria | 2 | 156749824 | 160661504 | 3911680 | 3849963 |
| MyISAM | 2 | 156749824 | 158076928 | 1327104 | 1261615 |
| InnoDB | 2 | 156749824 | 166322176 | 9572352 | 9503061 |
| MEMORY | 3 | 156749824 | 156876800 | 126976 | 65359 |
| Aria | 3 | 156749824 | 160661504 | 3911680 | 3850012 |
| MyISAM | 3 | 156749824 | 158076928 | 1327104 | 1261666 |
| InnoDB | 3 | 156749824 | 166322176 | 9572352 | 9503010 |
| ROCKSDB | 3 | 156749824 | 157974528 | 1224704 | 1169934 |
| Aria | 4 | 156749824 | 160661504 | 3911680 | 3850013 |
| MyISAM | 4 | 156749824 | 158076928 | 1327104 | 1261561 |
| InnoDB | 4 | 156749824 | 166322176 | 9572352 | 9502963 |
| ROCKSDB | 4 | 156749824 | 157974528 | 1224704 | 1169931 |
| MEMORY | 4 | 156749824 | 156876800 | 126976 | 65261 |
| MyISAM | 5 | 156749824 | 158076928 | 1327104 | 1261514 |
| InnoDB | 5 | 156749824 | 166322176 | 9572352 | 9502908 |
| ROCKSDB | 5 | 156749824 | 157974528 | 1224704 | 1169882 |
| MEMORY | 5 | 156749824 | 156876800 | 126976 | 65361 |
| Aria | 5 | 156749824 | 160661504 | 3911680 | 3850061 |

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
| ROCKSDB | 2 | 0 | 0 | Engine-reported statistics; not a filesystem measurement |
| MEMORY | 2 | 8388576 | 760000 | Approximate RAM allocation |
| Aria | 2 | 1097728 | 335872 | Engine-reported statistics; not a filesystem measurement |
| MyISAM | 2 | 919772 | 276480 | Engine-reported statistics; not a filesystem measurement |
| InnoDB | 2 | 1589248 | 278528 | Engine-reported statistics; not a filesystem measurement |
| MEMORY | 3 | 8388576 | 760000 | Approximate RAM allocation |
| Aria | 3 | 1097728 | 335872 | Engine-reported statistics; not a filesystem measurement |
| MyISAM | 3 | 919772 | 276480 | Engine-reported statistics; not a filesystem measurement |
| InnoDB | 3 | 1589248 | 278528 | Engine-reported statistics; not a filesystem measurement |
| ROCKSDB | 3 | 0 | 0 | Engine-reported statistics; not a filesystem measurement |
| Aria | 4 | 1097728 | 335872 | Engine-reported statistics; not a filesystem measurement |
| MyISAM | 4 | 919772 | 276480 | Engine-reported statistics; not a filesystem measurement |
| InnoDB | 4 | 1589248 | 278528 | Engine-reported statistics; not a filesystem measurement |
| ROCKSDB | 4 | 0 | 0 | Engine-reported statistics; not a filesystem measurement |
| MEMORY | 4 | 8388576 | 760000 | Approximate RAM allocation |
| MyISAM | 5 | 919772 | 276480 | Engine-reported statistics; not a filesystem measurement |
| InnoDB | 5 | 1589248 | 278528 | Engine-reported statistics; not a filesystem measurement |
| ROCKSDB | 5 | 0 | 0 | Engine-reported statistics; not a filesystem measurement |
| MEMORY | 5 | 8388576 | 760000 | Approximate RAM allocation |
| Aria | 5 | 1097728 | 335872 | Engine-reported statistics; not a filesystem measurement |

No forced MyRocks compaction or claim of steady-state storage. No compression-ratio claim.
Fresh volumes isolate trials; all trials still share the same host and filesystem.
A pilot verifies the procedure; one observation per engine is insufficient for a stable ranking.
Full file inventories, checksums, settings, image IDs and source hashes are in results.json.
See docs/storage-method.md for protocol and limitations.
