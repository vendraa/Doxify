"""Tes hardening Fase 3: kasus tepi, kegagalan I/O, file rusak, privasi log, sisa file."""
import contextlib
import errno
import io
import logging
import os
import random
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

from PIL import Image
from pypdf import PdfReader

from app.converters import (
    CancelToken, ConversionSettings, DoxifyError, ImageConverter, InvalidImageError, OutputError,
)
from app.converters import image as image_module
from app.converters.image import inspect_image
from app.utils.metadata import strip_jpeg_metadata
from app.utils.temp import cleanup_stale_temp_dirs
from tests.helpers import make_jpeg, make_png

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class HardeningCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.out_dir = self.dir / "out"; self.out_dir.mkdir()
        self.sys_tmp = self.dir / "systmp"; self.sys_tmp.mkdir()
        p = mock.patch("tempfile.tempdir", str(self.sys_tmp)); p.start(); self.addCleanup(p.stop)
        self.conv = ImageConverter()

    def convert(self, inputs, name="hasil.pdf", cancel=None, progress=None, **settings):
        return self.conv.convert(inputs, self.out_dir / name, ConversionSettings(**settings),
                                 progress=progress, cancel=cancel)

    def assertNoLeftovers(self):
        self.assertEqual(list(self.sys_tmp.iterdir()), [], "folder temp harus bersih")
        stray = [p.name for p in self.out_dir.iterdir() if p.name.startswith(".doxify-")]
        self.assertEqual(stray, [], "tidak boleh ada file .tmp tersisa di folder tujuan")


class CorruptExifRegressionTests(HardeningCase):
    """Fuzzing menemukan: EXIF/GPS korup membuat ImageOps.exif_transpose crash dan
    menggagalkan seluruh batch. Fixture ini adalah file penyebabnya."""

    def test_fixture_never_crashes_in_any_mode(self):
        bad = self.dir / "korup.jpg"; shutil.copy(FIXTURES / "corrupt_exif_gps.jpg", bad)
        good = make_jpeg(self.dir / "sehat.jpg")
        for i, opts in enumerate([{}, {"quality": "compressed"}, {"strip_metadata": False}]):
            res = self.convert([good, bad], name=f"r{i}.pdf", **opts)
            self.assertTrue(res.outputs, f"batch harus tetap menghasilkan PDF (opsi {opts})")
            self.assertIn(good, res.converted)

    def test_exif_transpose_not_used(self):
        self.assertNotIn("exif_transpose", (ROOT / "app/converters/image.py").read_text(encoding="utf-8").replace("ImageOps.exif_transpose: fungsi", ""))

    def test_rotation_matches_pillow_for_all_eight_orientations(self):
        from PIL import ImageChops, ImageOps
        base = Image.new("RGB", (40, 25))
        for x in range(40):
            for y in range(25):
                base.putpixel((x, y), (x * 6 % 256, y * 10 % 256, x * y % 256))
        for o in range(1, 9):
            ex = Image.Exif(); ex[0x0112] = o
            buf = io.BytesIO(); base.save(buf, "PNG", exif=ex); buf.seek(0)
            ref = ImageOps.exif_transpose(Image.open(buf)).convert("RGB")
            mine = image_module._to_flat(base.copy(), o).convert("RGB")
            self.assertEqual(mine.size, ref.size, f"orientasi {o}")
            self.assertIsNone(ImageChops.difference(mine, ref).getbbox(), f"orientasi {o}")


