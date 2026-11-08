import importlib.util
import io
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from app import selftest
from app.selftest import FAIL, PASS, SKIP

ROOT = Path(__file__).resolve().parent.parent
HAS_QT = importlib.util.find_spec("PySide6") is not None


class SelfTestRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = Path(self.tmp.name) / "laporan.txt"

    def test_passes_and_writes_report(self):
        code = selftest.run(self.report, require_qt=False)
        text = self.report.read_text(encoding="utf-8")
        self.assertEqual(code, 0, text)
        self.assertIn("HASIL: LULUS", text)
        for name in ("Konversi JPG + PNG ke PDF", "Penghapusan metadata EXIF/GPS", "Tanpa koneksi jaringan"):
            self.assertIn(f"[{PASS}] {name}", text)

    def test_prints_to_stdout_without_report_path(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(selftest.run(None, require_qt=False), 0)
        self.assertIn("uji mandiri", out.getvalue())

    def test_failing_check_is_reported_and_others_still_run(self):
        def boom(work): raise RuntimeError("sengaja gagal")
        code = selftest.run(self.report, require_qt=False, extra_checks=[("Pemeriksaan rusak", boom)])
        text = self.report.read_text(encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertIn(f"[{FAIL}] Pemeriksaan rusak - RuntimeError: sengaja gagal", text)
        self.assertIn(f"[{PASS}] Konversi JPG + PNG ke PDF", text)
        self.assertIn("HASIL: GAGAL (1 pemeriksaan)", text)

    def test_skip_status_does_not_fail(self):
        def skip(work): raise selftest._SkipCheck("tidak relevan")
        code = selftest.run(self.report, require_qt=False, extra_checks=[("Opsional", skip)])
        self.assertEqual(code, 0)
        self.assertIn(f"[{SKIP}] Opsional - tidak relevan", self.report.read_text(encoding="utf-8"))

    def test_network_attempt_is_detected_and_blocked(self):
        reached = []
        def tries_network(work):
            try:
                socket.create_connection(("192.0.2.1", 80), timeout=1)  # alamat dokumentasi, tidak pernah dipakai
                reached.append(True)
            except OSError:
                pass
            return "mencoba konek"
        code = selftest.run(self.report, require_qt=False, extra_checks=[("Pelanggar", tries_network)])
        text = self.report.read_text(encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertEqual(reached, [], "koneksi harus diblokir, bukan diteruskan")
        self.assertIn(f"[{FAIL}] Tanpa koneksi jaringan - ada upaya koneksi", text)
        self.assertIn("create_connection", text)

    def test_dns_lookup_is_also_detected(self):
        def tries_dns(work):
            try: socket.getaddrinfo("contoh.invalid", 80)
            except OSError: pass
            return "dns"
        self.assertEqual(selftest.run(self.report, require_qt=False, extra_checks=[("DNS", tries_dns)]), 1)

    def test_socket_functions_restored_afterwards(self):
        before = (socket.socket.connect, socket.create_connection, socket.getaddrinfo)
        selftest.run(self.report, require_qt=False)
        self.assertEqual(before, (socket.socket.connect, socket.create_connection, socket.getaddrinfo))

    def test_socket_functions_restored_even_when_check_crashes(self):
        before = socket.create_connection
        def boom(work): raise KeyboardInterrupt if False else RuntimeError("x")
        selftest.run(self.report, require_qt=False, extra_checks=[("x", boom)])
        self.assertIs(socket.create_connection, before)

    def test_selftest_leaves_no_temp_directories(self):
        with mock.patch("tempfile.tempdir", self.tmp.name):
            selftest.run(self.report, require_qt=False)
        leftovers = [p.name for p in Path(self.tmp.name).iterdir() if p.name.startswith("doxify_")]
        self.assertEqual(leftovers, [])

    @unittest.skipIf(HAS_QT, "PySide6 terpasang: perilaku tanpa Qt tidak bisa diuji")
    def test_missing_qt_is_reported_as_failure_not_crash(self):
        code = selftest.run(self.report, require_qt=True)
        self.assertEqual(code, 1)
        self.assertIn("PySide6 tidak bisa dimuat", self.report.read_text(encoding="utf-8"))


class EntryPointTests(unittest.TestCase):
    def test_run_doxify_self_test_no_gui_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            report = Path(d) / "r.txt"
            proc = subprocess.run([sys.executable, str(ROOT / "run_doxify.py"), "--self-test", "--no-gui", str(report)],
                                  cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr + (report.read_text(encoding="utf-8") if report.exists() else ""))
            self.assertIn("HASIL: LULUS", report.read_text(encoding="utf-8"))

    def test_windowed_mode_streams_are_made_safe(self):
        spec = importlib.util.spec_from_file_location("run_doxify", ROOT / "run_doxify.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with mock.patch.object(sys, "stdout", None), mock.patch.object(sys, "stderr", None):
            module._ensure_std_streams()
            self.assertIsNotNone(sys.stdout); self.assertIsNotNone(sys.stderr)
            print("tidak boleh crash")  # bukti praktis
            sys.stdout.close(); sys.stderr.close()


if __name__ == "__main__":
    unittest.main()
