# First team baseline: provenance and review

Measured on the team laptop on 2026-09-23, using benchmark/baseline commit
428b62c3ed6ac31274711c4a8c1112474c2d7bde. These are the team-uploaded raw JSON
and generated summary, preserved unchanged. Database performance was not rerun
in the assistant environment.

Offline checks passed: completed status; 25 trials in the seeded balanced order;
regenerated 10000-row dataset checksum matches every trial; 5000 lookup timings and
125 scan timings; deterministic lookup streams; finite nonnegative timings; exact
summary regeneration. All 14 recorded source hashes match the source at the tested
revision when encoded with the Windows checkout's CRLF line endings. This explains
byte-level differences from the repository's LF source; it is not a code difference.

The machine was reported during setup as Ryzen 5 7530U, six physical cores/twelve
logical processors, 15.4 GiB usable RAM. The result JSON records Python/PyMySQL/server
versions and runner limits. Compose at the tested revision specifies database limits
of two CPUs and 2 GiB. Host power/thermal state and utilization were not captured.

This small synthetic warm-read baseline supports only workload-specific observations.
MEMORY had the lowest mean scan time and ROCKSDB the highest in this run. Point
lookup means are close; this evidence does not establish a reliable overall winner.
Load completion is not an equal-durability comparison. Physical disk size,
concurrent writes and crash recovery were not measured in this run.

Read ../../../docs/benchmark-method.md for method and limitations. The summary's
original docs link text is relative to repository root, not this evidence directory.
