"""Reproduce the archived MyRocks compression report without Docker or network access."""
import argparse
import csv
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import rocksdb_compression as benchmark
from benchmarks.core import describe
from scripts.run_rocksdb_compression import SOURCE_FILES

PILOT = "20261027T213812Z-rocksdb-compression-501c1299"
FULL = "20261027T220128Z-rocksdb-compression-ea876f45"
MEASURED_COMMIT = "cd3865136c8f466d3d19a5e327c578e033478778"
EVIDENCE_COMMIT = "7dd87e4fde8f015c1d5f5759f94c910e4804a807"
EVIDENCE = ROOT / "evidence/rocksdb-compression"
HOST_FIELDS = {
    "position", "project", "images", "clean_stop", "sst_inventory",
    "table_sst", "resource_cleanup",
}
COLORS = {"none": "#216779", "zstd": "#b65b1b"}
LABELS = {"compressible": "Repetitive payload", "random": "High-entropy payload"}
METRICS = (
    "sst_bytes", "allocated_sst_bytes", "load_execute_seconds",
    "load_with_generation_seconds", "forced_flush_seconds", "lookup_ms", "scan_ms",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def compare_statistics(recorded, calculated):
    """Permit machine roundoff, never an integer count or material timing change."""
    require(type(recorded) is type(calculated) or
            type(recorded) in (int, float) and type(calculated) in (int, float),
            "Statistic type differs")
    if isinstance(calculated, dict):
        require(set(recorded) == set(calculated), "Statistic fields differ")
        for key in calculated:
            if key == "n":
                require(type(recorded[key]) is int and recorded[key] == calculated[key],
                        "Statistic sample count differs")
            compare_statistics(recorded[key], calculated[key])
    elif recorded != calculated:
        require(type(recorded) in (int, float) and type(calculated) in (int, float),
                "Statistic differs")
        require(not (type(recorded) is int and type(calculated) is int)
                and math.isclose(recorded, calculated, rel_tol=1e-12, abs_tol=1e-12),
                "Statistic differs beyond floating-point roundoff")


@lru_cache(maxsize=1)
def expected_data():
    return {profile: benchmark.oracle(profile, 65536) for profile in benchmark.PROFILES}


def verify_source(path, recorded, allowed):
    require(path in allowed, "Unexpected measured source path")
    raw = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    require(recorded in {sha256(raw), sha256(raw.replace(b"\n", b"\r\n"))},
            "Measured source changed: " + path)


def normalized_cf(options):
    result = dict(options)
    # These two values contain process-specific object addresses. Keep the factory name.
    for key in ("TABLE_FACTORY::BLOCK_CACHE", "TABLE_FACTORY::FLUSH_BLOCK_POLICY_FACTORY"):
        if key in result:
            result[key] = re.sub(r"0x[0-9a-fA-F]+", "<POINTER>", result[key])
    return result


def validate(result, run_id, mode):
    require(mode in ("pilot", "full") and result["mode"] == mode
            and result["run_id"] == run_id
            and result["experiment"] == "isolated_rocksdb_compression_v1"
            and result["format_version"] == 1, "Wrong experiment identity")
    require("active_trial" not in result and "retained_project" not in result,
            "Unfinished trial remains")
    require(result["git_commit"] == MEASURED_COMMIT
            and result["git_tracked_changes"] is False, "Measured revision/state differs")
    require(result["expected_data"] == expected_data(), "Dataset oracle differs")
    stats = benchmark.summary(result)
    compare_statistics(result["statistics"], stats)
    require(set(result["source_sha256"]) == set(SOURCE_FILES), "Missing source provenance")
    for path, digest in result["source_sha256"].items():
        verify_source(path, digest, SOURCE_FILES)
    require(result["docker"]["os"] == "linux"
            and result["docker"]["architecture"] in ("amd64", "x86_64")
            and result["host_machine"].lower() in ("amd64", "x86_64")
            and result["docker_endpoint_kind"] in ("npipe", "unix"),
            "Unexpected Docker platform/endpoint")
    require(set(result["images"]) == {"db", "runner"}, "Missing fixed images")
    for image in result["images"].values():
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", image["id"]) is not None
                and image["os"] == "linux" and image["architecture"] == "amd64",
                "Unexpected image identity/platform")
    first = result["trials"][0]
    worker_paths = set(benchmark.source_fingerprint())
    projects = set()
    for number, trial in enumerate(result["trials"], 1):
        project = trial["project"]
        match = re.fullmatch(r"cu-compression-([0-9a-f]{32})-([1-9][0-9]*)", project)
        require(match is not None and match[1][:8] == run_id.rsplit("-", 1)[1]
                and int(match[2]) == number and project not in projects,
                "Wrong or reused trial resource identity")
        projects.add(project)
        require(trial["server_version"] == "11.8.9-MariaDB-ubu2404"
                and trial["runtime"]["pymysql"] == "1.1.2"
                and trial["runtime"]["cgroup_cpu_max"] == "100000 100000"
                and trial["runtime"]["cgroup_memory_max"] == "536870912",
                "Server, driver or worker resource limit differs")
        require(trial["runtime"] == first["runtime"], "Worker runtime changed")
        require(set(trial["source_sha256"]) == worker_paths
                and trial["source_sha256"] == first["source_sha256"],
                "Worker fingerprint set changed")
        for path, digest in trial["source_sha256"].items():
            verify_source(path, digest, worker_paths)
        require(all(trial["source_sha256"][p] == h
                    for p, h in result["source_sha256"].items()
                    if p != "scripts/run_rocksdb_compression.py"),
                "Host/worker source mismatch")
        ddl = trial["actual_ddl"]
        require(ddl == first["actual_ddl"] and
                re.sub(r"\s+", " ", ddl).startswith(
                    "CREATE TABLE `compression_rows` ( `id` int(11) NOT NULL, "
                    "`payload` varbinary(1024) NOT NULL, PRIMARY KEY (`id`) ) ENGINE=ROCKSDB "),
                "Table schema changed")
        for scope in ("global_variables", "session_variables"):
            values = trial[scope]
            require(values["query_cache_type"] == "OFF" and int(values["query_cache_size"]) == 0
                    and values["autocommit"] == "ON" and values["log_bin"] == "OFF"
                    and {"STRICT_ALL_TABLES", "NO_ENGINE_SUBSTITUTION"} <=
                    set(values["sql_mode"].split(",")), "SQL controls differ")
            differing = {k for k in set(values) | set(first[scope])
                         if values.get(k) != first[scope].get(k)}
            require(differing <= {"rocksdb_default_cf_options"}, "Server/session settings changed")
        settings = trial["rocksdb_settings"]
        require(settings["rocksdb_collect_sst_properties"] == "ON"
                and settings["rocksdb_ignore_unknown_options"] == "OFF"
                and settings["rocksdb_flush_log_at_trx_commit"] == "1"
                and settings["rocksdb_default_cf_options"] ==
                benchmark.cf_configuration(trial["codec"]), "MyRocks controls differ")
        options, baseline = normalized_cf(trial["cf_options_before"]), normalized_cf(first["cf_options_before"])
        require({k for k in set(options) | set(baseline)
                 if options.get(k) != baseline.get(k)} <= {"COMPRESSION_TYPE"},
                "A column-family option other than the codec changed")
        require(trial["load_with_generation_seconds"] >= trial["load_execute_seconds"] > 0
                and trial["forced_flush_seconds"] > 0
                and all(v > 0 for v in trial["lookup_ms"] + trial["scan_ms"]),
                "Invalid or inconsistent timing")
        require(trial["table_sst"]["allocated_bytes"] >= trial["table_sst"]["bytes"],
                "Invalid SST allocation")
    return stats