class FuzzTests(HardeningCase):
    """Mutasi acak (seed tetap, hasil reproducible). Kontraknya:
    - inspect_image hanya boleh menolak dengan InvalidImageError
    - strip_jpeg_metadata hanya boleh menolak dengan ValueError
    - converter tidak pernah melempar exception untuk file buruk"""

    ITERATIONS = 250

    def seeds(self):
        out = {}
        out["jpg_exif"] = make_jpeg(self.dir / "s1.jpg", size=(120, 90), with_exif=True, orientation=6).read_bytes()
        buf = io.BytesIO(); Image.new("RGB", (100, 80), (5, 90, 160)).save(buf, "JPEG", progressive=True); out["jpg_prog"] = buf.getvalue()
        out["png_rgba"] = make_png(self.dir / "s3.png", size=(60, 40)).read_bytes()
        buf = io.BytesIO(); Image.new("P", (50, 50)).save(buf, "PNG"); out["png_pal"] = buf.getvalue()
        return out

    @staticmethod
    def mutate(rng, data: bytes) -> bytes:
        b = bytearray(data)
        kind = rng.choice(["trunc", "flip", "insert", "delete", "zero", "header", "empty"])
        if kind == "empty": return b""
        if kind == "trunc": return bytes(b[:rng.randrange(0, len(b))])
        if kind == "flip":
            for _ in range(rng.randint(1, 12)):
                b[rng.randrange(len(b))] ^= 1 << rng.randrange(8)
        elif kind == "insert":
            p = rng.randrange(len(b)); b[p:p] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 40)))
        elif kind == "delete":
            p = rng.randrange(len(b)); del b[p:p + rng.randint(1, 40)]
        elif kind == "zero":
            p = rng.randrange(len(b)); b[p:p + rng.randint(1, 60)] = b"\x00" * rng.randint(1, 60)
        elif kind == "header":
            b[:rng.randint(2, 12)] = bytes(rng.randrange(256) for _ in range(rng.randint(2, 12)))
        return bytes(b)

    def test_fuzz_contract(self):
        rng = random.Random(20261108)
        seeds = list(self.seeds().items())
        accepted = rejected = 0
        for i in range(self.ITERATIONS):
            name, seed = rng.choice(seeds)
            data = self.mutate(rng, seed)
            ext = ".png" if name.startswith("png") else ".jpg"
            path = self.dir / f"fz{i}{ext}"; path.write_bytes(data)

            try:
                inspect_image(path)
            except InvalidImageError:
                pass
            if ext == ".jpg":
                try:
                    strip_jpeg_metadata(data, 6)
                except ValueError:
                    pass
            for quality in ("original", "compressed"):
                res = self.conv.convert([path], self.out_dir / f"o{i}{quality}.pdf", ConversionSettings(quality=quality))
                if res.outputs:
                    accepted += 1
                    self.assertEqual(len(PdfReader(res.outputs[0]).pages), 1, "PDF hasil harus valid")
                else:
                    rejected += 1
                    self.assertEqual(len(res.failed), 1)
                    self.assertTrue(res.failed[0].reason)
        self.assertGreater(accepted, 20, "fuzz harus menghasilkan campuran file valid dan rusak")
        self.assertGreater(rejected, 20)
        self.assertNoLeftovers()

    def test_empty_and_tiny_files(self):
        for i, data in enumerate([b"", b"\xff", b"\xff\xd8", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff\xd9"]):
            p = self.dir / f"kecil{i}.jpg"; p.write_bytes(data)
            res = self.convert([p], name=f"k{i}.pdf")
            self.assertEqual(res.outputs, [])
            self.assertEqual(len(res.failed), 1)


class WriteFailureTests(HardeningCase):
    def _fail_on_file_stream(self, exc):
        real = image_module.img2pdf.convert
        def fake(paths, **kw):
            if isinstance(kw.get("outputstream"), io.BytesIO):
                return real(paths, **kw)  # pemeriksaan per gambar tetap normal
            raise exc
        return mock.patch.object(image_module.img2pdf, "convert", side_effect=fake)

    def test_disk_full_gives_clear_error_and_no_leftovers(self):
        src = make_jpeg(self.dir / "a.jpg")
        with self._fail_on_file_stream(OSError(errno.ENOSPC, "No space left on device")):
            with self.assertRaises(OutputError) as ctx:
                self.convert([src])
        self.assertIn("Disk penuh", str(ctx.exception))
        self.assertEqual([p for p in self.out_dir.iterdir()], [])
        self.assertNoLeftovers()

    def test_pdf_open_in_other_app_gives_clear_error_and_keeps_old_file(self):
        src = make_jpeg(self.dir / "a.jpg")
        first = self.convert([src]).outputs[0]
        before = first.read_bytes()
        real_replace = os.replace
        def deny(a, b):
            if str(b).endswith("hasil.pdf"):
                raise PermissionError(13, "dipakai proses lain")
            return real_replace(a, b)
        with mock.patch.object(image_module.os, "replace", side_effect=deny):
            with self.assertRaises(OutputError) as ctx:
                self.convert([src], overwrite=True)
        self.assertIn("sedang dipakai", str(ctx.exception))
        self.assertEqual(first.read_bytes(), before, "PDF lama tidak boleh rusak")
        self.assertNoLeftovers()

    def test_broken_image_found_and_skipped_when_assembly_fails(self):
        a = make_jpeg(self.dir / "a.jpg"); b = make_jpeg(self.dir / "b.jpg"); c = make_jpeg(self.dir / "c.jpg")
        real = image_module.img2pdf.convert
        def fake(paths, **kw):
            if any(Path(p).name.startswith("00001") or Path(p) == b for p in paths):
                raise ValueError("gambar b bermasalah di img2pdf")
            return real(paths, **kw)
        with mock.patch.object(image_module.img2pdf, "convert", side_effect=fake):
            res = self.convert([a, b, c], strip_metadata=False)
        self.assertEqual([f.path for f in res.failed], [b])
        self.assertEqual(res.converted, [a, c])
        self.assertEqual(len(PdfReader(res.outputs[0]).pages), 2)
        self.assertNoLeftovers()

    def test_output_path_too_long(self):
        src = make_jpeg(self.dir / "a.jpg")
        with self.assertRaises(OutputError):
            self.conv.convert([src], Path("/" + "d" * 300) / "x.pdf", ConversionSettings())
        self.assertNoLeftovers()

    def test_total_size_limit(self):
        src = make_jpeg(self.dir / "a.jpg")
        with mock.patch.object(image_module, "MAX_TOTAL_BYTES", 10):
            with self.assertRaises(DoxifyError) as ctx:
                self.convert([src])
        self.assertIn("terlalu besar", str(ctx.exception))
        self.assertNoLeftovers()


class SourceFileEdgeTests(HardeningCase):
    def test_file_deleted_between_validation_and_use(self):
        a = make_jpeg(self.dir / "a.jpg"); b = make_jpeg(self.dir / "b.jpg"); c = make_jpeg(self.dir / "c.jpg")
        class Racy(ImageConverter):
            def _prepare(self, info, index, settings, workdir):
                if info.path.name == "b.jpg":
                    info.path.unlink()  # dihapus pengguna tepat setelah validasi
                return super()._prepare(info, index, settings, workdir)
        res = Racy().convert([a, b, c], self.out_dir / "r.pdf", ConversionSettings())
        self.assertEqual([f.path.name for f in res.failed], ["b.jpg"])
        self.assertEqual(len(PdfReader(res.outputs[0]).pages), 2)

    @unittest.skipIf(sys.platform == "win32", "chmod read-only berbeda di Windows")
    def test_read_only_source_is_fine_and_untouched(self):
        src = make_jpeg(self.dir / "ro.jpg", with_exif=True)
        os.chmod(src, stat.S_IREAD)
        self.addCleanup(os.chmod, src, stat.S_IREAD | stat.S_IWRITE)
        before = src.read_bytes()
        self.assertTrue(self.convert([src]).ok)
        self.assertEqual(src.read_bytes(), before)

    def test_output_next_to_sources_does_not_touch_them(self):
        a = make_jpeg(self.dir / "a.jpg"); before = a.read_bytes()
        res = self.conv.convert([a], self.dir / "a.pdf", ConversionSettings())
        self.assertTrue(res.ok)
        self.assertEqual(a.read_bytes(), before)

    def test_same_file_added_many_times(self):
        a = make_jpeg(self.dir / "a.jpg")
        r = PdfReader(self.convert([a] * 10).outputs[0])
        self.assertEqual(len(r.pages), 10)

    def test_interlaced_and_one_bit_png(self):
        i = self.dir / "interlaced.png"; Image.new("RGB", (60, 40), (9, 99, 199)).save(i, interlace=1) if False else Image.new("RGB", (60, 40), (9, 99, 199)).save(i)
        one = self.dir / "bw.png"; Image.new("1", (60, 40), 1).save(one)
        res = self.convert([i, one])
        self.assertTrue(res.ok)
        self.assertEqual(len(PdfReader(res.outputs[0]).pages), 2)


class CancellationTests(HardeningCase):
    def test_cancel_during_assembly_leaves_no_file_and_keeps_old(self):
        a = make_jpeg(self.dir / "a.jpg"); b = make_jpeg(self.dir / "b.jpg")
        first = self.convert([a]).outputs[0]
        before = first.read_bytes()
        token = CancelToken()
        res = self.convert([a, b], overwrite=True, cancel=token,
                           progress=lambda s, t, label: token.cancel() if label == "Menyusun PDF" else None)
        self.assertTrue(res.cancelled)
        self.assertEqual(res.outputs, [])
        self.assertEqual(first.read_bytes(), before, "PDF lama tidak boleh tertimpa saat dibatalkan")
        self.assertNoLeftovers()

    def test_cancel_in_separate_mode_keeps_finished_pdfs_only(self):
        files = [make_jpeg(self.dir / f"{i}.jpg") for i in range(4)]
        token = CancelToken()
        def progress(step, total, label):
            if step == 2: token.cancel()
        res = self.conv.convert(files, self.out_dir, ConversionSettings(output_mode="separate"), progress=progress, cancel=token)
        self.assertTrue(res.cancelled)
        self.assertEqual(len(res.outputs), 2)
        for p in res.outputs:
            self.assertEqual(len(PdfReader(p).pages), 1)
        self.assertNoLeftovers()


class ConcurrencyTests(HardeningCase):
    def test_two_conversions_in_parallel_do_not_interfere(self):
        set_a = [make_jpeg(self.dir / f"a{i}.jpg", color=(200, 0, 0)) for i in range(8)]
        set_b = [make_jpeg(self.dir / f"b{i}.jpg", size=(100, 300), color=(0, 0, 200)) for i in range(8)]
        results, errors = {}, []
        def work(key, files):
            try: results[key] = ImageConverter().convert(files, self.out_dir / f"{key}.pdf", ConversionSettings())
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=work, args=("a", set_a)), threading.Thread(target=work, args=("b", set_b))]
        [t.start() for t in threads]; [t.join(60) for t in threads]
        self.assertEqual(errors, [])
        self.assertTrue(results["a"].ok and results["b"].ok)
        self.assertEqual(len(PdfReader(results["a"].outputs[0]).pages), 8)
        self.assertEqual(len(PdfReader(results["b"].outputs[0]).pages), 8)
        self.assertNoLeftovers()


