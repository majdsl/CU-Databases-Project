# README and tutorial audit — October 15, 2026

**October 29 follow-up:** main revision `8fd722cbd0b429b1f28e8b4c02b378d17d486e56`
passed [all four CI jobs](https://github.com/majdsl/CU-Databases-Project/actions/runs/40883972632).
The current tutorial adds per-case lock-counter deltas, SQL procedure-interval
observations and exact five-engine commit/rollback checks. The offline suite at that
revision has 40 tests, including repeated safe regeneration of all eight reports.
See [maintenance validation](maintenance-validation.md). Counts and claims in the
dated records below describe their original revisions; fresh human Windows setup
and interactive Windows/macOS reproduction remain separate work.

**October 27 follow-up:** [Team identities and contributions](team-contributions.md)
are now confirmed. The [hands-on tutorial](tutorial.md) has a separate live SQL
correctness path in CI. Earlier counts and run links below remain historical
snapshots. The [35/40 practice response and follow-up](evaluation-follow-up.md) are
now archived. The [stock-image tutorial](stock-tutorial-validation.md) now has
successful native Linux amd64 and ARM64 jobs and permanent command transcripts.
The [Windows Python CLI record](../evidence/reviews/20261027-windows-stock-tutorial/README.md)
also passed with Docker Desktop/WSL2 Linux amd64 in the owner's existing checkout.
Evaluated revision/tool context and interactive Windows/macOS reproduction remain open.

This is a documentation and source-consistency audit, not an evaluator grade or a new
benchmark run. Reviewed source: main commit `84a6ad04c9777d4fe6ee06758bf4b11c3603eb6d`.
The [official assignment](https://mariadb.org/bachelor_hackathon_2026-09/) was checked
for Area 6 and the published evaluation criteria on October 15.

## Verified publication and execution evidence

- Both stacked pull requests [#2](https://github.com/majdsl/CU-Databases-Project/pull/2)
  and [#1](https://github.com/majdsl/CU-Databases-Project/pull/1) are merged.
- The public default branch is `main`. Its Git tree exactly matched benchmark head
  `b496ff7165984cf0afb88e23ee8c67d8f7dc3697`: all 243 tracked files, including 148
  evidence files and 15 chart files. Team work not yet committed/merged is outside this count.
- [Main CI run 38788927632](https://github.com/majdsl/CU-Databases-Project/actions/runs/38788927632)
  passed fresh runner and DB builds, the unit suite, DB healthcheck, and all five
  actual-engine insert/read checks. This is setup/correctness evidence, not a full
  independent performance reproduction.

## Tutorial fixes made

| Finding | Change |
| --- | --- |
| README said the merge was still pending | State that the project is on main; keep unfinished team review explicit |
| Experiment commands appeared before first-run setup | Move prerequisites, checkout, setup and correctness checks before experiments |
| Initial setup omitted the OpenFlights fetch step | Fetch and verify the pinned dataset before building, consistent with CI |
| A reader had to open several reports to learn the result | Add a short evidence-linked findings table and an inline chart |
| Schema reasoning was mostly in linked method pages | Add dataset/key/index decisions and common-capability limitations to the README |
| Output paths and pilot/full progression were easy to miss | Add a complete worked example with expected outcomes and container-to-host path mapping |
| Multiple clones could look like independent environments | Explain that the normal Compose project name is fixed and can share the existing volume |
| OpenFlights method still listed completed work as pending | Link current CI, image provenance and recommendations; retain actual remaining tasks |

The written commands were checked against the current CLI arguments, Compose mount,
Dockerfile and CI sequence. Relative file/directory link targets in the README and all
17 method/findings documentation pages were checked against the repository tree.
This does not validate every external website or rerun a Windows shell. No experimental
code, raw result, measured value or historical source fingerprint was changed.

## Area 6 evidence map

| Evaluation concern, paraphrased | Where the reader can inspect it | Qualification |
| --- | --- | --- |
| Comparable schemas and workloads across multiple engines | [Synthetic method](benchmark-method.md), [OpenFlights method](openflights-method.md), SQL directories linked in README | Five engines; comparisons are within each dataset, not pooled across schemas |
| Explain useful and costly engine behaviour | [Recommendations](engine-recommendations.md), [storage](storage-findings.md), [recovery](recovery-findings.md) | Documented mechanisms are distinguished from measured causes |
| Repeated measurements and stated conditions | Each findings page, raw evidence, [environment](benchmark-environment.md) | Five repeats on one machine; CPU power blocks remain separate; some historical host details are unavailable |
| A reusable experiment path | README setup and pilot/full worked example, [CI](ci.md) | Fresh Linux setup passed; independent Windows reproduction remains pending |
| Actionable selection advice | [Decision table](engine-recommendations.md) | Requirements and costs determine the choice; no universal ranking |

Across the general criteria, documentation now exposes the model, method and example;
depth is supported by engine verification, contention diagnostics and bounded recovery
experiments; execution evidence includes repeated raw measurements and correctness checks;
usability has a direct setup-to-results path. These are evidence locations, not awarded scores.

## Still open

- Team identities and completed contributions, outstanding in the October 15 review,
  are now recorded in [the team page](team-contributions.md).
- Collect the independent reproduction/review findings. Record tested commit, host,
  commands, success/error outputs and fixes. Do not publish credentials.
- Resolve any concrete issues found by the evaluation on main; preserve the evaluation's
  tested commit so later improvements are distinguishable.
- Windows walkthrough validation on another checkout/machine remains outstanding.
  For native Linux benchmark reruns, the non-root runner (UID 10001) needs write access
  to the bind-mounted results directory; the new setup wrapper now probes that mount before starting MariaDB.
  A full native Linux benchmark reproduction remains separate from this write probe.
- Remaining environment details and fully locked transitive database packages are still
  limitations. The [recorded package inventory](../evidence/environment/20261010-db-packages.txt)
  identifies one installed build; it does not guarantee a future byte-identical rebuild.
- Broader claims about power loss, open transactions, large datasets or steady-state
  compaction require new experiments. They are outside the conclusions currently made.

Historical evidence and its original reports are preserved. Continue improvements through
reviewable commits and reevaluate the resulting main revision.

## Follow-up: tutorial simplification

The README now presents findings first and one setup command, with detailed
platform requirements and troubleshooting in [setup](setup.md). The obsolete
root ZIP-install note was removed. The wrapper checks output permissions before
starting MariaDB, and CI invokes that same wrapper. Three failure-path tests bring
the suite to 85 tests. [Recorded cache and durability settings](cache-and-durability.md)
make the comparison limits explicit. Independent team review was outstanding at
that snapshot; the named reviews and confirmed roles are now linked above.

## Hands-on SQL follow-up — October 26, 2026

The new tutorial is reachable directly from README. Its common four-engine scripts
and optional MyRocks follow-ups are explicit; expected errors are not a navigation
mechanism. The MyRocks metadata explanation agrees with the existing SST-file
findings, and locking recommendations retain their workload limits. The routine
rejects invalid inputs/nonexistent rows, counts actual affected rows and reports
observed elapsed time. The CI driver checks actual SQL and guarded restart/cleanup;
see [CI scope](ci.md). This does not substitute for a manual Windows or ARM transcript,
repeat benchmark measurements or a full evaluator response.

## Received practice feedback follow-up

The full 35/40 response predates the completed roster and tutorial-CI changes. The
[disposition table](evaluation-follow-up.md) distinguishes those resolved items from
current refinements and optional experimental extensions. The README now summarizes
storage mechanisms and the build-selection context for differing image IDs; the
exact historical cause of the image-byte differences remains unestablished. The
manual concurrency window is 30 seconds with explicit start-together instructions,
Path B was labeled unvalidated at that documentation snapshot, and the tutorial ends with its own
requirements/engine/cost table. The nine tutorial SQL files and archived CI
validation hashes are unchanged by these documentation refinements.

## Stock-image follow-up — October 27, 2026

The automated Path B now uses a digest-pinned official MariaDB 11.8.9 image on
fresh native Linux amd64 and ARM64 runners. Shared SQL checks cover all six common
files, actual engines, deterministic rows, MEMORY indexes, writer totals, restart
and cleanup. The runner verifies image/source identity and ownership, records
credential-safe command output, and removes its own disposable resources.

The [archived record](../evidence/reviews/20261027-stock-tutorial-ci/README.md) preserves
tested source/merge revisions and both successful jobs. Five new offline guard tests
also pass normally and with optimized Python. No benchmark data or tutorial SQL was
changed. This is native-platform correctness evidence; interactive Windows/macOS
walkthroughs and second-host performance replication remain outside the record.

The owner then ran the same stock driver from Windows PowerShell with Python
3.10.11 and Docker Desktop/WSL2 Linux amd64. The [uploaded evidence](../evidence/reviews/20261027-windows-stock-tutorial/README.md)
preserves all 119 command records, validation, transcript and the separately recorded
`e6767a5` commit. Nine source hashes match that revision with CRLF line endings.
This validates the Windows Python CLI in the existing checkout; the manual SQL
walkthrough and fresh Windows setup-wrapper installation remain separate.
