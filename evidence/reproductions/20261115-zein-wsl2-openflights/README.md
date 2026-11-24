# Does the engine choice change on a second laptop?

For these 67,663 routes, both laptops gave the same load order. MEMORY loaded
and scanned fastest. Among persistent engines, MyISAM loaded fastest and Aria
scanned fastest. **The middle of the scan ranking changed:** MyISAM beat InnoDB
on the original laptop; InnoDB beat MyISAM on the second. If you're choosing
between those two for scans, try your own workload.

| Engine | Original load (s) | Second load (s) | Original scan (ms) | Second scan (ms) |
| --- | ---: | ---: | ---: | ---: |
| InnoDB | 1.1840 ± 0.0383 | 0.7957 ± 0.0100 | 11.4745 ± 0.4860 | 8.3209 ± 0.0359 |
| Aria | 2.0078 ± 0.0305 | 1.2865 ± 0.0209 | 9.7694 ± 0.4150 | 6.6367 ± 0.0735 |
| MyISAM | 0.7932 ± 0.0213 | 0.5176 ± 0.0100 | 10.3507 ± 0.3222 | 9.4288 ± 0.0624 |
| MEMORY | 0.6906 ± 0.0410 | 0.4230 ± 0.0094 | 5.7458 ± 0.3325 | 4.2018 ± 0.1442 |
| ROCKSDB | 1.2440 ± 0.0182 | 0.8217 ± 0.0107 | 18.8477 ± 0.3985 | 14.3955 ± 0.2072 |

Each cell is a mean ± sample SD across five balanced rounds **on one host**.
For scans, one observation is a trial's mean, not an individual query.
The [original full report](../../openflights/20261009T160813Z-openflights-6884f225/summary.md)
and [second laptop's full report](full/summary.md) include point lookups and
source aggregates too. These are warm client-observed timings. Hardware, Docker
and builds can differ: this comparison does not isolate a cause or an OS effect.

## What Zeineldin ran

[Zeineldin Mohamed Hassan](../../../docs/teammate-2-review.md) ran the project on
a second Windows 11 Pro laptop using Ubuntu 26.04 LTS in WSL2 and Docker Desktop's
Linux amd64 engine at [source `4fa0cc7`](https://github.com/majdsl/CU-Databases-Project/commit/4fa0cc760bcc66bcdfbdf81c1b4a6c304e76a701).
The machine (Intel Core i7-13700H, 7.70 GiB RAM) was on AC power with Energy
Saver off. Database and runner limits were 2 CPUs / 2 GiB and 1 CPU / 512 MiB.

- **Setup:** the first attempt could not write to `/results`. After installing
  `acl` and granting UID 10001 access to just the checkout's `results/` directory,
  the probe, 147 tests and all five engine checks passed.
- **Tutorial and reports:** all seven common stock tutorial SQL files passed on
  amd64. The reporting Python initially lacked `ensurepip`; installing the matching
  Ubuntu venv package let him regenerate eight reports twice and check 55 outputs.
- **Measurements:** pilot `20261115T222419Z-openflights-e0ab128c` has five trials;
  full run `20261115T223047Z-openflights-3073fafb` has 25. All 30 recorded the same
  67,663-row dataset digest. Zeineldin reported a clean stop with the DB volume retained.

The build record, runtime image selection and session summary agree on the
selected DB image (`sha256:1eadf211de0515f4f568564abc19c2ff21301a59c6b0fe6e592e62d349bdda07`)
and runner (`sha256:a80790a5651e39ed0a14a4eb7479fdd141ad143e8a140e7db7721a2a318f786c`)
for the session. This was an automated workflow from WSL2; it was neither a macOS
run nor an unassisted study with a first-time user. The [October cloud run](../../../docs/openflights-linux-reproduction.md)
is a separate environment and is not in the table.

## What you can verify

From the repository root, run `python scripts/compare_openflights_laptops.py`
(Windows) or `python3 scripts/compare_openflights_laptops.py` (Linux/macOS).
Python 3.9+ is all you need. The command recalculates the table from each laptop's
25 full trials, checks the second laptop's five pilot trials separately, and checks
the means and sample deviations for all four metrics against the [CSV](full-summary.csv).

| Second laptop | Raw measurements | Readable report |
| --- | --- | --- |
| Pilot · 5 trials, excluded from the comparison | [results.json](pilot/results.json) | [summary.md](pilot/summary.md) |
| Full · 25 trials, used in the comparison | [results.json](full/results.json) | [summary.md](full/summary.md) |

The [checksums](SHA256SUMS.txt) cover the four files above. One number in the
first published CSV was transcribed incorrectly: the ROCKSDB point-lookup sample
deviation is **0.0103 ms**, not 0.0021 ms. The raw trials and original report agree;
the correction does not change the means or the load and scan rankings.

The [log excerpts](outcomes.txt) include Zeineldin's first setup failure. At
integration, all 43 recorded benchmark, tutorial and workflow file hashes matched
the producing revision. The four public measurement files are byte-for-byte copies
from the reviewed handoff; the ZIP itself stays private because it contains Docker
session labels. To check the ZIP as well, add `--handoff PATH_TO_ZIP`: this verifies
its identity, all 29 internal checksums and that the public files match. Optionally
add `--save-to results/reviewed-laptop` to copy just the four files to a new folder.

Reviewed ZIP: 115,943 bytes; SHA-256
`af4ba9377c6cf4ede5fa0f21067567c25296e04e7421afec119dff0320f2129d`.