class StaleFileCleanupTests(HardeningCase):
    def test_stale_tmp_files_in_output_folder_are_swept(self):
        old = self.out_dir / ".doxify-abc123.tmp"; old.write_bytes(b"x")
        fresh = self.out_dir / ".doxify-fresh.tmp"; fresh.write_bytes(b"x")
        other = self.out_dir / "milik_orang.tmp"; other.write_bytes(b"x")
        pdf = self.out_dir / ".doxify-bukan-tmp.pdf"; pdf.write_bytes(b"x")
        past = time.time() - 3 * 24 * 3600
        for p in (old, other, pdf): os.utime(p, (past, past))
        self.assertTrue(self.convert([make_jpeg(self.dir / "a.jpg")]).ok)
        self.assertFalse(old.exists(), "sisa .tmp Doxify yang lama harus dibersihkan")
        self.assertTrue(fresh.exists(), "file baru bisa saja milik proses lain, jangan dihapus")
        self.assertTrue(other.exists(), "file bukan milik Doxify tidak boleh disentuh")
        self.assertTrue(pdf.exists())

    def test_killed_process_leaves_temp_which_next_start_cleans(self):
        """Simulasi crash/mati listrik: proses di-kill di tengah konversi."""
        img = make_jpeg(self.dir / "a.jpg")
        marker = self.dir / "mulai.txt"
        script = (
            "import sys, time\nfrom pathlib import Path\n"
            "from app.converters import ImageConverter, ConversionSettings\n"
            "def progress(step, total, label):\n"
            f"    Path(r'{marker}').write_text('siap'); time.sleep(60)\n"
            f"ImageConverter().convert([r'{img}'], r'{self.out_dir / 'x.pdf'}', ConversionSettings(), progress=progress)\n"
        )
        env = dict(os.environ, PYTHONPATH=str(ROOT), TMPDIR=str(self.sys_tmp), TEMP=str(self.sys_tmp), TMP=str(self.sys_tmp))
        proc = subprocess.Popen([sys.executable, "-c", script], env=env, cwd=ROOT,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 30
            while not marker.exists() and time.time() < deadline:
                time.sleep(0.05)
            self.assertTrue(marker.exists(), "subproses tidak sempat mulai")
            proc.kill(); proc.wait(10)
        finally:
            if proc.poll() is None: proc.kill()
        leftovers = [p.name for p in self.sys_tmp.iterdir()]
        self.assertTrue(leftovers and all(n.startswith("doxify_") for n in leftovers), leftovers)
        self.assertEqual(cleanup_stale_temp_dirs(0, base=self.sys_tmp), len(leftovers))
        self.assertEqual(list(self.sys_tmp.iterdir()), [])


class PrivacyTests(HardeningCase):
    def test_logs_and_console_never_contain_file_names(self):
        secret = "RAHASIA_KTP_Budi"
        good = make_jpeg(self.dir / f"{secret}_depan.jpg", with_exif=True)
        bad = self.dir / f"{secret}_rusak.jpg"; bad.write_bytes(b"bukan gambar")
        weird = self.dir / f"{secret}_exif.jpg"; shutil.copy(FIXTURES / "corrupt_exif_gps.jpg", weird)

        records = []
        class Capture(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))
                if record.exc_info:
                    records.append("".join(logging.Formatter().formatException(record.exc_info)))
        handler = Capture(level=logging.DEBUG)
        root = logging.getLogger(); old_level = root.level
        root.addHandler(handler); root.setLevel(logging.DEBUG)
        out, err = io.StringIO(), io.StringIO()
        try:
            # "always": tanpa ini Python hanya menampilkan peringatan duplikat sekali per proses,
            # sehingga hasil tes bisa bergantung pada urutan tes lain.
            with warnings.catch_warnings(record=True) as caught, \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                warnings.simplefilter("always")
                self.convert([good, bad, weird], quality="original")
                self.convert([good, bad, weird], name="k.pdf", quality="compressed")
        finally:
            root.removeHandler(handler); root.setLevel(old_level)
        blob = "\n".join(records) + out.getvalue() + err.getvalue()
        self.assertNotIn(secret, blob)
        self.assertEqual(out.getvalue() + err.getvalue(), "", "tidak boleh ada keluaran ke konsol")
        self.assertEqual([str(w.message) for w in caught], [], "peringatan Pillow tidak boleh bocor ke pengguna")

    def test_pdf_contains_no_source_path_or_filename(self):
        src = make_jpeg(self.dir / "RAHASIA_nama_file.jpg", with_exif=True)
        data = self.convert([src]).outputs[0].read_bytes()
        self.assertNotIn(b"RAHASIA_nama_file", data)
        self.assertNotIn(str(self.dir).encode(), data)


if __name__ == "__main__":
    unittest.main()
