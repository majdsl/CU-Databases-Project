"""Reject misleading compression reports, including under optimized Python."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import report_rocksdb_compression_findings as findings


class CompressionFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = json.loads((findings.EVIDENCE / findings.FULL / "results.json").read_text())

    def test_archive_and_trial_statistical_unit(self):
        pilot, _, _ = findings.load("pilot")
        full, _, _ = findings.load("full")
        rows = findings.observations(full)
        stats = findings.summarize(rows)
        self.assertEqual(len(pilot["trials"]), 4)
        self.assertEqual(len(rows), 32)
        self.assertEqual(sum(r["lookup_samples"] for r in rows), 32000)
        self.assertEqual(sum(r["scan_samples"] for r in rows), 160)
        for profile in stats.values():
            for condition in profile.values():
                self.assertTrue(all(s["n"] == 8 for s in condition.values()))

    def test_sql_runtime_and_provenance_changes_rejected(self):
        mutations = [
            lambda r: r["trials"][0]["global_variables"].update(query_cache_type="ON"),
            lambda r: r["trials"][0]["session_variables"].update(autocommit="OFF"),
            lambda r: r["trials"][0]["runtime"].update(cgroup_cpu_max="200000 100000"),
            lambda r: r["source_sha256"].update({"benchmarks/rocksdb_compression.py": "wrong"}),
            lambda r: r["trials"][0].update(actual_ddl="CREATE TABLE wrong (id INT) ENGINE=ROCKSDB"),
            lambda r: [r["trials"][0][name].update(BLOCK_SIZE="8192")
                       for name in ("cf_options_before", "cf_options_after")],
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                result = copy.deepcopy(self.full)
                mutate(result)
                with self.assertRaises(ValueError):
                    findings.validate(result, findings.FULL, "full")

    def test_incomplete_and_inconsistent_run_rejected(self):
        mutations = [
            lambda r: r.update(status="failed"),
            lambda r: r["trials"].pop(),
            lambda r: r["trials"][0]["clean_stop"].update(ExitCode=137),
            lambda r: r["trials"][0]["table_sst"].update(bytes=1),
            lambda r: r["trials"][0]["resource_cleanup"].update(volume_removed=False),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                result = copy.deepcopy(self.full)
                mutate(result)
                with self.assertRaises(ValueError):
                    findings.validate(result, findings.FULL, "full")

    def test_only_floating_roundoff_is_accepted(self):
        result = copy.deepcopy(self.full)
        stat = result["statistics"]["random"]["none"]["scan_ms"]
        stat["sample_sd"] += 1e-16
        findings.validate(result, findings.FULL, "full")
        stat["sample_sd"] += .01
        with self.assertRaises(ValueError):
            findings.validate(result, findings.FULL, "full")
        with self.assertRaises(ValueError):
            findings.compare_statistics({"n": 8}, {"n": 9})
        with self.assertRaises(ValueError):
            findings.compare_statistics({"n": 8.0}, {"n": 8})

    def test_raw_tamper_rejected_before_outputs(self):
        for kind in ("worker", "inventory", "command bytes", "network namespace"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                evidence = root / "evidence"
                shutil.copytree(findings.EVIDENCE / findings.PILOT, evidence / findings.PILOT)
                folder = evidence / findings.PILOT
                if kind in ("worker", "inventory"):
                    name = "trial-01.json" if kind == "worker" else "trial-01-inventory.json"
                    path = folder / name
                    value = json.loads(path.read_text())
                    if kind == "worker":
                        value["verified_rows"] = 0
                    else:
                        value[0]["bytes"] += 1
                    path.write_text(json.dumps(value))
                elif kind == "command bytes":
                    with (folder / "commands.json").open("ab") as f:
                        f.write(b"\n")
                else:
                    path = folder / "commands.json"
                    commands = json.loads(path.read_text())
                    for command in commands:
                        args = command["argv"]
                        if "--network" in args and args[args.index("--network") + 1].startswith("container:"):
                            args[args.index("--network") + 1] = "host"
                            break
                    path.write_text(json.dumps(commands))
                    result_path = folder / "results.json"
                    result = json.loads(result_path.read_text())
                    result["commands_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                    result_path.write_text(json.dumps(result))
                output = root / "output"
                with self.assertRaises(ValueError):
                    findings.build(output, evidence_root=evidence)
                self.assertFalse(output.exists())

    def test_generation_repeats_and_preserves_evidence(self):
        evidence_files = [p for p in findings.EVIDENCE.rglob("*") if p.is_file()]
        original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_files}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first", root / "second"
            data = findings.build(first)
            findings.build(second)
            files = [p.relative_to(first) for p in first.rglob("*") if p.is_file()]
            self.assertEqual(len(files), 7)
            for path in files:
                self.assertEqual((first / path).read_bytes(), (second / path).read_bytes(), str(path))
            self.assertEqual(data["full_counts"], {
                "trials": 32, "row_loads": 2097152, "timed_lookups": 32000, "timed_crc32_scans": 160,
            })
            self.assertFalse(data["pilot_included_in_statistics"])
            with (first / "docs/data/rocksdb-compression-observations.csv").open(newline="") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 32)
        self.assertEqual(original, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_files})


if __name__ == "__main__":
    unittest.main()
