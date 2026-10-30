"""Protect the published cloud comparison without changing archived evidence."""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from scripts import check_cloud_openflights as cloud
from scripts import report_openflights_findings as findings


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = Path("evidence/reproductions/20261030-cloud-linux-openflights")
ARCHIVE = ROOT / ARCHIVE_PATH


class CloudOpenFlightsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = cloud.load_validator()
        cls.manifest, cls.rows = cls.validator.load_dataset(ROOT / "data/openflights")
        cls.runs = {
            run: json.loads((ROOT / "evidence/openflights" / run / "results.json").read_text())
            for run in (cls.validator.LAPTOP_PILOT, cls.validator.LAPTOP_FULL,
                        cls.validator.CLOUD_PILOT, cls.validator.CLOUD_FULL)
        }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / ARCHIVE_PATH
        shutil.copytree(ARCHIVE, self.archive,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for run in self.runs:
            shutil.copytree(ROOT / "evidence/openflights" / run,
                            self.root / "evidence/openflights" / run)
        shutil.copytree(ROOT / "data/openflights", self.root / "data/openflights")
        for patcher in (mock.patch.object(self.validator, "ROOT", self.root),
                        mock.patch.object(self.validator, "ARCHIVE", self.archive),
                        mock.patch.object(findings, "ROOT", self.root)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_validator(self):
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["validate.py"]), redirect_stdout(output):
            self.assertEqual(self.validator.main(), 0)
        return json.loads(output.getvalue())

    def test_archive_validation_preserves_inputs_and_excludes_pilots(self):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob("*") if p.is_file()}
        result = self.run_validator()
        self.assertEqual(result["validated_runs"], 4)
        self.assertEqual(result["validated_trials"], 60)
        self.assertEqual(result["full_trials_compared"], 50)
        self.assertEqual(result["comparison_records"], 20)
        self.assertTrue(result["pilots_excluded_from_comparison"])
        # The archive is sealed: unlike its pre-sealing maintenance mode, CI
        # must not accept a missing checksum manifest as a successful check.
        self.assertEqual(result["checksum_files"], 59)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in self.root.rglob("*") if p.is_file()})

    def test_changed_comparison_json_or_csv_is_rejected(self):
        for name in ("comparison.json", "comparison.csv"):
            with self.subTest(name=name):
                path = self.archive / name
                original = path.read_bytes()
                if name.endswith("json"):
                    records = json.loads(original)
                    records[0]["cloud_mean"] += 1
                    path.write_text(json.dumps(records))
                else:
                    path.write_bytes(original.replace(b"InnoDB", b"WrongEngine", 1))
                with self.assertRaisesRegex(ValueError, "Stored comparison"):
                    self.run_validator()
                path.write_bytes(original)

    def test_changed_cloud_digest_or_missing_query_sample_is_rejected(self):
        path = self.root / "evidence/openflights" / self.validator.CLOUD_FULL / "results.json"
        original = path.read_bytes()
        for mutation in ("digest", "sample"):
            with self.subTest(mutation=mutation):
                result = json.loads(original)
                if mutation == "digest":
                    result["dataset_sha256"] = "0" * 64
                else:
                    result["trials"][0]["lookup_ms"].pop()
                path.write_text(json.dumps(result))
                with self.assertRaises(ValueError):
                    findings.validate_run(self.validator.CLOUD_FULL, False,
                                          self.manifest, self.rows)
                path.write_bytes(original)

    def test_changed_measured_source_is_rejected(self):
        path = self.archive / "measured-source/benchmarks/openflights.py"
        path.write_bytes(path.read_bytes() + b"\n# changed source\n")
        with self.assertRaisesRegex(ValueError, "Cloud measured source snapshot differs"):
            self.validator.validate_sources(self.runs[self.validator.LAPTOP_FULL],
                                            self.runs[self.validator.CLOUD_FULL])

    def test_changed_archived_bytes_or_incomplete_checksum_coverage_is_rejected(self):
        path = self.archive / "logs/setup-transcript.txt"
        original = path.read_bytes()
        path.write_bytes(original + b"\nchanged archive bytes\n")
        with self.assertRaisesRegex(ValueError, "Archive checksum differs"):
            self.validator.validate_checksums()
        path.write_bytes(original)
        manifest = self.archive / "sha256.json"
        hashes = json.loads(manifest.read_text())
        hashes.pop((ARCHIVE_PATH / "comparison.csv").as_posix())
        manifest.write_text(json.dumps(hashes))
        with self.assertRaisesRegex(ValueError, "does not cover exactly"):
            self.validator.validate_checksums()

    def test_missing_published_checksum_manifest_is_rejected(self):
        (self.archive / "sha256.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing sealed archive checksum"):
            self.validator.validate_checksums()

    def test_current_checker_rejects_write_before_loading_archive(self):
        with mock.patch.object(sys, "argv", ["check_cloud_openflights.py", "--write"]), \
                mock.patch.object(cloud, "load_validator") as load, \
                mock.patch.object(sys, "stderr", io.StringIO()), \
                self.assertRaises(SystemExit) as error:
            cloud.main()
        self.assertEqual(error.exception.code, 2)
        load.assert_not_called()

    def test_checksum_keys_use_portable_separators(self):
        # Model Windows' native relative-path rendering on either test host.
        # A regression to str(relative_path) would mismatch the sealed '/' keys.
        class RelativePath:
            def __init__(self, path):
                self.path = path

            def __str__(self):
                return str(self.path).replace("/", "\\")

            def as_posix(self):
                return self.path.as_posix()

        class WindowsRenderedRelativePaths(type(Path())):
            def relative_to(self, *parts):
                return RelativePath(super().relative_to(*parts))

        with mock.patch.object(self.validator, "ROOT", WindowsRenderedRelativePaths(self.root)), \
                mock.patch.object(self.validator, "ARCHIVE", WindowsRenderedRelativePaths(self.archive)):
            self.assertEqual(self.validator.validate_checksums(), 59)

    def test_pilot_cannot_be_compared_as_a_full_run(self):
        pilot = copy.deepcopy(self.runs[self.validator.CLOUD_PILOT])
        with self.assertRaisesRegex(ValueError, "Pilot cannot enter"):
            self.validator.comparison_records(self.runs[self.validator.LAPTOP_FULL], pilot)


if __name__ == "__main__":
    unittest.main()