def validate_commands(commands, result, raw_workers, raw_inventories):
    require([c["number"] for c in commands] == list(range(1, len(commands) + 1))
            and all(c["exit_code"] == 0 for c in commands), "Missing/failed command")
    for command in commands:
        args = command["argv"]
        require(args and args[0] in ("docker", "git")
                and "prune" not in args and args[:2] != ["docker", "compose"]
                and args[:2] != ["docker", "system"], "Unexpected lifecycle command")
        require(math.isfinite(command["elapsed_seconds"]) and command["elapsed_seconds"] >= 0,
                "Invalid command duration")
        if args[:3] in (["docker", "container", "inspect"], ["docker", "volume", "inspect"]):
            require(command["stdout"] == "[private output omitted]", "Private inspect output retained")
    creations = [(i, c) for i, c in enumerate(commands)
                 if c["argv"][:3] == ["docker", "container", "create"]]
    require(len(creations) == 3 * len(result["trials"]), "Missing/extra trial container")
    by_name = {c["argv"][c["argv"].index("--name") + 1]: (i, c) for i, c in creations}
    require(len(by_name) == len(creations), "Reused container name")
    owners = set()
    for number, trial in enumerate(result["trials"]):
        project = trial["project"]
        db_id = by_name[project + "-db"][1]["stdout"].strip()
        removals = []
        for role in ("db", "worker", "inventory"):
            created_at, record = by_name[project + "-" + role]
            args = record["argv"]
            container_id = record["stdout"].strip()
            require(re.fullmatch(r"[0-9a-f]{64}", container_id) is not None,
                    "Invalid created container ID")
            require(args[args.index("--cpus") + 1] == ("2" if role == "db" else "1")
                    and args[args.index("--memory") + 1] == ("2g" if role == "db" else "512m")
                    and result["images"]["db" if role == "db" else "runner"]["id"] in args
                    and "--publish" not in args and "-p" not in args, "Container controls differ")
            labels = [args[i + 1] for i, value in enumerate(args) if value == "--label"]
            require("cu.compression.project=" + project in labels, "Project ownership label differs")
            owner = [v.split("=", 1)[1] for v in labels if v.startswith("cu.compression.owner=")]
            require(len(owner) == 1 and re.fullmatch(r"[0-9a-f]{32}", owner[0]) is not None,
                    "Missing ownership label")
            owners.add(owner[0])
            if role == "worker":
                require(args[args.index("--network") + 1] == "container:" + db_id
                        and "--mount" not in args
                        and args[args.index("--mode") + 1] == result["mode"]
                        and args[args.index("--profile") + 1] == trial["profile"]
                        and args[args.index("--codec") + 1] == trial["codec"]
                        and args[args.index("--round") + 1] == str(trial["round"]),
                        "Worker network/condition differs")
            else:
                destination = "/var/lib/mysql" if role == "db" else "/snapshot,readonly"
                require(args[args.index("--network") + 1] == "none"
                        and args[args.index("--mount") + 1] ==
                        f"type=volume,src={project}-data,dst={destination}",
                        "Unexpected volume/network")
                if role == "db":
                    require("--rocksdb-default-cf-options=" +
                            benchmark.cf_configuration(trial["codec"]) in args,
                            "Requested codec controls differ")
                else:
                    stops = [i for i, c in enumerate(commands) if c["argv"] ==
                             ["docker", "stop", "--timeout", "120", db_id]]
                    require(len(stops) == 1 and stops[0] < created_at, "Inventory preceded clean stop")
            if role != "db":
                require("--read-only" in args, "Writable helper/worker root")
                outputs = [c["stdout"] for c in commands if c["argv"] ==
                           ["docker", "start", "--attach", container_id]]
                expected = raw_workers[number] if role == "worker" else raw_inventories[number]
                require(len(outputs) == 1 and json.loads(outputs[0]) == expected,
                        "Saved worker/inventory differs from command output")
            removed_at = [i for i, c in enumerate(commands)
                          if c["argv"] == ["docker", "rm", container_id]]
            require(len(removed_at) == 1 and removed_at[0] > created_at, "Container cleanup missing")
            removals.extend(removed_at)
        deleted_volume = [i for i, c in enumerate(commands)
                          if c["argv"] == ["docker", "volume", "rm", project + "-data"]]
        require(len(deleted_volume) == 1 and deleted_volume[0] > max(removals),
                "Owned volume cleanup missing/out of order")
    require(len(owners) == 1, "Ownership token changed during invocation")
    require(sum(c["argv"][:3] == ["docker", "volume", "rm"] for c in commands)
            == len(result["trials"]), "Unexpected volume removal")


