# Tutorial SQL correctness — October 26, 2026

This records the maintainer's automated validation added after Zeineldin Mohamed
Hassan authored the tutorial. It is not a transcript of his personal machine.

- [PR #5 run 40395842648](https://github.com/majdsl/CU-Databases-Project/actions/runs/40395842648)
  passed both jobs, including tutorial SQL/restart/cleanup and normal/optimized offline checks.
- Tested PR merge revision: `515032dc5b04b1aa61c1e7940e589c42d3778cd8`.
  PR source head: `1526e565d6aeb177ca177dd4f6e74bfabd92f5d4`.
- The independent push run [40395828223](https://github.com/majdsl/CU-Databases-Project/actions/runs/40395828223)
  also passed against that source head.
- `validation.json` preserves the decoded driver record and provenance. All nine
  recorded SQL hashes match the corresponding files in this integration.
- `transcript.txt` preserves the tutorial's SQL-PASS lines and JSON/success markers
  from the CI job, with GitHub timestamp prefixes removed. Other job output is omitted.

The MariaDB 11.8.9 amd64 run covered five engines and then the common four-engine
sequence without a MyRocks table: deterministic generated data, actual engines,
20/200-row index answers and REF/RANGE/ALL access paths, six invalid routine cases
per sequence, successful single/concurrent increment totals, persistent data after
restart, emptied MEMORY rows, and cleanup preserving a non-tutorial sentinel.

The logged elapsed times/counters validate the demonstration; they are not controlled
performance evidence. No native ARM, interactive Windows, device-power-loss or full
benchmark reproduction is claimed. See the [tutorial](../../../docs/tutorial.md),
[CI scope](../../../docs/ci.md) and [team contributions](../../../docs/team-contributions.md).
