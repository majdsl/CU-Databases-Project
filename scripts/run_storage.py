"""Run isolated storage measurements. Host Python needs only the standard library."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.core import Config, ENGINES, dataset_digest, engine_schedule, generate_rows
from benchmarks.run import save_json

PROJECT_PATTERN = re.compile(r"cu-storage-[0-9a-f]{32}-[0-9]+\Z")


def execute(arguments, capture=False):
    result = subprocess.run(arguments, cwd=ROOT, check=True, text=True,
                            encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def compose(project, *arguments, capture=False):
    if not PROJECT_PATTERN.fullmatch(project):
        raise ValueError("Refusing a project name outside the isolated storage namespace")
    return execute(["docker", "compose", "--env-file", str(ROOT / ".env"),
                    "-f", str(ROOT / "compose.storage.yaml"), "-p", project,
                    *arguments], capture=capture)


def ensure_new_project(project):
    for resource in ("container", "volume", "network"):
        names = execute(["docker", resource, "ls", "-q", "--filter",
                         "label=com.docker.compose.project=" + project,
                         *(["-a"] if resource == "container" else [])], capture=True)
        if names:
            raise RuntimeError("Isolated project already has resources; refusing reuse")


def db_state(project):
    container = compose(project, "ps", "-a", "-q", "db", capture=True)
    if not container or len(container.splitlines()) != 1:
        raise RuntimeError("Expected exactly one isolated database container")
    state = json.loads(execute(["docker", "inspect", "--format", "{{json .State}}", container], capture=True))
    return container, state


def stop_cleanly(project):
    compose(project, "stop", "-t", "120", "db")
    container, state = db_state(project)
    if state.get("Status") != "exited" or state.get("ExitCode") != 0 or state.get("OOMKilled"):
        raise RuntimeError("Database did not stop cleanly; refusing storage measurement")
    return {key: state.get(key) for key in ("Status", "ExitCode", "OOMKilled", "FinishedAt")}


def snapshot(project):
    _, state = db_state(project)
    if state.get("Status") != "exited" or state.get("ExitCode") != 0:
        raise RuntimeError("File inventory requires the database to be cleanly stopped")
    return json.loads(compose(project, "run", "--rm", "--no-deps", "-T", "snapshot", capture=True))


def size_delta(before, after):
    return {key: after[key] - before[key] for key in
            ("regular_file_apparent_bytes", "regular_file_allocated_bytes")}


def render_report(result):
    if result["status"] != "completed":
        raise ValueError("Incomplete run cannot have a success report")
    expected = len(ENGINES) * result["rounds"]
    if len(result["trials"]) != expected:
        raise ValueError("Incomplete trial set")
    lines = ["# Storage footprint " + ("pilot" if result["pilot"] else "experiment"), "",
             "Run: " + result["run_id"], "",
             f"{result['rows']} identical synthetic rows; {result['rounds']} fresh-volume trial(s) per engine.",
             "Every dataset verified before shutdown. Bytes below are not interchangeable metrics.", "",
             "| Engine | Round | Before allocated bytes | After allocated bytes | Allocated delta bytes | Apparent delta bytes |",
             "| --- | --- | --- | --- | --- | --- |"]
    for trial in result["trials"]:
        before, after, delta = trial["before"], trial["after"], trial["delta"]
        lines.append(f"| {trial['engine']} | {trial['round']} | {before['regular_file_allocated_bytes']} | "
                     f"{after['regular_file_allocated_bytes']} | {delta['regular_file_allocated_bytes']} | "
                     f"{delta['regular_file_apparent_bytes']} |")
    lines += ["", "Allocated bytes are Linux filesystem blocks for regular files in the entire isolated datadir.",
              "The delta includes table creation, logs, metadata, and startup/shutdown side effects; it is not table-only size.",
              "Apparent bytes are file lengths. Neither metric is Windows VHDX size or total physical SSD usage.",
              "Negative deltas are retained: log removal or truncation can outweigh new allocations.",
              "MEMORY loses its rows at shutdown: its disk delta measures metadata/overhead, not stored row data.", "",
              "## Live engine-reported allocation (before shutdown)", "",
              "| Engine | Round | Data_length | Index_length | Interpretation |", "| --- | --- | --- | --- | --- |"]
    for trial in result["trials"]:
        status = trial["load"]["live_engine_reported_table_status"]
        meaning = "Approximate RAM allocation" if trial["engine"] == "MEMORY" else "Engine-reported statistics; not a filesystem measurement"
        lines.append(f"| {trial['engine']} | {trial['round']} | {status.get('Data_length', 'n/a')} | "
                     f"{status.get('Index_length', 'n/a')} | {meaning} |")
    lines += ["", "No forced MyRocks compaction or claim of steady-state storage. No compression-ratio claim.",
              "Fresh volumes isolate trials; all trials still share the same host and filesystem.",
              "A pilot verifies the procedure; one observation per engine is insufficient for a stable ranking.",
              "Full file inventories, checksums, settings, image IDs and source hashes are in results.json.",
              "See docs/storage-method.md for protocol and limitations.", ""]
    return "\n".join(lines)


def run(args):
    config = Config(rows=args.rows, seed=args.seed)
    config.validate()
    if not (ROOT / ".env").is_file():
        raise ValueError("Run from the existing project with its .env file; do not upload .env")
    if execute(["docker", "info", "--format", "{{.OSType}}"], capture=True) != "linux":
        raise RuntimeError("Docker must be running Linux containers")
    compose_version = execute(["docker", "compose", "version", "--short"], capture=True)
    token = uuid.uuid4().hex
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-storage-" + token[:8]
    directory = ROOT / "results" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    schedule = engine_schedule(args.seed, 5)
    if args.pilot:
        schedule = schedule[:1]
    result = {"format_version": 1, "experiment": "isolated_storage", "status": "running",
              "run_id": run_id, "pilot": args.pilot, "rows": args.rows, "seed": args.seed,
              "rounds": len(schedule), "schedule": schedule, "compose_version": compose_version,
              "host_python": sys.version, "power_condition": args.power_condition,
              "dataset_sha256": dataset_digest(generate_rows(config)), "trials": [],
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in ("scripts/run_storage.py", "compose.storage.yaml", "benchmarks/storage.py")}}
    save_json(directory / "results.json", result)
    current = None
    try:
        for round_index, order in enumerate(schedule, 1):
            for engine in order:
                project = f"cu-storage-{token}-{len(result['trials']) + 1}"
                ensure_new_project(project)
                current = project
                result["active_project"] = project
                save_json(directory / "results.json", result)
                print(f"Storage round {round_index}/{len(schedule)}: {engine}", flush=True)
                if not result["trials"]:
                    compose(project, "build", "db", "runner")
                compose(project, "up", "-d", "--wait", "--wait-timeout", "180", "db")
                container, _ = db_state(project)
                image_id = execute(["docker", "inspect", "--format", "{{.Image}}", container], capture=True)
                runner_image = execute(["docker", "image", "inspect", "--format", "{{.Id}}",
                                        "cu-engine-lab-storage-runner:local"], capture=True)
                before_stop = stop_cleanly(project)
                before = snapshot(project)
                compose(project, "up", "-d", "--wait", "--wait-timeout", "180", "db")
                loaded = json.loads(compose(project, "run", "--rm", "--no-deps", "-T", "runner",
                                             "python", "-m", "benchmarks.storage", "load", "--engine", engine,
                                             "--rows", str(args.rows), "--seed", str(args.seed), capture=True))
                if loaded["verified_dataset_sha256"] != result["dataset_sha256"] or loaded["verified_rows"] != args.rows:
                    raise RuntimeError("Host/runner dataset validation mismatch")
                after_stop = stop_cleanly(project)
                after = snapshot(project)
                result["trials"].append({"engine": engine, "round": round_index, "project": project,
                                         "db_image_id": image_id, "runner_image_id": runner_image,
                                         "before_stop": before_stop, "after_stop": after_stop,
                                         "load": loaded, "before": before, "after": after,
                                         "delta": size_delta(before, after)})
                save_json(directory / "results.json", result)
                # This exact project was verified absent, then created by this invocation.
                # No access to the normal cu-engine-lab project or db_data volume.
                compose(project, "down", "--volumes", "--timeout", "120")
                current = None
                result.pop("active_project", None)
                save_json(directory / "results.json", result)
        result["status"] = "completed"
        summary = render_report(result)
        (directory / "summary.md").write_text(summary, encoding="utf-8")
        save_json(directory / "results.json", result)
        print(summary)
        print("Saved:", directory)
    except BaseException as error:
        result["status"] = "failed"
        result["error_type"] = type(error).__name__
        if current:
            # Retain the failed trial's isolated volume for diagnosis; stop its server.
            try:
                compose(current, "stop", "-t", "120", "db")
            except (Exception, KeyboardInterrupt):
                result["stop_on_failure"] = "failed; check the isolated project"
        (directory / "summary.md").unlink(missing_ok=True)
        save_json(directory / "results.json", result)
        print("Partial results:", directory, file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", help="One fresh-volume trial per engine instead of five")
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--power-condition", default="not recorded")
    args = parser.parse_args()
    try:
        run(args)
    except (Exception, KeyboardInterrupt) as error:
        print("FAILED:", str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
