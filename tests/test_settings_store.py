import json
import tempfile
import unittest
from pathlib import Path

from app.converters.base import ConversionSettings, PageSize, Quality
from app.utils.settings_store import SettingsStore, UserSettings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "sub" / "settings.json"
        self.store = SettingsStore(self.path)

    def test_defaults_match_prd(self):
        s = UserSettings()
        self.assertEqual((s.output_mode, s.page_size, s.orientation, s.margin, s.quality),
                         ("merged", "a4", "auto", "small", "original"))
        self.assertTrue(s.strip_metadata)

    def test_missing_file_gives_defaults(self):
        self.assertEqual(self.store.load(), UserSettings())

    def test_roundtrip(self):
        s = UserSettings(output_mode="separate", page_size="letter", orientation="landscape",
                         margin="none", quality="compressed", jpeg_quality=50,
                         strip_metadata=False, last_output_dir="C:/Hasil")
        self.assertTrue(self.store.save(s))
        self.assertEqual(self.store.load(), s)

    def test_corrupt_json_gives_defaults(self):
        self.path.parent.mkdir(parents=True); self.path.write_text("{bukan json")
        self.assertEqual(self.store.load(), UserSettings())

    def test_invalid_values_replaced_individually(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({
            "page_size": "letter", "orientation": "miring", "margin": 5, "jpeg_quality": 9999,
            "strip_metadata": "ya", "last_output_dir": 123, "quality": "compressed",
        }))
        s = self.store.load()
        self.assertEqual(s.page_size, "letter")       # valid dipertahankan
        self.assertEqual(s.quality, "compressed")
        self.assertEqual(s.orientation, "auto")       # tidak valid -> default
        self.assertEqual(s.margin, "small")
        self.assertEqual(s.jpeg_quality, 95)          # dijepit ke batas
        self.assertTrue(s.strip_metadata)
        self.assertEqual(s.last_output_dir, "")

    def test_non_dict_json_gives_defaults(self):
        self.path.parent.mkdir(parents=True); self.path.write_text("[1,2,3]")
        self.assertEqual(self.store.load(), UserSettings())

    def test_bool_not_accepted_as_jpeg_quality(self):
        self.assertEqual(UserSettings.from_dict({"jpeg_quality": True}).jpeg_quality, 75)

    def test_save_failure_returns_false_not_raises(self):
        blocker = Path(self.tmp.name) / "file"; blocker.write_text("x")
        self.assertFalse(SettingsStore(blocker / "settings.json").save(UserSettings()))

    def test_no_tmp_files_left(self):
        self.store.save(UserSettings())
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["settings.json"])

    def test_saved_file_contains_no_filenames(self):
        self.store.save(UserSettings())
        self.assertNotIn(".jpg", self.path.read_text())

    def test_to_conversion_settings(self):
        cs = UserSettings(page_size="letter", quality="compressed", jpeg_quality=60).to_conversion_settings(overwrite=True)
        self.assertIsInstance(cs, ConversionSettings)
        self.assertEqual((cs.page_size, cs.quality, cs.jpeg_quality, cs.overwrite),
                         (PageSize.LETTER, Quality.COMPRESSED, 60, True))


class ArchitectureTests(unittest.TestCase):
    """NFR-08: converters/ dan utils/ tidak boleh bergantung pada ui/ atau Qt."""

    def test_core_does_not_import_ui_or_qt(self):
        import ast
        root = Path(__file__).resolve().parent.parent / "app"
        offenders = []
        for sub in ("converters", "utils"):
            for py in (root / sub).rglob("*.py"):
                for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        names = [node.module]
                    offenders += [(py.name, n) for n in names if n.startswith(("app.ui", "PySide6", "PyQt"))]
        self.assertEqual(offenders, [])

    def test_logic_module_does_not_import_qt(self):
        src = (Path(__file__).resolve().parent.parent / "app" / "ui" / "logic.py").read_text(encoding="utf-8")
        self.assertNotIn("PySide6", src)


if __name__ == "__main__":
    unittest.main()