def load(mode, evidence_root=None):
    run_id = PILOT if mode == "pilot" else FULL
    folder = (EVIDENCE if evidence_root is None else Path(evidence_root)) / run_id
    try:
        result = json.loads((folder / "results.json").read_text(encoding="utf-8"))
        stats = validate(result, run_id, mode)
        require((folder / "summary.md").read_text(encoding="utf-8") == benchmark.markdown(result),
                "Archived summary differs")
        commands_raw = (folder / "commands.json").read_bytes()
        require(sha256(commands_raw) == result["commands_sha256"], "Command-log checksum differs")
        workers, inventories, hashes = [], [], {}
        for number, trial in enumerate(result["trials"], 1):
            for suffix, target in ((".json", workers), ("-inventory.json", inventories)):
                name = f"trial-{number:02d}" + suffix
                raw = (folder / name).read_bytes()
                target.append(json.loads(raw))
                hashes[name] = {"raw_sha256": sha256(raw), "canonical_json_sha256": canonical_hash(target[-1])}
            require(workers[-1] == {k: v for k, v in trial.items() if k not in HOST_FIELDS},
                    "Raw worker differs from host result")
            require(inventories[-1] == trial["sst_inventory"], "Raw inventory differs from host result")
        commands = json.loads(commands_raw)
        validate_commands(commands, result, workers, inventories)
        for name in ("results.json", "commands.json"):
            raw = (folder / name).read_bytes()
            hashes[name] = {"raw_sha256": sha256(raw), "canonical_json_sha256": canonical_hash(json.loads(raw))}
        hashes["summary.md"] = {"lf_normalized_sha256": sha256(
            (folder / "summary.md").read_bytes().replace(b"\r\n", b"\n"))}
        return result, stats, {"files": hashes, "commands": len(commands)}
    except (KeyError, TypeError, IndexError, RuntimeError, OSError) as error:
        raise ValueError(f"Invalid {mode} evidence: {error}") from error


