"""NFR-01: bukti bahwa Doxify tidak memakai jaringan sama sekali."""
import contextlib
import io
import os
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import cli
from app.converters import ConversionSettings, ImageConverter
from tests.helpers import make_jpeg, make_png

ROOT = Path(__file__).resolve().parent.parent

BLOCKER = '''
import os, socket
def _deny(*args, **kwargs):
    with open(os.environ["DOXIFY_NET_LOG"], "a") as fh:
        fh.write("jaringan dipakai\\n")
    raise OSError("jaringan diblokir oleh tes")
for _name in ("connect", "connect_ex", "sendto", "sendmsg"):
    setattr(socket.socket, _name, _deny)
for _name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "create_connection"):
    setattr(socket, _name, _deny)
'''


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.images = [
            make_jpeg(self.dir / "a.jpg", with_exif=True, orientation=6),
            make_png(self.dir / "b.png"),
            make_jpeg(self.dir / "c.jpg", size=(300, 120)),
        ]

    def test_conversions_work_with_all_network_calls_blocked_in_process(self):
        calls = []
        def deny(*a, **k):
            calls.append(a); raise OSError("jaringan diblokir oleh tes")
        with mock.patch.multiple(socket.socket, connect=deny, connect_ex=deny, sendto=deny), \
             mock.patch.multiple(socket, getaddrinfo=deny, gethostbyname=deny, create_connection=deny):
            conv = ImageConverter()
            for i, opts in enumerate([{}, {"quality": "compressed"}, {"output_mode": "separate"}, {"strip_metadata": False}]):
                target = self.dir / (f"o{i}" if opts.get("output_mode") == "separate" else f"o{i}.pdf")
                res = conv.convert(self.images, target, ConversionSettings(**opts))
                self.assertTrue(res.ok, opts)
        self.assertEqual(calls, [], "tidak boleh ada panggilan jaringan")

    def test_whole_process_with_network_blocked_from_interpreter_start(self):
        """Proses terpisah: jaringan diblokir sejak Python menyala (sitecustomize),
        sehingga impor library pun ikut teruji, bukan hanya fungsi konversi."""
        site = self.dir / "site"; site.mkdir()
        (site / "sitecustomize.py").write_text(BLOCKER)
        log = self.dir / "net.log"
        env = dict(os.environ, DOXIFY_NET_LOG=str(log),
                   PYTHONPATH=os.pathsep.join([str(site), str(ROOT)]))
        out_pdf = self.dir / "cli.pdf"
        proc = subprocess.run(
            [sys.executable, "-m", "app.cli", *map(str, self.images), "-o", str(out_pdf)],
            env=env, cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(out_pdf.exists())
        self.assertFalse(log.exists(), "ada upaya memakai jaringan: " + (log.read_text() if log.exists() else ""))

    def test_blocker_really_blocks(self):
        """Pastikan alat uji di atas memang bekerja (bukan lulus karena salah pasang)."""
        site = self.dir / "site"; site.mkdir()
        (site / "sitecustomize.py").write_text(BLOCKER)
        log = self.dir / "net.log"
        env = dict(os.environ, DOXIFY_NET_LOG=str(log), PYTHONPATH=str(site))
        code = "import socket\ntry:\n    socket.create_connection(('example.com', 80), timeout=1)\nexcept OSError:\n    pass\n"
        subprocess.run([sys.executable, "-c", code], env=env, timeout=30)
        self.assertTrue(log.exists())

    def test_cli_main_runs_with_network_blocked(self):
        def deny(*a, **k): raise OSError("diblokir")
        with mock.patch.multiple(socket, getaddrinfo=deny, create_connection=deny), \
                contextlib.redirect_stdout(io.StringIO()):
            code = cli.main([*map(str, self.images), "-o", str(self.dir / "m.pdf")])
        self.assertEqual(code, 0)

    def test_source_has_no_urls_or_hostnames(self):
        pattern = re.compile(r"https?://|ftp://|www\.[a-z0-9-]+\.", re.I)
        hits = []
        for py in (ROOT / "app").rglob("*.py"):
            for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{py.relative_to(ROOT)}:{n}: {line.strip()}")
        self.assertEqual(hits, [])

    def test_no_telemetry_or_update_keywords(self):
        banned = re.compile(r"telemetry|analytics|sentry|mixpanel|crashlytics|check_for_update|autoupdate", re.I)
        hits = [p.name for p in (ROOT / "app").rglob("*.py") if banned.search(p.read_text(encoding="utf-8"))]
        self.assertEqual(hits, [])

    def test_dependencies_are_pinned(self):
        lines = [l.strip() for l in (ROOT / "requirements.txt").read_text().splitlines()
                 if l.strip() and not l.startswith("#")]
        loose = [l for l in lines if "==" not in l and not l.lower().startswith("pyside6")]
        self.assertEqual(loose, [], "dependensi non-GUI harus dikunci ke versi pasti")


if __name__ == "__main__":
    unittest.main()
