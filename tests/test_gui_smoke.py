"""Tes smoke GUI. Dilewati otomatis jika PySide6 belum terpasang.

Jalankan di Windows setelah `pip install -r requirements.txt`:
    python -m unittest tests.test_gui_smoke -v
Memakai platform Qt 'offscreen' sehingga tidak ada jendela yang muncul.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.ui.main_window import MainWindow
    HAS_QT = True
except ImportError:  # pragma: no cover
    HAS_QT = False

from app.utils.settings_store import SettingsStore
from tests.helpers import make_jpeg, make_png


@unittest.skipUnless(HAS_QT, "PySide6 belum terpasang")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.store = SettingsStore(self.dir / "cfg" / "settings.json")
        for target in ("exec",):
            p = mock.patch.object(QMessageBox, target, return_value=0)
            p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(QMessageBox, "critical"); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes)
        p.start(); self.addCleanup(p.stop)
        self.win = MainWindow(self.store)
        self.win._show_result = mock.Mock()  # hindari dialog modal
        self.addCleanup(self.win.close)

    def images(self, n=3):
        return [make_jpeg(self.dir / f"foto{i}.jpg", size=(300 + i, 200)) for i in range(n)]

    def run_conversion(self, output, overwrite=False, timeout_ms=30000):
        loop, got = QEventLoop(), []
        self.win.conversion_finished.connect(lambda r: (got.append(r), loop.quit()))
        self.win.start_conversion(output, overwrite)
        if not got:
            QTimer.singleShot(timeout_ms, loop.quit)
            loop.exec()
        self.assertTrue(got, "konversi tidak selesai tepat waktu")
        return got[0]

    # ---- daftar -----------------------------------------------------------

    def test_add_files_updates_list_and_buttons(self):
        self.assertFalse(self.win.btn_convert.isEnabled())
        self.win.add_paths(self.images(3))
        self.assertEqual(self.win.list_widget.count(), 3)
        self.assertTrue(self.win.btn_convert.isEnabled())
        self.assertIn("3 gambar", self.win.count_label.text())

    def test_unsupported_file_rejected_without_crash(self):
        txt = self.dir / "x.txt"; txt.write_text("x")
        self.win.add_paths([txt, *self.images(1)])
        self.assertEqual(self.win.list_widget.count(), 1)

    def test_reorder_buttons_and_drag_request(self):
        imgs = self.images(4)
        self.win.add_paths(imgs)
        self.win.list_widget.item(2).setSelected(True)
        self.win.on_move_up()
        self.assertEqual([p.name for p in self.win.state.paths], ["foto0.jpg", "foto2.jpg", "foto1.jpg", "foto3.jpg"])
        self.win.on_move_requested([0], 4)  # seperti menyeret item pertama ke akhir
        self.assertEqual(self.win.state.paths[-1].name, "foto0.jpg")
        self.assertEqual(self.win.list_widget.paths()[-1], str(imgs[0]))

    def test_remove_and_clear(self):
        self.win.add_paths(self.images(3))
        self.win.list_widget.item(1).setSelected(True)
        self.win.on_remove_clicked()
        self.assertEqual(self.win.list_widget.count(), 2)
        self.win.on_clear_clicked()
        self.assertEqual(self.win.list_widget.count(), 0)
        self.assertFalse(self.win.btn_convert.isEnabled())

    # ---- konversi ---------------------------------------------------------

    def test_end_to_end_merged_conversion(self):
        self.win.add_paths([*self.images(2), make_png(self.dir / "logo.png")])
        out = self.dir / "hasil.pdf"
        result = self.run_conversion(out)
        self.assertTrue(result.ok)
        self.assertEqual(result.outputs, [out])
        self.assertEqual(out.read_bytes()[:5], b"%PDF-")
        self.assertFalse(self.win._busy)
        self.assertTrue(self.win.btn_convert.isEnabled())
        self.win._show_result.assert_called_once()

    def test_end_to_end_separate_mode(self):
        self.win.add_paths(self.images(3))
        self.win.combo_mode.setCurrentIndex(self.win.combo_mode.findData("separate"))
        out_dir = self.dir / "keluar"
        result = self.run_conversion(out_dir)
        self.assertEqual(len(result.outputs), 3)

    def test_bad_file_does_not_stop_batch(self):
        bad = self.dir / "palsu.jpg"; bad.write_text("bukan gambar")
        self.win.add_paths([self.images(1)[0], bad])
        result = self.run_conversion(self.dir / "h.pdf")
        self.assertEqual(len(result.converted), 1)
        self.assertEqual(len(result.failed), 1)

    def test_cancel_leaves_ui_usable(self):
        self.win.add_paths([make_jpeg(self.dir / f"f{i}.jpg", size=(1500, 1000)) for i in range(15)])
        loop, got = QEventLoop(), []
        self.win.conversion_finished.connect(lambda r: (got.append(r), loop.quit()))
        self.win.start_conversion(self.dir / "c.pdf")
        self.win.on_cancel_clicked()
        if not got:
            QTimer.singleShot(30000, loop.quit); loop.exec()
        self.assertTrue(got)
        self.assertFalse(self.win._busy)
        if got[0].cancelled:
            self.assertFalse((self.dir / "c.pdf").exists())

    # ---- pengaturan -------------------------------------------------------

    def test_setting_widget_dependencies(self):
        self.win.combo_page.setCurrentIndex(self.win.combo_page.findData("original"))
        self.assertFalse(self.win.combo_orientation.isEnabled())
        self.win.combo_page.setCurrentIndex(self.win.combo_page.findData("a4"))
        self.assertTrue(self.win.combo_orientation.isEnabled())
        self.assertFalse(self.win.slider_quality.isEnabled())
        self.win.combo_quality.setCurrentIndex(self.win.combo_quality.findData("compressed"))
        self.assertTrue(self.win.slider_quality.isEnabled())

    def test_settings_persist_across_sessions(self):
        self.win.combo_page.setCurrentIndex(self.win.combo_page.findData("letter"))
        self.win.chk_strip.setChecked(False)
        self.win.close()
        again = MainWindow(self.store)
        self.addCleanup(again.close)
        self.assertEqual(again.read_settings().page_size, "letter")
        self.assertFalse(again.read_settings().strip_metadata)


if __name__ == "__main__":
    unittest.main()
