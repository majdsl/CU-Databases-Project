# Project checkpoint — November 1, 2026

Operational handoff; the reader's starting point remains [README](../README.md).

## Source and publication

- Starting and last verified remote `main`: `93e3eedc1db066bc3d9254d6d9fef25a12ba6206`.
  `git fetch origin` and `git ls-remote origin refs/heads/main` agreed on November 1.
- Active branch: `improve/session-validation-20261101`; [PR #15](https://github.com/majdsl/CU-Databases-Project/pull/15).
- Initial checkpoint `d75c4b7271d9f5877ddb2a37b5f1a2a75febc5e6` pushed and
  verified with `git ls-remote`. Workflow source frozen at
  `2da20124ca1e52128d7cb8c3536736ae139239f7` for [manual run 41321256187](https://github.com/majdsl/CU-Databases-Project/actions/runs/41321256187).
  Dispatch: `gh workflow run correctness.yml --ref improve/session-validation-20261101 -f validate_openflights_session=true`.
  All five jobs passed. Source and complete raw evidence are preserved in
  [the format-v2 session archive](../evidence/reproductions/20261101-ci-openflights-session/README.md).
- Starting worktree clean; no applicable `AGENTS.md` found in repository or ancestors.
- Baseline main [Correctness run 41208021340](https://github.com/majdsl/CU-Databases-Project/actions/runs/41208021340)
  completed successfully. This is historical validation, not a result for new changes.
- Official [assignment and evaluation prompt](https://mariadb.org/bachelor_hackathon_2026-09/)
  fetched November 1; prompt states **last updated September 4, 2026**. Area 6 is
  “Choosing the right storage engine”; the four criteria remain equally weighted.

## Priorities and completed milestones

1. Repository access, starting revision, official rubric and capacity inspected.
2. Completed: real format-v2 setup → stop setup DB → prepare → pilot → inspect →
   full → clean stop → export → separate extraction/offline verification on a
   disposable Ubuntu amd64 CI runner. Pilot `20261101T152902Z-openflights-444900b0`
   has five verified trials; full `20261101T152915Z-openflights-8fa924ee` has 25.
   ZIP SHA-256: `2df17236c7f9ed91acded1525a1eb87ef04f756d40029ac01e1278ecf795c35a`.
   The measurement checkout remained frozen; this separate workspace holds publication.
3. Newcomer documentation now explains storage/worker inspection and standalone
   extraction/verification; an outdated transaction-check claim was corrected.
   Relative paths and anchors passed static checks. Signed package-snapshot
   metadata is [retained and verified](../evidence/reviews/20261101-package-snapshot-research/README.md).
   An isolated paired-build CI experiment is in progress. First attempt
   [41322017709](https://github.com/majdsl/CU-Databases-Project/actions/runs/41322017709)
   failed because Compose `run` rejected `--no-build`; source `752a87a` fixes it.
   Second attempt [41322523394](https://github.com/majdsl/CU-Databases-Project/actions/runs/41322523394)
   passed both builds/readbacks, but artifact upload omitted the checksummed
   `.gitattributes`. Preserve both original artifacts; validate a new complete one.
4. Completed local [normal/optimized validation](../evidence/reviews/20261101-local-validation/README.md):
   146 lightweight and 102 offline tests in each mode; all eight reports/55 outputs
   generated twice; cloud and sealed archive guards passed. The original manual CI
   also passed real five-engine integration/tutorial and native stock amd64/ARM64.
   Three new snapshot guards passed normally/optimized, bringing the current offline
   suite to 105 (confirm against the final passing CI).
5. Pending: publish remaining records and complete snapshot artifact; merge checked
   PR; verify remote main/checks; publish a fresh, explicitly internal assessment.

## Environment and evidence boundaries

The managed workspace preflight (`df -h`, `df -i`, `docker info`, `docker ps -a`,
`docker system df`, cgroup limits) found roughly 7.5 GiB physical free, Docker
`vfs`, no containers, three existing images and one existing volume. The host
reports 3 CPUs/approximately 9.7 GiB RAM; this task's cgroup limits are 2 CPUs/8 GiB.
No local build or new timed workload was attempted: copied-layer pressure caused
the two previously archived sandbox failures. Existing resources are retained.
CI will establish workflow correctness, not an OS effect or laptop performance.

The missing assessment-chat ZIP remains unverified. Original laptop and October 30
cloud evidence remain separate; neither failed October 31 sandbox pilot is a success.
Zane's independent physical-laptop reproduction remains pending. Build package
inventories are observations, not a complete dependency lock or identical-image proof.

## Next concrete action

Commit the reviewed session/local evidence and snapshot artifact-upload correction.
Retain failed and successful snapshot observations separately. Large public package
inputs will use GitHub Releases after privacy review: direct workspace upload returned
HTTP 401 on `uploads.github.com` (no release remained), so the manual trusted-main
publication workflow will use its scoped GitHub Actions token after merge. It verifies
reviewed archive hashes before upload and downloads every release asset again afterward.
Do not claim durable backup until the repository/release bytes have been verified.
