# Does the runner CPU quota affect the four-client slowdown?

Status: telemetry and quota override implemented; 32 unit tests pass locally.
Live telemetry collection and CPU comparison remain pending. Docker is unavailable
in the assistant execution environment, so the actual container build is unverified.

## Evidence motivating this test

The team run `20260929T064106Z-writes-612ad3ec` completed 150 verified trials.
For disjoint updates, MyISAM averaged 3581.95 updates/s at two clients but 1604.37
at four. MEMORY averaged 3746.21 and 1620.02 respectively. Across the 5000 raw
statement timings in each four-client disjoint condition, nearest-rank p99 was
41.321 ms (MyISAM) and 41.529 ms (MEMORY). These are descriptive pooled percentiles,
not independent samples or confidence intervals.

The manifest records a runner quota of `100000 100000` (one CPU's bandwidth).
The original run does **not** record CPU usage or throttling. A roughly 41 ms delay
alone cannot identify its cause. CPU quota, Python thread scheduling, server locking,
network timing and host scheduling are competing explanations, not established findings.

## What is measured

Every new write trial includes `runner_cpu` snapshots of cgroup v2 `cpu.stat` and
`cpu.max`, plus Python process CPU time. Deltas retain usage, user/system time,
quota periods, throttled periods and throttled microseconds when available.
Missing counters stay unavailable; counter resets and quota changes are flagged.
The summary counts trials with any observed throttling. `0/0` means no observations,
not zero throttling. Average cores = CPU seconds / elapsed wall seconds; 1.0 means
one CPU continuously busy over that interval, not 100% of the laptop.

The diagnostic interval starts before worker creation and ends after connections
and threads close. It includes setup/teardown and is deliberately separate from
the barrier-to-final-update throughput interval. Loading, row verification and
JSON output are outside this diagnostic interval. Reading counters adds some overhead,
so both comparison arms must use the instrumented code and the same built image.

These are **runner-only** counters. They do not measure database CPU, Windows host
load, network stalls, the Python GIL or ancestor-cgroup throttling. No Docker socket,
privileged container or database filesystem access is introduced. The Linux counters
are read from the runner's own cgroup. Zero local throttling does not rule out a
client-side or host-side bottleneck.

## Controlled comparison

The override `compose.runner-2cpu.yaml` changes only runner `cpus` from 1.0 to 2.0.
Database settings, workload, row count, memory limits, code, seeds and image remain
unchanged. This changes CPU bandwidth, not CPU affinity or physical core assignment.
The harness verifies the expected quota before connecting to the database.

Build once, and keep the resulting image for both arms:

```powershell
git pull --ff-only
docker compose build runner
docker compose up -d --wait db
docker compose run --rm runner python -m unittest discover -s tests -v
```

Run the instrumented one-CPU control first:

```powershell
docker compose run --rm runner python -m benchmarks.concurrency --expected-runner-cpus 1
```

After it succeeds, run the two-CPU condition:

```powershell
docker compose -f compose.yaml -f compose.runner-2cpu.yaml run --rm runner python -m benchmarks.concurrency --expected-runner-cpus 2
```

Each produces a different timestamped result directory. Preserve both JSON and summary
files. Do not overwrite the original uninstrumented result. No rebuild, package update
or database reset between arms. Use the same laptop power mode, plugged in, with heavy
background applications closed. Record interruptions or sleep; do not hide poor trials.

A first pair is diagnostic evidence, not a causal conclusion. If a difference appears,
repeat in reverse order (two CPUs, then one CPU) to reduce simple time/order confounding.
The five within-run rounds share a server and do not replace independent machine runs.
Do not run arms concurrently. Stop and inspect failures instead of blindly retrying.

## Interpretation decided before running

- Less recorded throttling alongside recovered throughput at two CPUs supports a
  contribution from runner quota; it does not isolate every source of latency.
- Continued slowdown with negligible local throttling calls for other measurements,
  including server CPU/lock waits and a separate-process client experiment.
- Mixed or inconsistent observations remain inconclusive and must be reported that way.

This test is about validity of the measurement setup, not picking a winning engine.
The original durability caveats still apply.

## Primary references

- [Linux cgroup v2 CPU counters and quota](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html#cpu-interface-files)
- [Docker Compose cpus](https://docs.docker.com/reference/compose-file/services/#cpus)
