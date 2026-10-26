# Image provenance: pilot and full identities

## Why two builds were selected

The two host orchestrators run a build at the start of each invocation:

- [`scripts/run_cache_pressure.py`](../scripts/run_cache_pressure.py) calls
  `compose(project, 'build', 'db', 'runner')` on its first trial.
- [`scripts/run_write_diagnostics.py`](../scripts/run_write_diagnostics.py) calls
  the same build before starting its run.

Pilot and full are separate invocations, so they each build/resolve the mutable
local image tags and record the selected DB and runner image IDs. They were not
held to one previously selected image pair across both invocations. This explains
the selection process that allowed different identities, not the exact byte-level
cause of the difference. A build can reuse cached layers; running the same build
command does not itself prove that image bytes or configuration are identical.

## What the evidence records

The table shows 12-character prefixes for readability. The linked raw results and
[cache-pressure](data/cache-pressure-statistics.json) / [write-diagnostic](data/write-diagnostics-statistics.json)
statistics retain every complete `sha256:` identity.

| Experiment | Mode | Archived run | DB image ID prefix | Runner image ID prefix |
| --- | --- | --- | --- | --- |
| cache-pressure | pilot | [20261016T224159Z-cache-pressure-fe05dc09](../evidence/cache-pressure/20261016T224159Z-cache-pressure-fe05dc09/results.json) | `f0781fbbf0fd` | `e6ad2c2535f8` |
| cache-pressure | full | [20261016T224612Z-cache-pressure-ca6cb57e](../evidence/cache-pressure/20261016T224612Z-cache-pressure-ca6cb57e/results.json) | `24a84c7b9bf0` | `f06351f5d5b9` |
| write-diagnostics | pilot | [20261017T170909Z-write-diagnostics-31a106d2](../evidence/write-diagnostics/20261017T170909Z-write-diagnostics-31a106d2/results.json) | `15d71a27037b` | `2b0a760307a1` |
| write-diagnostics | full | [20261017T172951Z-write-diagnostics-773525b2](../evidence/write-diagnostics/20261017T172951Z-write-diagnostics-773525b2/results.json) | `835f676e242c` | `838d2c881fbb` |

For these two pairs, recorded host/worker source hashes, selected server/session
variables, runtime, server version and power label matched. That is an observation
about the fields captured, not a complete manifest of every build input or installed
OS package. Workload counts differ intentionally between pilot and full modes.
Cache-pressure trials used constant DB/runner image identities within each run;
the write diagnostic observed one DB container throughout each run. Pilot and full
are validated separately, and pilot timings are excluded from full-run statistics.

## What is not established

The archived pairs do **not** include enough paired build logs, complete image
configuration/layer comparisons and package manifests to identify the exact change.
Build metadata, changed build inputs or dependency contents can affect an image
identity, but none is established as the cause here. Different IDs are not evidence
that the same image was used, and matching selected settings do not establish
byte-identical environments. The reports retain this limitation.

The records distinguish local built image IDs from pinned base-image index/manifest
digests and from container IDs. These identifiers answer different questions; a
fresh container ID does not by itself mean a different image. See the
[recorded runner pin and build components](runner-image.md). The OCI image
configuration describes creation/history, runtime configuration and layer references;
its current ImageID note also cautions that implementation conventions have diverged.
We use the Docker fields as recorded, rather than assuming every digest has the
same meaning across objects or tools.

## Stronger control for a future paired experiment

Build and select the images once, preserve their complete identities and selected
platform, and reuse that immutable selection for both pilot and full. Record build
logs, base/output manifests, image configuration/layer identities and package
inventories before measurements. Abort a paired experiment if its selected identities
change unexpectedly. Pin transitive dependencies if byte-identical reconstruction
is required. This is a future control improvement; it does not reconstruct missing
historical provenance or change the original measurements.

References: [Docker image inspection](https://docs.docker.com/reference/cli/docker/image/inspect/),
[Docker digests and multi-platform manifests](https://docs.docker.com/dhi/explore/security-concepts/digests/),
[OCI image configuration](https://github.com/opencontainers/image-spec/blob/main/config.md).
