# MyRocks compression: pilot

Run: 20261027T213812Z-rocksdb-compression-501c1299
Mean ± sample SD across trial/round means; pilot/smoke supports no ranking.

| Data | Codec | SST MiB | Insert execute s | Forced flush s | Lookup ms | CRC32 scan ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| compressible | none | 65.7062 ± n/a | 1.8533 ± n/a | 0.0314 ± n/a | 0.1643 ± n/a | 40.2126 ± n/a |
| compressible | zstd | 3.1852 ± n/a | 1.6869 ± n/a | 0.0230 ± n/a | 0.1745 ± n/a | 39.3332 ± n/a |
| random | none | 65.7062 ± n/a | 7.6944 ± n/a | 0.0257 ± n/a | 0.1731 ± n/a | 42.8212 ± n/a |
| random | zstd | 65.4159 ± n/a | 8.6273 ± n/a | 0.0293 ± n/a | 0.1628 ± n/a | 41.6457 ± n/a |

Fresh database volume per trial; actual column-family and SST codec checked.
SST bytes are table-mapped file lengths from a read-only mount after a verified clean stop.
Automatic compaction is disabled in both treatments: this is a bounded flush-only study.
Reads follow full row verification and warmups; timings include client/network and CRC32 work.
Synthetic data, one engine and a 64 MiB full-run payload: no cold-cache, physical-SSD,
steady-state compaction, server-CPU isolation or five-engine ranking claim.
See docs/rocksdb-compression-method.md.