def observations(result):
    rows = []
    for t in result["trials"]:
        rows.append({
            "run_id": result["run_id"], "round": t["round"], "position": t["position"],
            "profile": t["profile"], "codec": t["codec"], "rows": t["rows"],
            "payload_bytes_per_row": t["payload_bytes"], "verified_rows": t["verified_rows"],
            "dataset_sha256": t["dataset_sha256"], "sst_bytes": t["table_sst"]["bytes"],
            "allocated_sst_bytes": t["table_sst"]["allocated_bytes"],
            "mapped_sst_files": len(t["table_sst"]["files"]),
            "sst_entries": sum(int(s["ENTRIES"]) for s in t["sst_after_reads"]),
            "actual_cf_codec": t["cf_options_before"]["COMPRESSION_TYPE"],
            "actual_sst_codec": ",".join(sorted({s["COMPRESSION_ALGO"] for s in t["sst_after_reads"]})),
            "load_execute_seconds": t["load_execute_seconds"],
            "load_with_generation_seconds": t["load_with_generation_seconds"],
            "forced_flush_seconds": t["forced_flush_seconds"],
            "lookup_samples": len(t["lookup_ms"]), "lookup_ms": statistics.mean(t["lookup_ms"]),
            "scan_samples": len(t["scan_ms"]), "scan_ms": statistics.mean(t["scan_ms"]),
        })
    return rows


def summarize(rows):
    return {profile: {codec: {metric: describe([r[metric] for r in rows
            if r["profile"] == profile and r["codec"] == codec]) for metric in METRICS}
            for codec in benchmark.CODECS} for profile in benchmark.PROFILES}


def paired_ratios(rows):
    result = {}
    for profile in benchmark.PROFILES:
        pairs = []
        for round_number in range(1, 9):
            pair = {r["codec"]: r for r in rows if r["profile"] == profile and r["round"] == round_number}
            pairs.append({"round": round_number, **{
                metric: pair["zstd"][metric] / pair["none"][metric] for metric in METRICS}})
        result[profile] = {
            "direction": "ZSTD / no compression; each ratio pairs trials in the same round",
            "rounds": pairs,
            "summary": {metric: describe([p[metric] for p in pairs]) for metric in METRICS},
        }
    return result


def save_figure(fig, directory, name, plt):
    fig.savefig(directory / (name + ".png"), dpi=180)
    fig.savefig(directory / (name + ".svg"), metadata={"Date": None})
    plt.close(fig)


