"""Summarize trial means without treating individual queries as independent trials."""
from .core import ENGINES, describe


def summarize(trials):
    result = []
    for engine in ENGINES:
        matching = [t for t in trials if t["engine"] == engine]
        if not matching:
            continue
        for metric, unit, values in (
            ("load", "s", [t["load_seconds"] for t in matching]),
            ("point_lookup", "ms", [describe(t["lookup_ms"])["mean"] for t in matching]),
            ("full_scan", "ms", [describe(t["scan_ms"])["mean"] for t in matching]),
        ):
            result.append({"engine": engine, "metric": metric, "unit": unit,
                           **describe(values)})
    return result


def markdown(result):
    if result["status"] != "completed":
        raise ValueError("Cannot produce a completed report for a failed or partial run")
    config = result["config"]
    lines = ["# Local baseline results", "",
             "Run: " + result["run_id"], "",
             f"{config['rows']} synthetic rows; {config['rounds']} load/read rounds per engine.",
             "Warm/post-verification reads; single client; client-observed timings.",
             "This is a baseline, not a general ranking or a durability-equivalent comparison.", "",
             "| Engine | Metric | Unit | Trials | Mean | Sample SD | Min | Max |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in summarize(result["trials"]):
        sd = "n/a" if row["sample_sd"] is None else f"{row['sample_sd']:.4f}"
        lines.append(f"| {row['engine']} | {row['metric']} | {row['unit']} | {row['n']} | "
                     f"{row['mean']:.4f} | {sd} | {row['min']:.4f} | {row['max']:.4f} |")
    lines += ["", "SD for reads is across per-round query means; raw individual timings are in results.json.",
              "Trials reuse one server and are not independent machine replications.",
              "Load completion does not establish equal persistence or compaction completion.",
              "See docs/benchmark-method.md for design, settings and limitations.", ""]
    return "\n".join(lines)
