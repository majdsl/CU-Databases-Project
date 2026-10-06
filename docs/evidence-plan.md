# Evidence plan

Status reviewed after the verified October 6, 2026 storage run. Completed measurements
are evidence for their stated workloads, not a universal engine ranking.

| Criterion | Evidence available | Remaining work |
| --- | --- | --- |
| Documentation | Setup, baseline schema rationale, archived baseline, CPU and storage findings/charts, explicit limits | Workload recommendations, team roster/contributions, complete tutorial |
| MariaDB depth | Five actual-engine checks; repeated load/read, concurrent-write and storage experiments | Crash recovery, transaction/locking explanations backed by evidence, engine suitability |
| Execution | Seeded identical data, full row verification, repeated trials, raw measurements; four CPU runs with power conditions separated; 25 full storage trials plus a separate pilot | Recovery protocol, dataset coverage, complete machine settings and stronger environment pinning |
| Usability | Runnable harnesses, setup instructions, archived worked examples, committed figures and chart generator | Clean-checkout reproduction, correctness CI, review and merge to main |

## Completed measurement scope

- Load/read baseline: 10,000 synthetic flight events, five balanced rounds per engine.
- Concurrent writes: 1, 2 and 4 clients; disjoint and hotspot workloads; final data verified.
- CPU diagnostic: four archived runs; morning and evening power conditions kept separate.
- Storage: verified pilot plus full run `20261006T120404Z-storage-a5d23142`.
  The full run has 25 trials and 250,000 verified row loads. All 50 recorded shutdowns
  were clean. File sums/deltas and the saved summary were independently recalculated.
  The pilot is not pooled into full-run statistics.

Storage allocation includes whole-datadir regular files, logs, metadata and restart
side effects. MEMORY RAM is a separate metric. No steady-state MyRocks compaction,
physical-host disk-size, equal-durability or crash-recovery claim follows from this run.

## Next experiment: crash recovery

Write the protocol before running anything. Use only disposable, explicitly isolated
instances. Record the crash mechanism, server/engine durability settings, client-acknowledged
writes versus uncertain outcomes, persisted rows after restart, recovery time and any repair.
Repeat trials and preserve failures as evidence. A process crash is not a power-loss test.
The normal project database must not be the crash target.

## Other unfinished work

1. Review OpenFlights integration and complementary dataset coverage against the brief;
   document the synthetic generator's purpose and limits. Any larger-scale claims need
   appropriately larger datasets and repeated measurements.
2. Explain when each engine helps and what it costs, connecting measurements to storage,
   indexes, locking, transaction support and durability. Unsupported features are findings.
3. Add correctness CI; keep performance measurement on a controlled machine.
4. Pin the runner base image and record machine/VM/container settings and image identities.
   Preserve old run metadata rather than rewriting its provenance.
5. Add the actual team roster and contributions; review setup, all links and worked examples.
6. Audit against the current published evaluation prompt, then merge reviewed work into main.

References: [assignment](https://mariadb.org/bachelor_hackathon_2026-09/),
[CPU findings](cpu-findings.md), [storage findings](storage-findings.md),
[storage method](storage-method.md).
