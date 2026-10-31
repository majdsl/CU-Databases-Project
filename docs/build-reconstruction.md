# Build records and reconstruction limits

For new OpenFlights experiments, use the [prepared-session launcher](openflights-reproduction.md).
Its `--prepare` command builds once and writes `build-manifest.json` beside
`session.json`. Pilot and full reuse the selected immutable DB/runner image IDs.
Package probes and registry lookups finish before either measurement stage.

## What a new record contains

| Record | Meaning |
| --- | --- |
| Source commit and hashes | The checkout and experiment inputs recorded during preparation |
| Effective Dockerfile hashes | The actual local/inline Dockerfiles selected by resolved Compose, checked before and after the build; external paths and Dockerfile contents are omitted |
| Adapter hash | SHA-256 of an optional build override, checked again after preparation; adapter contents and private certificates are omitted |
| Declared base references | Literal digest-pinned `FROM` references from those Dockerfiles; dynamic/unpinned references are explicitly unresolved |
| Registry descriptors | When available, the pinned index's unique `linux/amd64` manifest and its config/compressed-layer digests |
| Output image identities | Docker's selected image/config ID, actual `linux/amd64` platform, creation timestamp and `RootFS` filesystem layer diff IDs |
| Installed software | Every installed Debian package's name/version/architecture in each image, plus runner Python version and distribution versions |
| Tool versions | Docker client/server and Compose versions, Buildx plugin version and available selected builder details |

Registry lookup uses the configured Docker client, proxy and trust configuration.
Each command has a 15-second timeout and each unique base needs at most two calls.
Missing Buildx, registry failures, unsupported manifests and ambiguous platform
selection are recorded as unavailable. They do not turn a successful local build
into a claim of complete registry evidence. A directly addressed image manifest
can supply config/layer digests but does not itself identify its platform; that
limitation is recorded explicitly. Index selection is based on its platform
descriptor, rather than an inferred operating system effect.

The Buildx plugin version and the selected BuildKit builder version are separate.
An inspection without `--bootstrap` records only the existing builder's driver
and node BuildKit versions/status, when available. It does not start, create or
reconfigure a builder. Unavailable details remain explicit; they do not prove
which backend an external build adapter or alternative Compose mode used.

Docker's image/config ID, registry index/manifest digests, compressed layer digests
and uncompressed filesystem diff IDs identify different objects. A local image ID
does not imply that the built image was pushed or can be pulled by that ID.
The record retains Docker's `inspect Id` as its reported image/config identity;
it does not manufacture a registry output digest from it. Declared bases and
registry descriptors are not a build attestation proving every parent/input.

## Probes, confidentiality and integrity

The collector reads resolved Compose and image inspection data only in memory,
then selects the fields above. It never writes resolved environment values,
build arguments, image environment/labels/history, builder endpoints or names,
registry annotations, raw command errors or certificate contents to the record.
The collector cannot make an arbitrary adapter or manually captured build log
safe to publish: review any extra files before sharing them.

Installed-package probes use only the full selected image IDs with `--pull=never`,
no network, a read-only root filesystem, dropped capabilities, no new privileges,
an unprivileged user and bounded CPU/memory/process limits. They override each
image-declared volume with a small tmpfs, so MariaDB's `/var/lib/mysql` declaration
does not create an anonymous database volume. The entrypoint is replaced with
`dpkg-query` or Python's distribution inventory; MariaDB is never started by a
package probe. Successful probe containers remove themselves. A timed-out Docker
client can leave its short-lived probe container behind; it has the label
`cu.build-record.probe=true`, no existing database volume mount and no network.
Inspect it rather than running broad cleanup commands.

New sessions use format version 2 and link the manifest's SHA-256. Loading a new
session checks that hash and its source/image/collector identities. Measurements
also check the current collector/launcher/source hashes against preparation, so
editing the helper between pilot and full is refused. Version 1 session records
remain readable without inventing metadata that they never captured. No archive
or historical image identity is changed by this feature.

## What remains necessary for long-term reconstruction

The pinned MariaDB/Python bases, exact MyRocks version and hash-pinned Python
requirement constrain important inputs. The database build still obtains
transitive Debian packages from repositories whose contents and availability may
change. An installed-package inventory records what was observed; it is not a
signed package snapshot, retained package binaries or a dependency lock. Docker
build caches, image metadata, source files and build-system versions can also
affect final identities. Matching package versions does not establish matching
image bytes or equivalent physical hosts.

A later reconstruction study should select and maintain a signed package
snapshot/version-lock strategy, perform two fresh isolated builds from it,
compare package/config/layer records and run setup/engine correctness checks.
Explain metadata-only differences and retain the resulting images separately
from existing measurement pairs. This project does not claim that study is
already complete or that missing historical configurations can be recovered.