def charts(rows, stats, directory):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "svg.hashsalt": "cu-rocksdb-compression-v1",
    })
    fig, axes = plt.subplots(1, 2, figsize=(11, 6.6), sharey=True)
    fig.subplots_adjust(left=.09, right=.97, top=.77, bottom=.24, wspace=.23)
    for ax, profile in zip(axes, benchmark.PROFILES):
        for x, codec in enumerate(benchmark.CODECS):
            values = [r["sst_bytes"] / 1048576 for r in rows
                      if r["profile"] == profile and r["codec"] == codec]
            stat = stats[profile][codec]["sst_bytes"]
            ax.bar(x, stat["mean"] / 1048576, width=.58, color=COLORS[codec], alpha=.85)
            ax.scatter([x + (i - 3.5) * .025 for i in range(8)], values,
                       color="#26333a", s=17, zorder=4)
            ax.errorbar(x, stat["mean"] / 1048576, yerr=stat["sample_sd"] / 1048576,
                        color="black", capsize=4, fmt="D", ms=3, zorder=5)
            ax.text(x, stat["mean"] / 1048576 + 1.5,
                    f"{stat['mean'] / 1048576:.2f} MiB", ha="center", fontsize=11)
        none, zstd = stats[profile]["none"]["sst_bytes"]["mean"], stats[profile]["zstd"]["sst_bytes"]["mean"]
        ax.set_title(LABELS[profile] + f"\n{100 * (1 - zstd / none):.2f}% fewer SST bytes",
                     loc="left", weight="bold", fontsize=12, pad=13)
        ax.set_xticks((0, 1), ("No compression", "ZSTD"))
        ax.set_ylim(0, 76)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.18)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Table-mapped SST file lengths (MiB)")
    fig.suptitle("MyRocks: compression depends on the payload", x=.04, y=.98,
                 ha="left", weight="bold", fontsize=18)
    fig.text(.04, .91, "64 MiB of payload per trial · eight trials per condition · pilot excluded")
    fig.legend(handles=[
        Line2D([], [], color="#26333a", marker="o", linestyle="None", label="One trial"),
        Line2D([], [], color="black", marker="D", label="Mean ± sample SD"),
    ], loc="upper left", bbox_to_anchor=(.03, .17), ncol=2, frameon=False)
    fig.text(.04, .04,
             "Both panels use the same zero-based scale. SD bars are smaller than the markers.\n"
             "Only table-mapped SSTs after a clean stop; logs and other database files are excluded.\n"
             "Automatic compaction disabled; this is a bounded flush-only result, not a steady-state footprint.",
             fontsize=9, linespacing=1.6)
    save_figure(fig, directory, "rocksdb-compression-size", plt)

    panels = (
        ("load_execute_seconds", 1, "Insert execution", "Seconds"),
        ("forced_flush_seconds", 1000, "Final flush statement", "Milliseconds"),
        ("lookup_ms", 1, "Warm primary-key lookup", "Milliseconds"),
        ("scan_ms", 1, "Warm CRC32 scan", "Milliseconds"),
    )
    fig, axes = plt.subplots(2, 4, figsize=(14.2, 8.2))
    fig.subplots_adjust(left=.075, right=.985, top=.78, bottom=.21, hspace=.58, wspace=.42)
    for row_number, profile in enumerate(benchmark.PROFILES):
        for ax, (metric, scale, title, unit) in zip(axes[row_number], panels):
            for rn in range(1, 9):
                pair = {r["codec"]: r[metric] * scale for r in rows
                        if r["profile"] == profile and r["round"] == rn}
                ax.plot((0, 1), (pair["none"], pair["zstd"]), color="#b0b5ba",
                        lw=.8, alpha=.8, zorder=1)
            for x, codec in enumerate(benchmark.CODECS):
                values = [r[metric] * scale for r in rows
                          if r["profile"] == profile and r["codec"] == codec]
                stat = stats[profile][codec][metric]
                ax.scatter([x] * 8, values, color=COLORS[codec], s=22, zorder=3)
                ax.errorbar(x, stat["mean"] * scale, yerr=stat["sample_sd"] * scale,
                            color="black", capsize=4, fmt="D", ms=4, zorder=4)
            ax.set_xticks((0, 1), ("None", "ZSTD"))
            ax.set_xlim(-.35, 1.35)
            ax.set_ylim(bottom=0, top=ax.get_ylim()[1] * 1.08)
            ax.set_title(title, loc="left", fontsize=11, weight="bold", pad=9)
            ax.set_ylabel(unit)
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", alpha=.18)
            ax.set_axisbelow(True)
        axes[row_number, 0].text(-.34, 1.25, LABELS[profile],
                                 transform=axes[row_number, 0].transAxes,
                                 fontsize=12, weight="bold")
    fig.suptitle("MyRocks compression: observed timing costs", x=.035, y=.98,
                 ha="left", weight="bold", fontsize=18)
    fig.text(.035, .925, "Eight trials per condition · lines connect the two codec trials in the same round")
    fig.legend(handles=[
        Line2D([], [], color=COLORS["none"], marker="o", linestyle="None", label="No compression"),
        Line2D([], [], color=COLORS["zstd"], marker="o", linestyle="None", label="ZSTD"),
        Line2D([], [], color="black", marker="D", label="Mean ± sample SD"),
    ], loc="upper left", bbox_to_anchor=(.025, .14), ncol=3, frameon=False)
    fig.text(.035, .035,
             "Every panel has its own zero-based vertical scale. Read points are trial means; SD is not a confidence interval.\n"
             "Driver/network work is included. Reads follow full verification; CRC32 scans include checksum computation.\n"
             "The final flush request excludes earlier flush work during loading. These are not compression CPU measurements.",
             fontsize=9, linespacing=1.6)
    save_figure(fig, directory, "rocksdb-compression-timings", plt)


