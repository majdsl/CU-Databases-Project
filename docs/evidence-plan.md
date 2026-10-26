# Evidence plan

Status reviewed October 26, 2026, including the confirmed team roster, hands-on tutorial,
and verified OpenFlights, storage/recovery,
MEMORY index, InnoDB cache-pressure and server CPU/lock-wait evidence. Completed measurements
are evidence for their stated workloads, not a universal engine ranking.

| Criterion | Evidence available | Remaining work |
| --- | --- | --- |
| Documentation | Setup, baseline schema rationale, archived baseline, CPU, storage, recovery and OpenFlights findings/charts, explicit limits and workload recommendations | Confirmed roster and expanded contributions linked; practice feedback archived; evaluated revision/tool context and separate manual tutorial transcript pending |
| MariaDB depth | Five actual-engine checks; repeated load/read, concurrent-write, storage, between-statement process-crash and real OpenFlights route experiments | Documented transaction/locking mechanisms and suitability synthesized in engine recommendations; broader failure claims need separate experiments |
| Execution | Seeded identical data, full row verification, repeated trials, raw measurements; four CPU runs with power conditions separated; 25 full storage trials, 50 full recovery trials and 25 full OpenFlights trials, each with a separate pilot | Remaining environment details and stronger environment pinning; review scope-aware recommendations |
| Usability | Runnable harnesses, setup instructions, archived worked examples, committed figures and chart generator; fresh Linux CI builds with 115 tests and five-engine integration | Independent Windows clean-checkout tutorial reproduction and team review |

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

## Offline reporting verified

The [October 15 report check](report-reproducibility.md) regenerated CPU, storage, recovery
and OpenFlights reports from a fresh source archive. Numerical results matched; line-ending
provenance and storage SVG determinism were corrected without changing raw evidence.
This does not replace independent database reproduction.

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
5. The [team roster and completed contributions](team-contributions.md) are now documented.
   Preserve any independent manual tutorial/reproduction transcript separately; automated
   tutorial SQL validation does not establish Windows or native ARM reproduction.
6. The [35/40 practice response and follow-up](evaluation-follow-up.md) are now archived.
   Record its exact evaluated revision and model/tool context when supplied, then
   reevaluate the improved main revision. No later score is inferred.
   The project was merged on October 15; main CI passed on `84a6ad0`.
   See the [tutorial audit](tutorial-audit.md) for completed checks and remaining gaps.

References: [assignment](https://mariadb.org/bachelor_hackathon_2026-09/),
[CPU findings](cpu-findings.md), [storage findings](storage-findings.md),
[storage method](storage-method.md), [recovery findings](recovery-findings.md).

## Tutorial and settings follow-up

The README now has an upfront measured comparison and a single setup wrapper.
Detailed platform support, output permissions and troubleshooting are in
[setup](setup.md). The [cache/durability table](cache-and-durability.md) is drawn
from the archived OpenFlights snapshot; it does not claim equal budgets. The
wrapper has three failure-path tests (85 total), and CI runs the documented command.
Team reproduction, contribution confirmation and targeted mechanism experiments
remain separate tasks; no new performance measurements are claimed here.

## MEMORY mechanism experiment

The [HASH/BTREE harness](memory-index-method.md) changes only the secondary index
type and records verified answers, plans and session handler deltas. Nine new unit
tests bring the suite to 94; CI also exercises a small real-server correctness run.
The October 16 laptop pilot and 24-trial full run are archived. The
[findings](memory-index-findings.md) report six rounds per size/index, 72 trial/workload
means and consistent plan/counter evidence: HASH scans for ranges, BTREE uses range
access. Equality means were similar. Four figure files, derived data and an offline
validator reproduce the findings. Larger-than-memory, duplicate-heavy, write and
concurrent-index behavior remain unmeasured.

## InnoDB cache-pressure extension (verified)

The [isolated protocol](cache-pressure-method.md) compares 32 MiB and 256 MiB
payloads against a fixed 128 MiB pool, verifies actual table allocation and records
read counters. Full mode has six rounds per size. This addresses a targeted
larger-than-buffer-pool question; it is not a five-engine equal-cache comparison
or physical SSD latency measurement. The two-trial pilot and 12-trial full run are
archived with all 14 worker files. [Findings and charts](cache-pressure-findings.md)
show 37.56/293.78 MiB tables against the 128 MiB pool, with zero measured data reads
for the small table and read activity for every large-table phase. Full evidence
covers 1,769,472 verified rows, 60,000 lookups and 36 scans. OS caching, dirty-page
history and different table sizes limit causal claims; pilot/full image IDs differ
and are explicitly preserved. Team contributions are now [documented](team-contributions.md).

## Server CPU and lock diagnostics

The [October 17 diagnostic findings](write-diagnostics-findings.md) validate 30 pilot
and 150 full trials, 1.5 million full-run updates and all 540 raw stage files.
Three charts (six PNG/SVG files), trial CSV, summary statistics and an offline
generator now accompany the immutable evidence. Global table-lock waits are observed
under concurrent writes; InnoDB row-wait deltas are zero for this workload. Neither
container recorded local quota throttling. Runner and DB CPU windows differ, so
these data do not isolate query CPU or a single scaling bottleneck. Full and pilot
statistics are separate. The team review/contributions are [documented](team-contributions.md); the full latest
evaluation is now [archived](evaluation-follow-up.md); its run metadata remains
incomplete. Broader claims still require separate experiments.

## Team and hands-on tutorial follow-up — October 26, 2026

The README names all three members and links their completed roles and evidence.
Zeineldin Mohamed Hassan's [tutorial](tutorial.md) and original seven SQL scripts
were merged in PR #4. Follow-up integration corrects unsupported metadata causality,
removes expected missing-MyRocks errors from the common path, hardens the update
routine and adds automated SQL, concurrency, restart and cleanup checks in CI.
This correctness work does not add new benchmark measurements or native ARM/Windows
reproduction. The supplied [35/40 response](evaluation-follow-up.md) predates these
changes; evaluated commit, model and tool context are still needed to complete the
evaluation record.

## Received evaluation and documentation refinement

The full 35/40 practice response is preserved unchanged, with a disposition for every
suggestion. Documentation (8/10 in that response) is the immediate focus: fuller,
evidence-linked teammate profiles, an upfront README mechanism explanation, a
recorded image-identity table, explicit stock-image/ARM validation limits, 30-second
manual concurrency instructions and a standalone tutorial engine-choice table.
These are documentation refinements; all original measurements remain unchanged.
Second-host measurements, client/driver decomposition, ARCHIVE, engine-option
studies, multi-engine cache pressure and replication remain distinct, unmeasured
extensions rather than newly claimed results. See [the follow-up](evaluation-follow-up.md).
