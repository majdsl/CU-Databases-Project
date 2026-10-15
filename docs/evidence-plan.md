# Evidence plan

Status reviewed after the verified October 9, 2026 OpenFlights full run, alongside the
October 6 storage and recovery evidence. Completed measurements
are evidence for their stated workloads, not a universal engine ranking.

| Criterion | Evidence available | Remaining work |
| --- | --- | --- |
| Documentation | Setup, baseline schema rationale, archived baseline, CPU, storage, recovery and OpenFlights findings/charts, explicit limits and workload recommendations | Team review, roster/contributions, complete tutorial |
| MariaDB depth | Five actual-engine checks; repeated load/read, concurrent-write, storage, between-statement process-crash and real OpenFlights route experiments | Documented transaction/locking mechanisms and suitability synthesized in engine recommendations; broader failure claims need separate experiments |
| Execution | Seeded identical data, full row verification, repeated trials, raw measurements; four CPU runs with power conditions separated; 25 full storage trials, 50 full recovery trials and 25 full OpenFlights trials, each with a separate pilot | Remaining environment details and stronger environment pinning; review scope-aware recommendations |
| Usability | Runnable harnesses, setup instructions, archived worked examples, committed figures and chart generator; fresh Linux CI builds with 82 tests and five-engine integration | Windows clean-checkout tutorial reproduction, review and merge to main |

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

## Verified OpenFlights scope

The [OpenFlights findings](openflights-findings.md) cover full run
`20261009T160813Z-openflights-6884f225`: 25 trials, 67,663 routes each and 1,691,575 verified
row loads. All source/dataset checksums, seeded query streams, sampled plans and statistics
were checked. The five-trial pilot is archived separately. All 82 unit tests passed in Docker.
The route dataset adds real reference distributions; synthetic data retains its role in
controlled update and failure experiments. No real-time traffic, joins, cold-cache or
large-scale steady-state claims are established by this addition.

## Verified process-crash scope

The [protocol and harness](recovery-method.md) have real Docker pilot/full evidence and
[findings with charts](recovery-findings.md). The design pairs clean and
forced restarts after all single-row autocommit writes are acknowledged. No statement
is in flight, and the writer connection stays open until the intervention.

Recorded timings include Docker, readiness polling and full verification, not engine-only
recovery latency. A process crash is not a power-loss test. Open transactions, interrupted
statements and uncertain commit outcomes are not covered. Additional claims require separate
experiments in disposable isolated instances; never crash the normal project database.

## Recommendation synthesis

The [engine recommendations](engine-recommendations.md) combine measured load/read,
CPU/concurrency, storage and recovery trade-offs with cited MariaDB feature documentation.
They distinguish observations, documented capabilities and application-design inferences.
The decision table covers all five engines without pooling datasets or claiming a universal
winner. Multi-statement transaction behavior is documented, not experimentally validated.

## Other unfinished work

1. Team-review the [recommendations](engine-recommendations.md) and explain their
   requirement-based choices in the final tutorial.
2. Keep claims within the measured scope. Broader transaction/failure, large-scale and
   steady-state claims require separate experiments; these are not existing results.
3. Keep [correctness CI](ci.md) green. October 9 push and pull-request runs passed
   fresh builds, all 82 unit tests and real five-engine integration. Windows clean-checkout
   tutorial reproduction remains separate. Keep performance measurement on a controlled machine.
4. Complete remaining environment details and stronger database package locking. The
   October 10 laptop [database image ID](../evidence/environment/20261010-db-image-id.txt)
   and [installed package inventory](../evidence/environment/20261010-db-packages.txt)
   are archived; this records the observed build without making it reconstructible by itself. The
   [pinned runner base](runner-image.md) was rebuilt on the team laptop and passed all 82
   Docker unit tests on October 9; its build identities and test transcript are recorded.
   The [October 9 laptop snapshot](benchmark-environment.md) records CPU, RAM, Windows,
   Docker-visible resources, Engine and Compose versions. It does not establish historical
   host settings; preserve old run metadata rather than rewriting its provenance.
5. Add the actual team roster and contributions; review setup, all links and worked examples.
6. Audit against the current published evaluation prompt, then merge reviewed work into main.

References: [assignment](https://mariadb.org/bachelor_hackathon_2026-09/),
[CPU findings](cpu-findings.md), [storage findings](storage-findings.md),
[storage method](storage-method.md), [recovery findings](recovery-findings.md).
