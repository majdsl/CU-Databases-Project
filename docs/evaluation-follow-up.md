# Practice evaluation: 35/40 feedback and follow-up

The [team-supplied response](../evidence/evaluations/20261026-team-review-35/README.md)
reports **documentation 8, MariaDB depth 9, execution 9, usability 9: 35/40**.
The earlier 33/40 figure was reported before this full response was received. No
new score is inferred for the repository changes below, and this is not an official
course grade. The evaluated commit, model/version and execution transcript were
not supplied. The owner confirmed that the response predates `722684e`.

The review describes a strong measurement project and no blocking issues. Its
comments combine older-state documentation gaps, useful refinements and proposals
for additional experiments. These have different statuses; the list is not a set
of newly discovered mandatory submission files.

## Feedback mapped to current evidence

| Review item | Status / response | Where to inspect |
| --- | --- | --- |
| Team roster and member contributions missing | **Resolved before this response arrived.** The README names all three members; this follow-up gives Hassan and Zeineldin fuller, parallel descriptions of completed responsibilities and outputs. | [README team section](../README.md#team-and-further-review), [team contributions](team-contributions.md) |
| Mechanism explanations scattered across documents | **Addressed in this follow-up.** A compact README table connects each engine's storage/locking/index design to observations and causal limits. | [README mechanisms](../README.md#why-the-results-differ) |
| Different pilot/full image IDs unexplained | **Process explained; historical cause remains unknown.** Both orchestrators invoke a build separately for pilot/full. The identity table and captured controls are retained; the records do not establish which image bytes/metadata changed. | [Image provenance](image-provenance.md) |
| Tutorial SQL not executed in CI | **Resolved in `722684e`.** Actual source files, engine/index behavior, concurrent increments, restart and cleanup passed in CI on five-engine and common four-engine sequences. | [CI scope](ci.md), [archived SQL validation](../evidence/reviews/20261026-tutorial-ci/README.md) |
| Delete `/tutorial` before copying SQL | **Underlying path concern resolved and tested.** The tutorial/driver create the directory and copy `sql/tutorial/.` into it, avoiding nested copies and preserving unrelated directory contents. A directory deletion is not necessary for this implementation. | [Tutorial setup](tutorial.md#path-a-the-projects-five-engine-lab-linux-amd64-docker), [driver](../scripts/check_tutorial.py) |
| Explain amd64/ARM effects | **Explicitly scoped.** The five-engine image is verified on amd64. Common four-engine SQL is checked on amd64 in that lab image; stock-image Path B commands and native ARM remain unvalidated end to end. No cross-architecture performance comparison is inferred. | [Tutorial Path B](tutorial.md#path-b-arm-laptops-or-a-quick-try-stock-image-four-engines), [setup limitations](setup.md) |
| Path B not run | **Marked unvalidated directly in Path B.** Testing the common SQL is not presented as execution of the stock-image/ARM instructions. A separate transcript is still needed to close that gap. | [Tutorial](tutorial.md), [archived validation scope](../evidence/reviews/20261026-tutorial-ci/README.md) |
| Fifteen-second manual calls may miss overlap | **Addressed in this follow-up.** Use 30-second calls, have both sessions ready and start them together. The longer window improves the opportunity for overlap; it does not guarantee synchronization. | [Locking demonstration](tutorial.md#5-see-table-level-locking-happen) |
| Tutorial needs its own engine-choice table | **Addressed explicitly in this follow-up.** The existing observation table is retained, followed by a compact workload/engine/cost table. | [Tutorial decision table](tutorial.md#when-to-pick-which-engine) |
| Repeat on a second machine | **Open extension.** Offline report reproduction and hosted CI correctness do not replicate laptop performance. A second-host run needs its own versions, settings, power and trial data. | [Environment](benchmark-environment.md), [methods](../README.md#explore-or-reproduce-the-other-experiments) |
| Isolate client/driver overhead from engine time | **Open extension.** Current timings include the client/network; separate container CPU counters have different windows and are not a latency decomposition. A paired experiment would need matched SQL/operation counts and independent verification. | [Write-diagnostic timing boundaries](write-diagnostics-findings.md#cpu-windows-and-limits) |
| Add ARCHIVE | **Optional depth extension, not a missing required file.** Area 6 requires at least three engines; five are already exercised. ARCHIVE does not support UPDATE and permits only a restricted AUTO_INCREMENT key, so it cannot simply receive the shared indexed update schema. A separate append/read protocol would need its own comparability limits. | [Area 6 criteria](https://mariadb.org/bachelor_hackathon_2026-09/), [ARCHIVE capabilities](https://mariadb.com/docs/server/server-usage/storage-engines/archive) |
| Vary MyRocks compression / Aria options | **Unmeasured extension.** A useful next study would change one option at a time and verify actual DDL/settings, repeated trials and integrity. No new configuration comparison is claimed by documenting it. | [Engine mechanisms and limits](engine-recommendations.md#mechanisms-and-what-we-actually-established) |
| Extend cache-pressure tests beyond InnoDB | **Unmeasured extension.** Cache components cover different data structures; equal configured bytes are not automatically equal memory or durability budgets. | [Cache-pressure findings](cache-pressure-findings.md), [budget inventory](cache-and-durability.md) |
| Add replication or another server interaction | **Optional depth extension.** The repository currently measures single-server engine/index/cache/locking and bounded recovery behavior; no replication experiment is claimed. | [Evidence plan](evidence-plan.md) |

## Priority and next evaluation

Documentation was the lowest category in the supplied response. The roster, concise
mechanism explanation, image context and self-contained tutorial decision path are
therefore the immediate focus. Several execution/usability comments were already
resolved by the prior tutorial-CI integration; they should be checked against the
new main revision instead of treated as unchanged deficiencies.

The [official Area 6 criteria](https://mariadb.org/bachelor_hackathon_2026-09/) ask for
comparable schemas/workloads across at least three engines, explained trade-offs,
repeated measurements with stated conditions, a rerunnable harness and actionable
recommendations. ARCHIVE, compression-option studies, multi-engine cache pressure
and replication are possible ways to extend depth; no specific one is listed as a
mandatory file or topology. They may strengthen a future study, but should not be
marked completed or assigned an automatic point value.

For a new practice evaluation, retain the full response, exact main commit, model
and version, published prompt version/date, and a record of tools/commands used.
Ask the evaluator to assess that revision against the published criteria and verify
claims against files. Preserve the output before making further changes. A new score
must come from that evaluation; this follow-up does not award the remaining points.
