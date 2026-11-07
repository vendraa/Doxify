import os
import tempfile
import time
import unittest
from pathlib import Path

from app.utils.temp import SessionTempDir, cleanup_stale_temp_dirs


class TempTests(unittest.TestCase):
    def test_dir_removed_after_use_even_on_error(self):
        paths = []
        with self.assertRaises(RuntimeError):
            with SessionTempDir() as d:
                paths.append(d)
                (d / "x.bin").write_bytes(b"1")
                raise RuntimeError("boom")
        self.assertFalse(paths[0].exists())

    def test_random_unique_names(self):
        with SessionTempDir() as a, SessionTempDir() as b:
            self.assertNotEqual(a, b)
            self.assertTrue(a.name.startswith("doxify_"))

    def test_stale_cleanup_only_old_doxify_dirs(self):
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            old = base / "doxify_old"; old.mkdir()
            new = base / "doxify_new"; new.mkdir()
            other = base / "bukan_doxify"; other.mkdir()
            past = time.time() - 7200
            os.utime(old, (past, past)); os.utime(other, (past, past))
            self.assertEqual(cleanup_stale_temp_dirs(600, base), 1)
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())
            self.assertTrue(other.exists())


if __name__ == "__main__":
    unittest.main()
