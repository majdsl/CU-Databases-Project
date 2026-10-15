# Pinned OpenFlights route data

Source: [OpenFlights](https://openflights.org/data.html), via
[MariaDB/openflights](https://github.com/MariaDB/openflights/tree/1608b8d24f30d153175dcc16bfe50e56dcc9256e).
The OpenFlights database is made available under the [Open Database License 1.0](LICENSE).
The license and source attribution accompany this manifest. They apply to the dataset;
this notice does not relicense unrelated project code.

`routes.dat` is fetched from the immutable revision in `manifest.json`, not from a moving branch.
It is ignored by Git. From the repository root, run:

```powershell
python scripts/fetch_openflights.py
```

The downloader verifies 2,309,485 bytes, SHA-256
`2b2a73310b0d8e4c3993042ee1e3827ee3c368730edd23441b4dfd79591839d2`,
and all 67,663 nine-field CSV records. A valid existing file is reused offline.
A bad existing file is refused rather than overwritten; inspect it before deliberately
removing only that download and fetching again. Interrupted downloads may leave a partial
file which will be refused by the same checksum check.

The benchmark adds a sequential file-row ID and converts three `\N` numeric ID fields to
SQL NULL. No routes are deduplicated, filtered, joined away, sampled or fabricated.
The transformed table is an OpenFlights-derived dataset. Keep its source attribution
and license with exports. See [method and limitations](../../docs/openflights-method.md).
