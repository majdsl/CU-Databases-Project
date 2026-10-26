# Stock-image tutorial validation — October 27, 2026

Native Linux amd64 and ARM64 jobs passed the four-engine tutorial against the pinned
official MariaDB image. These are SQL/setup/restart correctness observations, with
short writer calls; they are not cross-machine or cross-architecture performance results.

- Repository: `majdsl/CU-Databases-Project`, PR #9.
- Source head: `ed7ee7a1f754e085f33d4327a2cd3c1f73741bd6`.
- Tested PR merge revision: `9d8509de9edd8daa76bba80aed34a642c6250260`.
- Workflow: [40421200797](https://github.com/majdsl/CU-Databases-Project/actions/runs/40421200797).
- [amd64 job 121915791557](https://github.com/majdsl/CU-Databases-Project/actions/runs/40421200797/job/121915791557).
- [ARM64 job 121915791217](https://github.com/majdsl/CU-Databases-Project/actions/runs/40421200797/job/121915791217).

Both jobs reported MariaDB `11.8.9-MariaDB-ubu2404`. Runner Python, native architecture,
Docker version/resources, image ID/index reference and mounted SQL hashes are recorded
in each `validation.json`. The same index resolves different platform-specific images.

Each platform sourced all six common SQL files, checked four 50,000-row tables,
two 100,000-row MEMORY index variants, four query answers/access plans, six invalid
routine calls, four single writers and four two-writer cases. Persistent rows and
update counts survived a clean restart; MEMORY emptied. SQL cleanup preserved an
unrelated sentinel. The runner then removed its owned container and named volume.

`validation.json` was extracted between the JSON markers in the completed job log.
`commands.json` contains the parsed `COMMAND_RECORD` entries: 115 on amd64 and 120 on
ARM64 (readiness polling counts differ). `transcript.txt` retains the driver output
from its first command record through its PASS line, with GitHub timestamp prefixes
removed and LF newlines. It is a normalized job transcript, not a byte copy of the
runner's local output file. Credential-bearing inspection output was omitted by
the driver; generated passwords were redacted before logging.

The archive date uses Europe/Berlin. The linked Actions jobs began on October 26 UTC;
their original timestamps remain available in Actions. Windows/macOS interactive
shell instructions and the custom five-engine image on ARM remain outside this record.

Reproduce with `python scripts/check_stock_tutorial.py` from a clean checkout with
Docker Linux containers. See [the validation guide](../../../docs/stock-tutorial-validation.md)
for the commands, checks and scope.
