"""Keep the browser table in step with the reader command and check the publication boundary."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import compare_openflights_laptops as laptops


class LaptopComparisonTests(unittest.TestCase):
    def test_published_table_matches_original_raw_and_peer_csv(self):
        original = laptops.read_run((laptops.FIRST / 'results.json').read_bytes(),
                                    (laptops.FIRST / 'summary.md').read_bytes(), laptops.FIRST.name, False)
        text = '\n'.join(laptops.table(laptops.rounded(original), laptops.published()))
        self.assertIn(text, (laptops.ARCHIVE / 'README.md').read_text(encoding='utf-8'))

    def test_same_size_unreviewed_archive_rejected_before_zip_is_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'unreviewed.zip'
            path.write_bytes(b'x' * 115943)
            with patch.object(laptops.zipfile, 'ZipFile') as opener, self.assertRaisesRegex(ValueError, 'SHA-256'):
                laptops.checked_handoff(path, {}, {})
        opener.assert_not_called()

    def test_export_is_four_fixed_files_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'new'
            files = {n: ('proof of bytes ' + n).encode() for n in laptops.PUBLIC_FILES}
            with self.assertRaisesRegex(ValueError, 'Unexpected public file list'):
                laptops.save_public(dict(files, **{'private/commands.json': b'private'}), root)
            self.assertFalse(root.exists())
            laptops.save_public(files, root)
            self.assertEqual({p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()},
                             files)
            with self.assertRaises(FileExistsError):
                laptops.save_public(files, root)
