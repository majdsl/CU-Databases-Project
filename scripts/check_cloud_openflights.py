"""Validate the sealed cloud OpenFlights archive on Windows or Linux, without Docker.

The historical validator remains byte-for-byte archived. Load it in memory to avoid
creating __pycache__ inside its exact-checksum directory. Its coverage comparison
used native path separators, so supply the same checksum checks with canonical
POSIX manifest keys and require the published checksum manifest to be present.
All row, source, schedule and comparison checks still execute the archived code.
This sealed checker does not expose the archive's maintenance --write option.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = Path("evidence/reproductions/20261030-cloud-linux-openflights")


def validate_checksums(validator):
    root, archive = validator.ROOT, validator.ARCHIVE
    manifest = archive / "sha256.json"
    require = validator.require
    require(manifest.is_file(), "Missing sealed archive checksum manifest")
    hashes = json.loads(manifest.read_text(encoding="utf-8"))
    require(isinstance(hashes, dict) and bool(hashes), "Empty or invalid checksum manifest")
    allowed = (archive, root / "evidence/openflights" / validator.CLOUD_PILOT,
               root / "evidence/openflights" / validator.CLOUD_FULL)
    expected = {path.relative_to(root).as_posix() for folder in allowed
                for path in folder.rglob("*") if path.is_file() and path != manifest}
    require(set(hashes) == expected,
            "Checksum manifest does not cover exactly the archive/new runs")
    for relative, digest in hashes.items():
        portable = PurePosixPath(relative)
        require(not portable.is_absolute() and ".." not in portable.parts
                and not PureWindowsPath(relative).drive, "Unsafe checksum path")
        path = root.joinpath(*portable.parts)
        require(any(folder.resolve() in path.resolve().parents for folder in allowed)
                and not path.is_symlink() and path.is_file(),
                "Checksum path outside archive/new runs")
        require(isinstance(digest, str) and len(digest) == 64
                and all(character in "0123456789abcdef" for character in digest),
                "Invalid SHA-256 value")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                "Archive checksum differs: " + relative)
    return len(hashes)


def load_validator(root=None):
    root = ROOT if root is None else Path(root)
    path = root / ARCHIVE_PATH / "validate.py"
    validator = types.ModuleType("cloud_archive_validator")
    validator.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), validator.__dict__)
    validator.validate_checksums = lambda: validate_checksums(validator)
    return validator


def main():
    # Validate this checker's own interface before loading any archived code.
    # In particular, do not forward the historical maintenance --write option.
    argparse.ArgumentParser(description=__doc__).parse_args()
    return load_validator().main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, TypeError) as error:
        print("VALIDATION FAILED:", str(error), file=sys.stderr)
        sys.exit(1)
