# Project checkpoint — November 3, 2026

## Review corrections

This follow-up starts from `main` at `c1190ac0b34445f7ea379de8edaaf6e2d8bcc4ea`,
which includes the root MIT license. It addresses three concrete findings from the
[supplied practice review of `d81e17bd`](https://github.com/majdsl/CU-Databases-Project/blob/463d368bd4a135841cc8421eb19beb8756bf1765/practice-evaluation/20261101-d81e17bd/assessment.txt):

- OpenFlights and synthetic benchmark statements use literal fixed identifiers,
  with runtime values still bound through the driver. Recovery metadata uses two
  literal SHOW statements. No SQL-injection vulnerability was identified in the
  prior fixed-identifier construction. Workloads and timer placement are preserved.
- The [README quick start](../README.md#start-here) puts platform choice, Linux
  output access, setup, pilot inspection and full/stop/export/verification in one
  numbered path. The four-engine stock alternative is explicitly separate.
- The [current reporting guide](report-reproducibility.md) puts the safe eight-report
  check first and retains the older validation records in a
  [dated history](report-reproducibility-history.md). The concurrency method now
  links the completed storage and CPU/lock diagnostic studies.

The compression reporter checks the three changed historical benchmark files
against identical, already archived source bytes and pins their normalized hashes.
It rejects missing/altered frozen files and changed recorded fingerprints. No raw
measurement, historical source snapshot, derived finding, figure, team credit or
license is rewritten. New regression cases check parameter binding and these
historical-source failure modes. The matching commit's GitHub Checks record CI
validation; correctness checks are distinct from performance measurements.

The latest supplied practice score remains **37/40 for `d81e17bd`**. These changes
have no new independent score and do not guarantee one. Zane's and Hassan's new
physical-host evidence remains separate work: preserve and verify each original
ZIP before integrating its findings or extending contribution records. Further
engine experiments are optional; they are not substitutes for these corrections.

## Archived checkpoint — November 1, 2026

The following record describes the November 1 implementation and validation state.

**Implementation, validation and evidence publication are complete.**
[PR #15](https://github.com/majdsl/CU-Databases-Project/pull/15) merged into `main`
as `3dfab238d5d34c6d63082b8273fbc63f47c03414`. Both main workflows passed;
the original archives and internal practice review were subsequently published.
These outcomes were checked again against GitHub before this documentation cleanup.
No new evaluation or benchmark is part of the cleanup.

The reader starts at [README](../README.md). The next fresh review uses the
[neutral evaluation handoff](evaluation-handoff.md) and pins remote `main` after
this documentation cleanup. The implementation and measurement SHAs below are
dated evidence, not a substitute for that next evaluation target.

## Source and completed validation

| Record | Exact revision and observed outcome |
| --- | --- |
| Starting main before the implementation round | `93e3eedc1db066bc3d9254d6d9fef25a12ba6206` |
| Published implementation, PR #15 | `3dfab238d5d34c6d63082b8273fbc63f47c03414`; remote main and merge SHA agreed |
| [Main Correctness run 41324235736](https://github.com/majdsl/CU-Databases-Project/actions/runs/41324235736) | Success at `3dfab238d5d34c6d63082b8273fbc63f47c03414`: 146 lightweight/105 offline tests, each normally and with `-O`; five-engine setup/integration/tutorial; native amd64/ARM64 stock tutorials; report and sealed-evidence checks |
| [Main paired-build run 41324235769](https://github.com/majdsl/CU-Databases-Project/actions/runs/41324235769) | Success at that same main SHA: two uncached signed-snapshot database builds, actual five-engine readback and clean stops |
| [Local validation archive](../evidence/reviews/20261101-local-validation/README.md) | Then-current 146 lightweight/102 offline tests in both modes; eight reports/55 outputs generated twice with inputs preserved; cloud and sealed-archive guards passed. Three later snapshot guards account for main CI's 105 offline tests. |

The optional timed OpenFlights session job was **skipped on the main push**.
Its actual complete run has the separate frozen source below; main rechecked its
raw records and original export offline. The [CI guide](ci.md) describes job scope.

## Complete OpenFlights session and durable ZIP

The [real format-v2 session archive](../evidence/reproductions/20261101-ci-openflights-session/README.md)
records setup → stop the owned setup DB → prepare → pilot → automated inspection
→ full → clean stop → export → separate extraction and standalone verification.

- Producing source: `2da20124ca1e52128d7cb8c3536736ae139239f7`;
  [successful manual run 41321256187](https://github.com/majdsl/CU-Databases-Project/actions/runs/41321256187).
- Session: `20261101T152845Z-openflights-session-ba84d4b7`.
- Pilot: `20261101T152902Z-openflights-444900b0`, five verified trials.
- Full: `20261101T152915Z-openflights-8fa924ee`, 25 verified trials; pilot statistics excluded.
- Source, selected immutable images and required controls stayed unchanged between
  stages. The session records a clean stop with exit code 0 and no OOM event.
- [Original ZIP](../evidence/reproductions/20261101-ci-openflights-session/ci/openflights-evidence.zip):
  87,843 bytes, SHA-256
  `2df17236c7f9ed91acded1525a1eb87ef04f756d40029ac01e1278ecf795c35a`.
  An HTTP read at the published implementation SHA matched these bytes.

Standalone verification passed for extracted contents and ZIP, normally and with
`-O`; offline semantic rechecking matched all 15 original entries. Shared-CI
observations establish workflow execution, not controlled physical-host performance
or an independent person's installation.

## Snapshot study and completed publications

The [three-attempt index](../evidence/reviews/20261101-snapshot-builds/README.md)
and [artifact identities/checksums](../evidence/reviews/20261101-snapshot-builds/artifacts.json)
preserve the failed worker invocation, successful pair with an incomplete upload,
and complete original artifact separately. Complete archived
[run 41322953291](https://github.com/majdsl/CU-Databases-Project/actions/runs/41322953291)
tested PR merge `ab8cc6df8ac823011e9c797e86817d9d2f6ee568`; both builds/readbacks/stops
passed, and all 30 producer-checksummed files passed after download. Its ZIP SHA-256 is
`e7f883ccc00b186e286c7dc7e8bc7640bf24beb95714e4981ed9a38ac418f995`.
Inventories, selected runtime configuration and all 46 selected package-input file
contents matched; image/config IDs and RootFS diff IDs differed. The normal project
Dockerfiles are unchanged. [Build reconstruction](build-reconstruction.md) records
retention, registry and adoption limits.

| Publication | Verified durable location and outcome |
| --- | --- |
| Three original raw artifact ZIPs | [Evidence release](https://github.com/majdsl/CU-Databases-Project/releases/tag/evidence-reconstruction-20261101); [publication run 41324256907](https://github.com/majdsl/CU-Databases-Project/actions/runs/41324256907) succeeded. Each uploaded asset was downloaded again and hash-verified; GitHub asset digests/sizes match the artifact index. |
| Historical internal practice review | [Review release](https://github.com/majdsl/CU-Databases-Project/releases/tag/internal-review-20261101); [publication run 41325123834](https://github.com/majdsl/CU-Databases-Project/actions/runs/41325123834) succeeded. Notes bytes and tag were verified. It evaluates `3dfab238d5d34c6d63082b8273fbc63f47c03414`, not later documentation revisions or an independent external review. |

Both release tags point to `3dfab238d5d34c6d63082b8273fbc63f47c03414`.
Their downloadable `publication-manifest.json` files retain publication SHA,
workflow URL and content hashes. Public evidence required no redactions. The earlier
workspace upload failure was resolved through native CI publication; no upload is
pending. Actions artifacts alone are not the durable copies.

## Remaining work and boundaries

- **Next:** a fresh evaluation of pinned post-cleanup `main`, using the neutral
  handoff and current official prompt. This cleanup does not run that evaluation.
- **Pending independent physical-host task:** Zane or another reader should freeze
  that revision, inspect capacity, follow [setup](setup.md) and the
  [SQL tutorial](tutorial.md), then [prepare → pilot → inspect → full → stop → export](openflights-reproduction.md)
  and verify after extraction elsewhere. Retain hardware/OS/architecture,
  Docker/Python versions, actual power conditions, command outcomes, reader feedback,
  original ZIP and SHA-256. Preserve the measurement checkout between stages.
- **Separate follow-up:** snapshot-update/retention policy and any project-owned
  image registry retention; byte-identical reconstruction has not been demonstrated.
- The unavailable assessment-chat ZIP remains unverified. Original laptop and
  October 30 cloud evidence stay separate. The two October 31 disk-exhaustion
  attempts ended before timed workloads and remain failures. Existing Windows
  stock-tutorial checks do not complete the pending physical-laptop task.

The managed workspace had roughly 7.5 GiB physical free space with Docker `vfs`
before the implementation round. New timed work and paired builds used adequately
provisioned disposable CI, preserving existing local resources. Shared-cloud timings
do not establish an OS effect. Another cloud run is not needed to recover this state.
