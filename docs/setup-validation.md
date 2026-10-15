# Five-engine setup validation

Reported: 2026-09-22.
Tested commit: `8d08de9bbc37e8d0e7610af738e1ecfd34b90140`.
Branch: `setup/docker-python`.

## Source and scope

Evidence is terminal output supplied by the team in the project conversation.
The assistant did not independently execute Docker on the team's laptop.
This is an integration smoke test, not performance, recovery, durability or scale evidence.

The reported sequence completed successfully:

1. `git pull --ff-only` advanced to the tested commit.
2. `docker compose build db runner` built both images, including the exact-version MyRocks package.
3. `docker compose up -d --wait db` reported Healthy.
4. `docker compose run --rm runner` produced the excerpt below.

## Runner output (verbatim excerpt)

```text
Server: 11.8.9-MariaDB-ubu2404
PASS: InnoDB - actual engine verified; 3 rows matched
PASS: Aria - actual engine verified; 3 rows matched
PASS: MyISAM - actual engine verified; 3 rows matched
PASS: MEMORY - actual engine verified; 3 rows matched
PASS: ROCKSDB - actual engine verified; 3 rows matched
PASS: all five engines. Setup check only; no benchmark results yet.
```

This verifies availability, table creation with the requested engine, and exact
insertion/readback for three probe rows per engine. It does not establish throughput,
latency, persistence guarantees, crash recovery or engine recommendations.

## Remaining verification

The run reused an existing data volume. A fresh-volume installation and independent
teammate reproduction remain to be tested. Do not delete the existing volume to do so;
use an isolated Compose project and separate credentials.

Pin the Python base image before collecting benchmarks: the build transcript shows
a different resolved Python base than the earlier setup, but truncates the full digest.
Do not reconstruct or guess that digest. Capture the complete value from Docker.
Final experiment metadata must also include built image identities, installed package
versions, resource/cache settings, seed and workload configuration.
