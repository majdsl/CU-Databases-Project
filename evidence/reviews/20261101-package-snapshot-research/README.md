# Package-snapshot feasibility — November 1, 2026

This is a read-only availability/signature probe at source
`93e3eedc1db066bc3d9254d6d9fef25a12ba6206`. It does **not** establish a
complete package lock, successful dependency resolution, a clean rebuild,
MyRocks compatibility, or identical image bytes. No package was installed and
no Docker build or database was started for this probe. The working Dockerfiles
retain their existing base digests, exact MyRocks version and signature checks.

## Observed sources and results

The [Ubuntu snapshot service](https://snapshot.ubuntu.com/) and its
[maintained instructions](https://ubuntu.com/server/docs/how-to/software/snapshot-service/)
describe timestamp selection supported by Ubuntu 24.04's APT. The service states
an intention to retain at least two years of snapshots; indefinite availability
is not promised. The selected candidate is `20261031T000000Z`, not a retroactive
claim about any historical image's dependencies.

| Downloaded metadata | HTTPS source | Signature result |
| --- | --- | --- |
| `noble.InRelease` | [Ubuntu noble](https://snapshot.ubuntu.com/ubuntu/20261031T000000Z/dists/noble/InRelease) | GPG exit 0, `VALIDSIG` |
| `noble-updates.InRelease` | [Ubuntu noble-updates](https://snapshot.ubuntu.com/ubuntu/20261031T000000Z/dists/noble-updates/InRelease) | GPG exit 0, `VALIDSIG` |
| `noble-backports.InRelease` | [Ubuntu noble-backports](https://snapshot.ubuntu.com/ubuntu/20261031T000000Z/dists/noble-backports/InRelease) | GPG exit 0, `VALIDSIG` |
| `noble-security.InRelease` | [Ubuntu noble-security](https://snapshot.ubuntu.com/ubuntu/20261031T000000Z/dists/noble-security/InRelease) | GPG exit 0, `VALIDSIG` |
| `mariadb.InRelease` | [MariaDB 11.8.9 noble archive](https://archive.mariadb.org/mariadb-11.8.9/repo/ubuntu/dists/noble/InRelease) | GPG exit 0, `VALIDSIG` |

All five metadata downloads returned HTTP 200. Full file lengths, SHA-256 hashes and GPG
status/message output are retained in [metadata-probe.json](metadata-probe.json).
The exact downloaded metadata and public key inputs are in [downloaded/](downloaded/).
[SHA256SUMS.txt](SHA256SUMS.txt) covers every other file in this directory.

The Ubuntu signing fingerprint was
`F6ECB3762474EDA9D21B7022871920D1991BC93C`; the MariaDB fingerprint was
`177F4010FE56CA3336300305F1656F24C74CD1D8`. Ubuntu's keyring was extracted,
without installation, from its official HTTPS
[ubuntu-keyring_2023.11.28.1_all.deb](https://archive.ubuntu.com/ubuntu/pool/main/u/ubuntu-keyring/ubuntu-keyring_2023.11.28.1_all.deb).
MariaDB's public keys came from its official HTTPS
[release-signing-key endpoint](https://mariadb.org/mariadb_release_signing_key.pgp).

These key-bootstrap downloads used the managed environment's configured HTTPS
proxy and CA trust, with certificate checking enabled. No independently authenticated
key ceremony or package-chain authentication of the keyring `.deb` was performed.
GPG reported good cryptographic signatures and `TRUST_UNDEFINED`, with its warning
that the keys were not certified by a trusted signature in the isolated keyring.
That scope is narrower than proving package installation will succeed through APT.

## Commands actually executed

Python's `urllib.request.urlopen(url, timeout=25)` fetched the seven named files
from the URLs above and in `metadata-probe.json`, with the inherited TLS trust.
Each response was written unchanged and hashed with `hashlib.sha256(raw)`.
An isolated temporary directory held the extracted keyring and GPG home; no system
APT sources, keyrings or packages were changed. The signature commands were the
following, where `probe_dir` names that new temporary directory:

```sh
dpkg-deb -x "$probe_dir/ubuntu-keyring.deb" "$probe_dir/ubuntu"
mkdir -m 700 "$probe_dir/gnupg"
gpg --batch --homedir "$probe_dir/gnupg" --no-default-keyring \
  --keyring "$probe_dir/mariadb.gpg" --import "$probe_dir/mariadb-key.pgp"
```

For each of `noble`, `noble-updates`, `noble-backports` and `noble-security`:

```sh
gpg --batch --homedir "$probe_dir/gnupg" --no-default-keyring \
  --keyring "$probe_dir/ubuntu/usr/share/keyrings/ubuntu-archive-keyring.gpg" \
  --status-fd 1 --verify "$probe_dir/noble.InRelease"
```

The filename was changed to the corresponding pocket. MariaDB used:

```sh
gpg --batch --homedir "$probe_dir/gnupg" --no-default-keyring \
  --keyring "$probe_dir/mariadb.gpg" --status-fd 1 \
  --verify "$probe_dir/mariadb.InRelease"
```

The import and all five verifications returned 0. To repeat the signature checks
offline, copy the files from `downloaded/` into a new `probe_dir` and execute those
commands. Run `sha256sum -c SHA256SUMS.txt` from this evidence directory to verify
the published bytes; the checksum list is an integrity record, not an authenticity
or build attestation.

## Precise remaining work

Use the [isolated paired-build procedure](../../../docs/build-reconstruction.md#a-concrete-snapshot-follow-up)
on a disposable builder with adequate physical storage. Inspect every enabled
APT source in the pinned base; fix each Ubuntu pocket to one snapshot, retain the
MariaDB versioned archive and exact MyRocks pin, and preserve signature/TLS checks.
Retain selected indexes and package hashes, perform two uncached builds, verify
all five real engines, and compare package/configuration/layer records. Keep the
result separate from existing measurements. Neither metadata availability nor a
versioned repository URL substitutes for that work.

The local approximately 8 GB `vfs` Docker workspace already failed from physical
disk exhaustion in the [October 31 attempts](../20261031-build-evidence/README.md).
This review did not repeat those builds or delete existing volumes. The paired
study remains pending; no snapshot is enabled in the current project build.
