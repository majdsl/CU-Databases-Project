# OpenFlights evidence export

Tested source commit: 2da20124ca1e52128d7cb8c3536736ae139239f7

Pilot: 20261101T152902Z-openflights-444900b0
Full: 20261101T152915Z-openflights-8fa924ee

The original results/ paths are preserved. Pilot observations and full-run statistics remain separate. The session records immutable selected images, source/dataset hashes, controls, commands and a clean database stop. A build manifest is included when the producing launcher recorded one. Existing source/results/database volumes were not changed.

Extract to a new directory and run `python verify.py` (use `python3` on Linux). The extracted verifier can also check the ZIP directly: `python verify.py path/to/openflights-evidence.zip`. Checksums detect changed or missing bytes; they are not signatures, independent observation or SQL re-execution.

This export includes only known evidence filenames. It excludes .env, credentials files, external build-adapter contents and unrelated results. Review any privately customized output before sharing. The bundle is a new copy of this session, not recovery of another chat or historical ZIP. Backing up or publishing this file is a separate action; results/ is ignored by Git.
