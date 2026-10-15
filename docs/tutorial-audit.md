# README and tutorial audit — October 15, 2026

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

- Confirm full team names/usernames and actual completed contributions with the team.
  No planned work has been marked complete.
- Collect the independent reproduction/review findings. Record tested commit, host,
  commands, success/error outputs and fixes. Do not publish credentials.
- Resolve any concrete issues found by the evaluation on main; preserve the evaluation's
  tested commit so later improvements are distinguishable.
- Windows walkthrough validation on another checkout/machine remains outstanding.
  For native Linux benchmark reruns, the non-root runner (UID 10001) needs write access
  to the bind-mounted results directory; CI's setup check does not exercise benchmark
  result writes to that mount. Native Linux benchmark permissions are not validated here.
- Remaining environment details and fully locked transitive database packages are still
  limitations. The [recorded package inventory](../evidence/environment/20261010-db-packages.txt)
  identifies one installed build; it does not guarantee a future byte-identical rebuild.
- Broader claims about power loss, open transactions, large datasets or steady-state
  compaction require new experiments. They are outside the conclusions currently made.

Historical evidence and its original reports are preserved. Continue improvements through
reviewable commits and reevaluate the resulting main revision.