def cell(stat, scale=1, digits=4):
    return f"{stat['mean'] / scale:.{digits}f} ± {stat['sample_sd'] / scale:.{digits}f}"


def report(full, stats):
    sizes = [
        "| Payload | Codec | SST MiB | Allocated SST MiB |",
        "| --- | --- | ---: | ---: |",
    ]
    times = [
        "| Payload | Codec | Insert execute s | Load loop s | Final flush ms | Lookup ms | CRC32 scan ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for profile in benchmark.PROFILES:
        for codec in benchmark.CODECS:
            s = stats[profile][codec]
            sizes.append("| " + " | ".join([LABELS[profile], codec,
                cell(s["sst_bytes"], 1048576), cell(s["allocated_sst_bytes"], 1048576)]) + " |")
            times.append("| " + " | ".join([LABELS[profile], codec,
                cell(s["load_execute_seconds"]), cell(s["load_with_generation_seconds"]),
                cell(s["forced_flush_seconds"], .001), cell(s["lookup_ms"]),
                cell(s["scan_ms"])]) + " |")
    compressible = stats["compressible"]
    ratio = compressible["none"]["sst_bytes"]["mean"] / compressible["zstd"]["sst_bytes"]["mean"]
    saved = 100 * (1 - 1 / ratio)
    random = stats["random"]
    random_saved = 100 * (1 - random["zstd"]["sst_bytes"]["mean"] / random["none"]["sst_bytes"]["mean"])
    return f"""# MyRocks compression findings

**Full run:** `{FULL}`, measured October 27, 2026 (Europe/Berlin; run IDs use UTC).
The full run has **32 fresh-volume trials: eight per profile/codec condition**,
**2,097,152 verified row loads, 32,000 timed lookups and 160 timed CRC32 scans**.
The four-trial pilot `{PILOT}` was validated separately and contributes no observations
to these statistics or charts. Evidence was archived in `7dd87e4`.

## Compression changed file size much more for repetitive data

With the same **64 MiB payload per trial**, ZSTD reduced the repetitive table's
mapped SST file lengths from **65.7062 MiB to 3.1850 MiB**: **{saved:.2f}% fewer bytes**.
The no-compression/ZSTD ratio of mean SST bytes was **{ratio:.2f}**.
For the deterministic high-entropy payload, SST lengths changed from **65.7062 MiB
to 65.4158 MiB**, only **{random_saved:.2f}% fewer bytes**.

This is a within-MyRocks result on two synthetic payload profiles. It demonstrates
that a codec option's space benefit depends strongly on the values stored. It does
not turn the earlier OpenFlights results into a compression comparison.

![SST lengths for both payload profiles](figures/rocksdb-compression-size.png)

## Complete file-size summary

All values are **mean ± sample SD across eight trial observations**. MiB is
1,048,576 bytes. The uncompressed SST lengths were identical across their eight
trials; their zero SD is observed, not a missing estimate.

{chr(10).join(sizes)}

Every trial mapped five unique SST files to the table through
`ROCKSDB_DDL`, `ROCKSDB_INDEX_FILE_MAP` and `ROCKSDB_SST_PROPS`. Their entry totals
covered all 65,536 verified rows. Actual file metadata reported `NoCompression` or
`ZSTD` as requested; CF options and file layout were unchanged during timed reads.
The report counts each mapped file once and excludes unrelated system SSTs.

File lengths were inventoried only after a clean database stop, from a read-only
mount. Allocated bytes are Linux `st_blocks × 512` inside the Docker volume.
Both metrics exclude WALs, logs and other datadir files. Neither is a physical SSD
footprint. The earlier [whole-datadir storage study](storage-findings.md) uses a
different metric and dataset.

## Timing observations and their limits

![Insertion, final flush and warm-read trial measurements](figures/rocksdb-compression-timings.png)

{chr(10).join(times)}

For lookups/scans, average the samples within each trial first, then summarize the
eight trial means. Insert/flush measurements have one scalar per trial. Individual
queries are not independent experimental repeats. The chart connects codec trials
from the same round; their fresh volumes and order remain separate. Descriptive
within-round ZSTD/no-compression ratios are retained in the statistics JSON.
No significance test or confidence interval is claimed.

`Insert execute` sums driver execute/completion intervals and excludes this
harness's payload construction. `Load loop` includes construction and loop overhead.
Both include driver/transport and server work. Comparing profiles also changes the
payload bytes and client processing, so codec effects should be considered within a
profile. The final flush timer covers the administrative flush request after loading;
memtable flushes can already have occurred during inserts. These timers do not
decompose compression CPU cost.

Reads follow full streamed verification and 50 untimed point lookups. The MyRocks
block cache was **128 MiB**, larger than the payload. There is no cold-cache or
physical-read claim. CRC32 scans include checksum computation. The warm timings
do not establish a general read-speed benefit, equal CPU cost, or a production
compression policy.

## Mechanism and design

MariaDB's [compression reference](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/myrocks-and-data-compression)
describes per-column-family compression and checking the actual SST codec.
Current settings govern new SSTs, which is why each condition starts on a fresh
volume. Both requested CF policy and actual file metadata are checked.

The schema has one integer primary key and a `VARBINARY(1024)` payload, with no
secondary index. Binary bytes preserve the high-entropy control without character
conversion. The repetitive values contain a row/route prefix and repeated text;
the control uses seeded SHAKE-256 bytes. Both codecs receive the same values and
query IDs within each round/profile.

The only varying supplied CF option is `compression=kNoCompression` versus
`compression=kZSTD`. Both use `bottommost_compression=kDisableCompressionOption`,
a **16 MiB write buffer**, no per-level override and disabled automatic compaction.
Effective CF maps agree apart from the codec after normalizing two process object
addresses. Repetitive values offer much more redundancy than the high-entropy
control, consistent with the observed file-size contrast; individual block decisions
and compression CPU were not inspected.

Disabling automatic compaction makes this a **bounded flush-only study**. It does
not measure steady-state compaction, write amplification, sustained updates, cold
decompression or a production LSM layout.

## Controls, provenance and verification

- Eight rounds balance the four profile/codec conditions: each condition occupies
  each position twice, and each pair appears in either relative order four times.
  Each trial uses a fresh database, the same insert batches and fixed schema.
- The host regenerated ordered SHA-256/CRC32 oracles. All recorded row checks,
  query streams, actual DDL, CF/SST metadata, raw worker outputs and offline file
  inventories were cross-checked. All 32 databases stopped with exit 0 and no
  recorded OOM; all 96 owned containers and 32 volumes were removed afterward.
- MariaDB 11.8.9, runner Python 3.12.15/PyMySQL 1.1.2, Windows host Python 3.10.11
  and WSL2 Linux amd64 containers. Power label: `{full['power_condition']}`.
  DB limits: two CPUs/2 GiB; worker: one CPU/512 MiB. Quotas are not dedicated cores.
  Query cache and binary logging were off; strict/no-substitution mode and
  `rocksdb_flush_log_at_trx_commit=1` were checked.
- Measured commit: `{MEASURED_COMMIT}`, with no tracked edits recorded.
  All eight host source hashes and 25 worker hashes agree with the reviewed sources
  after accounting for Windows source line endings.
- The pilot and full invocations built separately and have different image IDs.
  Images are fixed by immutable ID within each invocation. Matching captured
  source/settings/runtime is not proof of identical image bytes; the exact reason
  for the ID differences is not established. See [image provenance](image-provenance.md).
- These are repeats on one laptop. Host/OS caches, scheduling and temperature remain
  possible influences. The real laptop benchmark is separate from tiny CI
  correctness checks and from a future second-host reproduction.

## Use the result

For a storage-constrained MyRocks table with repetitive values, include ZSTD in a
representative trial and measure its CPU, latency and steady-state compaction costs.
For high-entropy payloads like this control, assume little space benefit until measured.
The [engine decision guide](engine-recommendations.md) keeps transactions, restart
behaviour and the workload's recovery requirements alongside performance and space.

## Reproduce this report without Docker

From the repository root, with the archived evidence present:

```powershell
python -m pip install -r requirements-report.txt
python scripts/report_rocksdb_compression_findings.py
```

On Linux use `python3`. This regenerates seven tracked derived files: this report,
the [32-row CSV](data/rocksdb-compression-observations.csv), the
[statistics/provenance JSON](data/rocksdb-compression-statistics.json) and two figures
in PNG/SVG. It does not start Docker or modify raw evidence. Use `--output-root <dir>`
to write a separate copy of the derived `docs/` tree.

The generator checks pilot/full completeness, source hashes, every raw worker and
inventory, command-log checksums/lifecycle, original summaries and trial statistics
before creating outputs. Floating-point statistics allow only `1e-12` relative/absolute
roundoff; the original evidence is retained. The JSON `-text` attribute preserves
raw bytes needed by command-log hashes. Canonical JSON hashes and LF-normalized
summary hashes are labelled separately.

Rendering uses pinned Matplotlib 3.10.8. Repeated generation in the same environment
is deterministic; fonts, platform or Python/plotting versions can change rendering or
last-bit arithmetic. See [report reproducibility](report-reproducibility.md) and the
[full protocol](rocksdb-compression-method.md).
"""


def build(output_root=ROOT, evidence_root=None):
    pilot, _, pilot_provenance = load("pilot", evidence_root)
    full, full_stats, full_provenance = load("full", evidence_root)
    require(pilot["source_sha256"] == full["source_sha256"]
            and pilot["expected_data"] == full["expected_data"]
            and pilot["trials"][0]["source_sha256"] == full["trials"][0]["source_sha256"],
            "Pilot/full source or data differ")
    rows = observations(full)
    stats = summarize(rows)
    for profile in benchmark.PROFILES:
        for codec in benchmark.CODECS:
            compare_statistics(full_stats[profile][codec], {
                key: stats[profile][codec][key] for key in full_stats[profile][codec]})
    import matplotlib
    data = {
        "format_version": 1, "full_run_id": FULL, "pilot_run_id": PILOT,
        "statistical_unit": "one trial per condition/round; reads are averaged within trial first",
        "pilot_included_in_statistics": False,
        "full_counts": {"trials": len(rows), "row_loads": sum(r["verified_rows"] for r in rows),
                        "timed_lookups": sum(r["lookup_samples"] for r in rows),
                        "timed_crc32_scans": sum(r["scan_samples"] for r in rows)},
        "statistics": stats, "paired_ratios": paired_ratios(rows),
        "recorded_full_statistics": full["statistics"],
        "provenance": {
            mode: {"run_id": result["run_id"], "measured_commit": result["git_commit"],
                   "images": result["images"], "host_source_sha256": result["source_sha256"],
                   "worker_source_sha256": result["trials"][0]["source_sha256"],
                   "host_python": result["host_python"], "docker": result["docker"],
                   "worker_runtime": result["trials"][0]["runtime"],
                   "power_condition": result["power_condition"], **provenance}
            for mode, result, provenance in (("pilot", pilot, pilot_provenance),
                                            ("full", full, full_provenance))},
        "evidence_archive_commit": EVIDENCE_COMMIT,
        "generator_source_sha256_lf": sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "matplotlib_version": matplotlib.__version__,
        "boundaries": [
            "Table-mapped SST file lengths exclude WALs and other datadir files.",
            "Allocated blocks are inside the Docker volume, not physical SSD allocation.",
            "Automatic compaction disabled: no steady-state compaction claim.",
            "Post-verification warm reads, driver/network and CRC32 work included.",
            "No decomposition of server compression CPU cost.",
            "Separate pilot/full image IDs; immutable fixed images within each run.",
            "Single laptop, single client, insert-only synthetic data; pilot excluded.",
        ],
    }
    output_root = Path(output_root)
    data_dir, figure_dir = output_root / "docs/data", output_root / "docs/figures"
    data_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / "rocksdb-compression-observations.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (data_dir / "rocksdb-compression-statistics.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (output_root / "docs/rocksdb-compression-findings.md").write_text(report(full, stats), encoding="utf-8")
    charts(rows, stats, figure_dir)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = build(args.output_root)
    print("Validated 4 pilot and 32 full trials; pilot excluded from full statistics.")
    print("Wrote seven derived files; full trial observations:", result["full_counts"])


if __name__ == "__main__":
    main()
