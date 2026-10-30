"""Validate the four archived runs and this full-run comparison without Docker.

Run from any directory after fetching the pinned dataset with
``python scripts/fetch_openflights.py``. ``--write`` updates only comparison.json
and comparison.csv; default mode verifies their existing values and archive hashes.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import statistics
import sys

ARCHIVE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from benchmarks.core import ENGINES
from benchmarks.openflights_data import load_dataset
from scripts.report_openflights_findings import validate_run


LAPTOP_PILOT = "20261009T152651Z-openflights-b44366ef"
LAPTOP_FULL = "20261009T160813Z-openflights-6884f225"
CLOUD_PILOT = "20261030T184911Z-openflights-329f0869"
CLOUD_FULL = "20261030T184936Z-openflights-85032cd6"
METRICS = ("load_seconds", "lookup_ms", "scan_ms", "source_ms")
FIELDS = ("engine", "metric", "unit", "trials_per_host", "laptop_mean",
          "laptop_sample_sd", "cloud_mean", "cloud_sample_sd", "percent_difference")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_hashes(relative):
    path = ARCHIVE / "measured-source" / relative
    require(path.is_file(), "Missing measured source snapshot: " + relative)
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return {hashlib.sha256(value).hexdigest()
            for value in (raw, lf, lf.replace(b"\n", b"\r\n"))}


def validate_sources(laptop, cloud):
    old, new = laptop["source_sha256"], cloud["source_sha256"]
    for relative, digest in new.items():
        path = ARCHIVE / "measured-source" / relative
        require(path.is_file(), "Missing cloud measured source snapshot: " + relative)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                "Cloud measured source snapshot differs from captured bytes: " + relative)
    required = {"benchmarks/openflights.py", "benchmarks/openflights_data.py",
                "benchmarks/core.py", "benchmarks/run.py", "scripts/fetch_openflights.py",
                "data/openflights/manifest.json", "requirements.txt", "compose.yaml",
                "docker/mariadb/Dockerfile", "docker/mariadb/rocksdb.cnf"}
    required.update("sql/openflights/" + engine.lower() + ".sql" for engine in ENGINES)
    require(required <= old.keys() and required <= new.keys(),
            "Missing comparison-source fingerprint")
    common = (old.keys() & new.keys()) - {"Dockerfile"}
    for relative in common:
        candidates = source_hashes(relative)
        require(old[relative] in candidates and new[relative] in candidates,
                "Compared measured source changed beyond LF/CRLF: " + relative)
    # The runner Dockerfile gained auxiliary COPY entries after the laptop run.
    # Its historical fingerprint is preserved, but identical images are not claimed.
    require(new["Dockerfile"] in source_hashes("Dockerfile"),
            "Cloud runner Dockerfile differs from measured source snapshot")
    return len(common)


def compare_conditions(laptop, cloud):
    for field in ("config", "dataset", "dataset_sha256", "scan_oracle", "schedule",
                  "cache_condition", "server_version", "global_variables", "session_variables"):
        require(laptop[field] == cloud[field], "Cross-host condition differs: " + field)
    for left, right in zip(laptop["trials"], cloud["trials"]):
        for field in ("engine", "round", "position", "verified_rows", "verified_dataset_sha256",
                      "lookup_ids", "source_ids", "source_result_counts"):
            require(left[field] == right[field], "Cross-host trial differs: " + field)
    for field in ("python", "pymysql", "cgroup_memory_max", "cgroup_cpu_max"):
        require(laptop["runtime"][field] == cloud["runtime"][field],
                "Cross-host runner control differs: " + field)


def full_statistics(result, engine, metric):
    trials = [trial for trial in result["trials"] if trial["engine"] == engine]
    require(len(trials) == 5, "Expected five full-run trials per engine")
    values = [trial[metric] if metric == "load_seconds" else statistics.mean(trial[metric])
              for trial in trials]
    mean, sd = statistics.mean(values), statistics.stdev(values)
    saved = result["statistics"][engine][metric]
    require(saved["n"] == 5 and saved["mean"] == mean and saved["sample_sd"] == sd,
            "Full-run statistics differ from independent calculation")
    return mean, sd


def comparison_records(laptop, cloud):
    require(not laptop["config"]["pilot"] and not cloud["config"]["pilot"],
            "Pilot cannot enter full-run comparison")
    records = []
    for engine in ENGINES:
        for metric in METRICS:
            left, left_sd = full_statistics(laptop, engine, metric)
            right, right_sd = full_statistics(cloud, engine, metric)
            require(left > 0, "Cannot calculate relative change from zero")
            records.append(dict(engine=engine, metric=metric,
                unit="s" if metric == "load_seconds" else "ms", trials_per_host=5,
                laptop_mean=left, laptop_sample_sd=left_sd,
                cloud_mean=right, cloud_sample_sd=right_sd,
                percent_difference=100 * (right / left - 1)))
    require(len(records) == 20, "Expected twenty comparison records")
    return records


def comparison_csv(records):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def validate_checksums():
    manifest = ARCHIVE / "sha256.json"
    if not manifest.exists():
        return None
    hashes = json.loads(manifest.read_text(encoding="utf-8"))
    require(isinstance(hashes, dict) and bool(hashes), "Empty or invalid checksum manifest")
    allowed = (ARCHIVE, ROOT / "evidence/openflights" / CLOUD_PILOT,
               ROOT / "evidence/openflights" / CLOUD_FULL)
    expected = {str(path.relative_to(ROOT)) for folder in allowed
                for path in folder.rglob("*") if path.is_file() and path != manifest}
    require(set(hashes) == expected, "Checksum manifest does not cover exactly the archive/new runs")
    for relative, digest in hashes.items():
        path = ROOT / relative
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "Unsafe checksum path")
        require(any(folder in path.resolve().parents for folder in allowed)
                and not path.is_symlink() and path.is_file(), "Checksum path outside archive/new runs")
        require(isinstance(digest, str) and len(digest) == 64
                and all(character in "0123456789abcdef" for character in digest),
                "Invalid SHA-256 value")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                "Archive checksum differs: " + relative)
    return len(hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="Write comparison JSON/CSV after validation; skip archive hashes")
    args = parser.parse_args()
    manifest, rows = load_dataset(ROOT / "data/openflights")
    runs = {}
    for run_id, pilot in ((LAPTOP_PILOT, True), (LAPTOP_FULL, False),
                          (CLOUD_PILOT, True), (CLOUD_FULL, False)):
        result, _ = validate_run(run_id, pilot, manifest, rows)
        runs[run_id] = result
    for pilot_id, full_id in ((LAPTOP_PILOT, LAPTOP_FULL), (CLOUD_PILOT, CLOUD_FULL)):
        for field in ("source_sha256", "runtime", "server_version", "global_variables",
                      "session_variables", "power_condition"):
            require(runs[pilot_id][field] == runs[full_id][field],
                    "Within-host pilot/full conditions differ: " + field)
    compare_conditions(runs[LAPTOP_PILOT], runs[CLOUD_PILOT])
    compare_conditions(runs[LAPTOP_FULL], runs[CLOUD_FULL])
    common_sources = validate_sources(runs[LAPTOP_FULL], runs[CLOUD_FULL])
    records = comparison_records(runs[LAPTOP_FULL], runs[CLOUD_FULL])
    json_path, csv_path = ARCHIVE / "comparison.json", ARCHIVE / "comparison.csv"
    if args.write:
        json_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        csv_path.write_text(comparison_csv(records), encoding="utf-8", newline="")
    else:
        require(json.loads(json_path.read_text(encoding="utf-8")) == records,
                "Stored comparison JSON differs from recalculation")
        require(csv_path.read_text(encoding="utf-8") == comparison_csv(records),
                "Stored comparison CSV differs from recalculation")
    checksums = None if args.write else validate_checksums()
    ranges = {metric: [min(row["percent_difference"] for row in records if row["metric"] == metric),
                       max(row["percent_difference"] for row in records if row["metric"] == metric)]
              for metric in ("load_seconds", "scan_ms")}
    print(json.dumps(dict(status="passed", validated_runs=4, validated_trials=60,
        cloud_trials=30, full_trials_compared=50, comparison_records=len(records),
        common_sources_validated=common_sources, checksum_files=checksums,
        pilots_excluded_from_comparison=True, percent_difference_ranges=ranges), indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, TypeError) as error:
        print("VALIDATION FAILED:", str(error), file=sys.stderr)
        sys.exit(1)
