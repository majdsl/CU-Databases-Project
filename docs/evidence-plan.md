# Evidence plan

Status reviewed after the verified October 6, 2026 storage and recovery runs. Completed measurements
are evidence for their stated workloads, not a universal engine ranking.

| Criterion | Evidence available | Remaining work |
| --- | --- | --- |
| Documentation | Setup, baseline schema rationale, archived baseline, CPU, storage and recovery findings/charts, explicit limits | Workload recommendations, team roster/contributions, complete tutorial |
| MariaDB depth | Five actual-engine checks; repeated load/read, concurrent-write, storage and between-statement process-crash experiments | Transaction/locking explanations backed by evidence, engine suitability; broader failure claims need separate experiments |
| Execution | Seeded identical data, full row verification, repeated trials, raw measurements; four CPU runs with power conditions separated; 25 full storage trials and 50 full recovery trials, each with a separate pilot | Dataset coverage, remaining environment details and stronger environment pinning |
| Usability | Runnable harnesses, setup instructions, archived worked examples, committed figures and chart generator | Clean-checkout reproduction, correctness CI, review and merge to main |

## Completed measurement scope

- Load/read baseline: 10,000 synthetic flight events, five balanced rounds per engine.
- Concurrent writes: 1, 2 and 4 clients; disjoint and hotspot workloads; final data verified.
- CPU diagnostic: four archived runs; morning and evening power conditions kept separate.
- Storage: verified pilot plus full run `20261006T120404Z-storage-a5d23142`.
  The full run has 25 trials and 250,000 verified row loads. All 50 recorded shutdowns
  were clean. File sums/deltas and the saved summary were independently recalculated.
  The pilot is not pooled into full-run statistics.
- Recovery: verified pilot plus full run `20261006T161514Z-recovery-99656d7e`.
  Fifty full trials pair clean and forced process restarts after 1,000 acknowledged inserts.
  Four engines returned all rows unchanged; MEMORY emptied after both conditions.
  All five MyISAM forced trials logged crashed-table warnings; all five Aria forced
  trials logged Aria recovery completion. All 60 pilot/full logs are archived with checksums.

Storage allocation includes whole-datadir regular files, logs, metadata and restart
side effects. MEMORY RAM is a separate metric. No steady-state MyRocks compaction,
physical-host disk-size, equal-durability or crash-recovery claim follows from this run.

## Verified process-crash scope

The [protocol and harness](recovery-method.md) have real Docker pilot/full evidence and
[findings with charts](recovery-findings.md). The design pairs clean and
forced restarts after all single-row autocommit writes are acknowledged. No statement
is in flight, and the writer connection stays open until the intervention.

Recorded timings include Docker, readiness polling and full verification, not engine-only
recovery latency. A process crash is not a power-loss test. Open transactions, interrupted
statements and uncertain commit outcomes are not covered. Additional claims require separate
experiments in disposable isolated instances; never crash the normal project database.

## Other unfinished work

1. Review OpenFlights integration and complementary dataset coverage against the brief;
   document the synthetic generator's purpose and limits. Any larger-scale claims need
   appropriately larger datasets and repeated measurements.
2. Explain when each engine helps and what it costs, connecting measurements to storage,
   indexes, locking, transaction support and durability. Unsupported features are findings.
3. Add correctness CI; keep performance measurement on a controlled machine.
4. Pin the runner base image and complete the remaining environment details and image identities.
   The [October 9 laptop snapshot](benchmark-environment.md) records CPU, RAM, Windows,
   Docker-visible resources, Engine and Compose versions. It does not establish historical
   host settings; preserve old run metadata rather than rewriting its provenance.
5. Add the actual team roster and contributions; review setup, all links and worked examples.
6. Audit against the current published evaluation prompt, then merge reviewed work into main.

References: [assignment](https://mariadb.org/bachelor_hackathon_2026-09/),
[CPU findings](cpu-findings.md), [storage findings](storage-findings.md),
[storage method](storage-method.md), [recovery findings](recovery-findings.md).
