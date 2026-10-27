# MyRocks compression: full

Run: 20261027T220128Z-rocksdb-compression-ea876f45
Mean ± sample SD across trial/round means; pilot/smoke supports no ranking.

| Data | Codec | SST MiB | Insert execute s | Forced flush s | Lookup ms | CRC32 scan ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| compressible | none | 65.7062 ± 0.0000 | 1.6321 ± 0.1364 | 0.0276 ± 0.0029 | 0.1682 ± 0.0041 | 41.2708 ± 2.1388 |
| compressible | zstd | 3.1850 ± 0.0002 | 1.5155 ± 0.0356 | 0.0308 ± 0.0018 | 0.1672 ± 0.0037 | 39.0418 ± 1.5435 |
| random | none | 65.7062 ± 0.0000 | 8.3161 ± 0.6327 | 0.0249 ± 0.0010 | 0.1749 ± 0.0107 | 39.8045 ± 0.9429 |
| random | zstd | 65.4158 ± 0.0001 | 7.8627 ± 0.4759 | 0.0302 ± 0.0015 | 0.1710 ± 0.0044 | 39.5660 ± 0.9623 |

Fresh database volume per trial; actual column-family and SST codec checked.
SST bytes are table-mapped file lengths from a read-only mount after a verified clean stop.
Automatic compaction is disabled in both treatments: this is a bounded flush-only study.
Reads follow full row verification and warmups; timings include client/network and CRC32 work.
Synthetic data, one engine and a 64 MiB full-run payload: no cold-cache, physical-SSD,
steady-state compaction, server-CPU isolation or five-engine ranking claim.
See docs/rocksdb-compression-method.md.
