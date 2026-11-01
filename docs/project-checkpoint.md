# Project checkpoint — November 1, 2026

Operational handoff; the reader's starting point remains [README](../README.md).

## Source and publication

- Starting and last verified remote `main`: `93e3eedc1db066bc3d9254d6d9fef25a12ba6206`.
  `git fetch origin` and `git ls-remote origin refs/heads/main` agreed on November 1.
- Active branch: `improve/session-validation-20261101`; PR pending initial push.
- Starting worktree clean; no applicable `AGENTS.md` found in repository or ancestors.
- Baseline main [Correctness run 41208021340](https://github.com/majdsl/CU-Databases-Project/actions/runs/41208021340)
  completed successfully. This is historical validation, not a result for new changes.
- Official [assignment and evaluation prompt](https://mariadb.org/bachelor_hackathon_2026-09/)
  fetched November 1; prompt states **last updated September 4, 2026**. Area 6 is
  “Choosing the right storage engine”; the four criteria remain equally weighted.

## Priorities and completed milestones

1. Repository access, starting revision, official rubric and capacity inspected.
2. In progress: validate real format-v2 setup → stop setup DB → prepare → pilot →
   inspect → full → clean stop → export → separate extraction/offline verification
   on a disposable Ubuntu amd64 CI runner. Freeze its source before preparation;
   publish checkpoints from this separate workspace while the runner is active.
3. In progress: newcomer documentation consistency and signed build-snapshot feasibility.
4. Pending: normal/optimized suites, repeated reports, five-engine integration and
   supported tutorial CI; privacy-review and commit raw evidence; merge checked PR;
   verify remote main; produce a fresh, explicitly internal assessment of that SHA.

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

Finish and push the gated full-session CI validation job; record its tested SHA,
run URL, exact session/pilot/full IDs and actual outcomes here. Download its
export, independently revalidate and privacy-review it, then commit the unmodified
archive and its SHA-256 under `evidence/`. An Actions artifact alone is temporary;
do not claim durable backup until remote Git bytes have been verified.
