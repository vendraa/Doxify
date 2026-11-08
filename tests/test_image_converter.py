import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
from pypdf import PdfReader

from app.converters import (
    CancelToken, ConversionSettings, DoxifyError, ImageConverter, OutputError,
)
from app.converters import image as image_module
from tests.helpers import (
    embedded_image_bytes, embedded_pil, make_jpeg, make_png, page_dims,
)

A4 = (595.28, 841.89)


class ConverterTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out_dir = self.dir / "out"
        self.out_dir.mkdir()
        # arahkan folder temp aplikasi ke folder uji agar kebersihan bisa diperiksa
        self.sys_tmp = self.dir / "systmp"
        self.sys_tmp.mkdir()
        patcher = mock.patch("tempfile.tempdir", str(self.sys_tmp))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.conv = ImageConverter()

    def convert(self, inputs, name="hasil.pdf", **settings):
        return self.conv.convert(inputs, self.out_dir / name, ConversionSettings(**settings))

    def assertTempClean(self):
        self.assertEqual(list(self.sys_tmp.iterdir()), [], "folder temp harus bersih")


class BasicConversionTests(ConverterTestCase):
    def test_jpg_to_single_page_pdf(self):
        jpg = make_jpeg(self.dir / "a.jpg")
        res = self.convert([jpg])
        self.assertTrue(res.ok)
        pdf = res.outputs[0]
        self.assertEqual(pdf.read_bytes()[:5], b"%PDF-")
        self.assertEqual(len(PdfReader(pdf).pages), 1)
        self.assertTempClean()

    def test_png_and_jpeg_merged_keep_order(self):
        # ukuran asli dipakai supaya urutan bisa dibaca dari rasio halaman
        a = make_jpeg(self.dir / "a.jpg", size=(400, 100))   # sangat lebar
        b = make_png(self.dir / "b.png", size=(100, 400), mode="RGB", color=(1, 2, 3, 255))  # sangat tinggi
        c = make_jpeg(self.dir / "c.jpeg", size=(300, 300))
        res = self.convert([a, b, c], page_size="original", margin="none")
        r = PdfReader(res.outputs[0])
        self.assertEqual(len(r.pages), 3)
        ratios = [page_dims(r, i)[0] / page_dims(r, i)[1] for i in range(3)]
        self.assertGreater(ratios[0], 2)
        self.assertLess(ratios[1], 0.5)
        self.assertAlmostEqual(ratios[2], 1.0, places=2)
        self.assertEqual(res.converted, [a, b, c])

    def test_uppercase_extension_accepted(self):
        src = make_jpeg(self.dir / "FOTO.JPG")
        self.assertTrue(self.convert([src]).ok)

    def test_unicode_and_spaces_in_names(self):
        src = make_jpeg(self.dir / "Scan KTP — Budi é.jpg")
        res = self.convert([src], name="Hasil Scan: KTP?.pdf")
        self.assertTrue(res.ok)
        self.assertEqual(res.outputs[0].name, "Hasil Scan_ KTP_.pdf")


class PageLayoutTests(ConverterTestCase):
    def test_a4_portrait_and_landscape_forced(self):
        img = make_jpeg(self.dir / "a.jpg", size=(400, 200))
        w, h = page_dims(PdfReader(self.convert([img], orientation="portrait").outputs[0]))
        self.assertAlmostEqual(w, A4[0], delta=1); self.assertAlmostEqual(h, A4[1], delta=1)
        w, h = page_dims(PdfReader(self.convert([img], name="b.pdf", orientation="landscape").outputs[0]))
        self.assertAlmostEqual(w, A4[1], delta=1); self.assertAlmostEqual(h, A4[0], delta=1)

    def test_auto_orientation_follows_image(self):
        wide = make_jpeg(self.dir / "w.jpg", size=(400, 200))
        tall = make_jpeg(self.dir / "t.jpg", size=(200, 400))
        r = PdfReader(self.convert([wide, tall], orientation="auto").outputs[0])
        self.assertGreater(page_dims(r, 0)[0], page_dims(r, 0)[1])
        self.assertLess(page_dims(r, 1)[0], page_dims(r, 1)[1])

    def test_letter_size(self):
        img = make_jpeg(self.dir / "a.jpg", size=(200, 400))
        w, h = page_dims(PdfReader(self.convert([img], page_size="letter").outputs[0]))
        self.assertAlmostEqual(w, 612, delta=1); self.assertAlmostEqual(h, 792, delta=1)

    def test_original_size_page_matches_image(self):
        img = Image.new("RGB", (192, 96), (9, 9, 9)); p = self.dir / "a.jpg"; img.save(p, dpi=(96, 96))
        w, h = page_dims(PdfReader(self.convert([p], page_size="original", margin="none").outputs[0]))
        self.assertAlmostEqual(w, 144, delta=1); self.assertAlmostEqual(h, 72, delta=1)  # px*72/96

    def test_margin_makes_image_smaller_than_page(self):
        img = make_jpeg(self.dir / "a.jpg", size=(200, 400))
        none = PdfReader(self.convert([img], name="n.pdf", margin="none", orientation="portrait").outputs[0])
        med = PdfReader(self.convert([img], name="m.pdf", margin="medium", orientation="portrait").outputs[0])
        def drawn_width(r):
            # lebar gambar = skala 'cm' pada content stream
            data = r.pages[0].get_contents().get_data().decode("latin1")
            return float(data.split("cm")[0].split()[-6])
        self.assertLess(drawn_width(med), drawn_width(none))

    def test_original_size_with_margin_works(self):
        img = make_jpeg(self.dir / "a.jpg", size=(200, 100))
        res = self.convert([img], page_size="original", margin="medium")
        self.assertTrue(res.ok)


class ExifAndAlphaTests(ConverterTestCase):
    def test_exif_rotation_applied(self):
        # 200x100 dengan Orientation=6: tampil sebagai potret
        img = make_jpeg(self.dir / "ponsel.jpg", size=(200, 100), orientation=6)
        r = PdfReader(self.convert([img], page_size="original", margin="none").outputs[0])
        w, h = page_dims(r)
        self.assertLess(w, h)

    def test_exif_rotation_applied_when_keeping_metadata(self):
        img = make_jpeg(self.dir / "ponsel.jpg", size=(200, 100), orientation=8)
        r = PdfReader(self.convert([img], page_size="original", margin="none", strip_metadata=False).outputs[0])
        w, h = page_dims(r)
        self.assertLess(w, h)

    def test_mirrored_orientation_handled(self):
        img = make_jpeg(self.dir / "cermin.jpg", size=(200, 100), orientation=5)
        res = self.convert([img], page_size="original", margin="none")
        self.assertTrue(res.ok)
        w, h = page_dims(PdfReader(res.outputs[0]))
        self.assertLess(w, h)

    def test_invalid_orientation_zero_ignored(self):
        img = make_jpeg(self.dir / "nol.jpg", size=(200, 100), orientation=0)
        self.assertTrue(self.convert([img]).ok)

    def test_transparent_png_gets_white_background(self):
        png = make_png(self.dir / "t.png", size=(60, 60), color=(0, 0, 0, 0))  # transparan penuh
        r = PdfReader(self.convert([png]).outputs[0])
        pixel = embedded_pil(r).convert("RGB").getpixel((5, 5))
        self.assertEqual(pixel, (255, 255, 255))

    def test_semi_transparent_png_blends_on_white(self):
        png = make_png(self.dir / "s.png", size=(40, 40), color=(255, 0, 0, 128))
        px = embedded_pil(PdfReader(self.convert([png]).outputs[0])).convert("RGB").getpixel((5, 5))
        self.assertEqual(px[0], 255); self.assertGreater(px[1], 100)  # merah pucat, bukan hitam

    def test_palette_png_with_transparency(self):
        img = Image.new("P", (30, 30)); img.putpalette([255, 0, 0] * 256)
        p = self.dir / "p.png"; img.save(p, transparency=0)
        px = embedded_pil(PdfReader(self.convert([p]).outputs[0])).convert("RGB").getpixel((3, 3))
        self.assertEqual(px, (255, 255, 255))

    def test_grayscale_16bit_png(self):
        img = Image.new("I;16", (30, 30), 40000); p = self.dir / "g16.png"; img.save(p)
        self.assertTrue(self.convert([p]).ok)

    def test_cmyk_jpeg(self):
        img = make_jpeg(self.dir / "cmyk.jpg", mode="CMYK")
        self.assertTrue(self.convert([img]).ok)


class QualityAndPrivacyTests(ConverterTestCase):
    def test_original_jpeg_not_recompressed_when_metadata_kept(self):
        src = make_jpeg(self.dir / "a.jpg", size=(333, 222), quality=77)
        r = PdfReader(self.convert([src], strip_metadata=False).outputs[0])
        self.assertEqual(embedded_image_bytes(r), src.read_bytes())

    def test_original_jpeg_pixels_identical_after_strip(self):
        src = make_jpeg(self.dir / "a.jpg", size=(333, 222), with_exif=True)
        r = PdfReader(self.convert([src]).outputs[0])
        data = embedded_image_bytes(r)
        a = Image.open(src).convert("RGB").tobytes()
        b = Image.open(io.BytesIO(data)).convert("RGB").tobytes()
        self.assertEqual(a, b)

    def test_gps_and_camera_not_in_pdf(self):
        src = make_jpeg(self.dir / "a.jpg", with_exif=True)
        pdf_bytes = self.convert([src]).outputs[0].read_bytes()
        self.assertNotIn(b"TestCam", pdf_bytes)
        self.assertNotIn(b"RahasiaSoftware", pdf_bytes)

    def test_keep_metadata_option_keeps_it(self):
        src = make_jpeg(self.dir / "a.jpg", with_exif=True)
        pdf_bytes = self.convert([src], strip_metadata=False).outputs[0].read_bytes()
        self.assertIn(b"TestCam", pdf_bytes)

    def test_png_text_chunks_not_in_pdf(self):
        from PIL.PngImagePlugin import PngInfo
        info = PngInfo(); info.add_text("Author", "RahasiaPenulis")
        p = self.dir / "a.png"; Image.new("RGB", (50, 50), (1, 1, 1)).save(p, pnginfo=info)
        self.assertNotIn(b"RahasiaPenulis", self.convert([p]).outputs[0].read_bytes())

    def test_compressed_mode_is_smaller(self):
        noisy = Image.effect_noise((1800, 1200), 60).convert("RGB"); p = self.dir / "n.jpg"; noisy.save(p, quality=98)
        big = self.convert([p], name="big.pdf").outputs[0].stat().st_size
        small = self.convert([p], name="small.pdf", quality="compressed", jpeg_quality=40, max_long_edge=900).outputs[0].stat().st_size
        self.assertLess(small, big / 2)

    def test_pdf_has_no_author_or_title(self):
        src = make_jpeg(self.dir / "a.jpg")
        meta = PdfReader(self.convert([src]).outputs[0]).metadata
        self.assertFalse(meta.get("/Author")); self.assertFalse(meta.get("/Title"))


class BadInputTests(ConverterTestCase):
    def test_corrupt_file_skipped_others_converted(self):
        good1 = make_jpeg(self.dir / "ok1.jpg")
        bad = self.dir / "palsu.jpg"; bad.write_text("ini bukan gambar")
        good2 = make_png(self.dir / "ok2.png")
        res = self.convert([good1, bad, good2])
        self.assertEqual(len(PdfReader(res.outputs[0]).pages), 2)
        self.assertEqual([f.path for f in res.failed], [bad])
        self.assertFalse(res.ok)
        self.assertTempClean()

    def test_truncated_jpeg_rejected(self):
        src = make_jpeg(self.dir / "ok.jpg", size=(400, 300))
        cut = self.dir / "potong.jpg"; cut.write_bytes(src.read_bytes()[:300])
        res = self.convert([src, cut])
        self.assertEqual(len(res.failed), 1)

    def test_unsupported_extension_rejected(self):
        gif = self.dir / "a.gif"; Image.new("RGB", (10, 10)).save(gif)
        res = self.convert([make_jpeg(self.dir / "ok.jpg"), gif])
        self.assertIn("tidak didukung", res.failed[0].reason)

    def test_png_content_with_jpg_extension_is_accepted_by_real_format(self):
        p = make_png(self.dir / "salah_nama.jpg", mode="RGB", color=(1, 2, 3, 255))
        self.assertTrue(self.convert([p]).ok)

    def test_missing_file_reported(self):
        res = self.convert([make_jpeg(self.dir / "ok.jpg"), self.dir / "hilang.png"])
        self.assertIn("tidak ditemukan", res.failed[0].reason)

    def test_all_files_invalid_creates_no_pdf(self):
        bad = self.dir / "x.jpg"; bad.write_text("x")
        res = self.convert([bad])
        self.assertEqual(res.outputs, [])
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_oversized_image_rejected(self):
        src = make_jpeg(self.dir / "a.jpg", size=(100, 100))
        with mock.patch.object(image_module, "MAX_PIXELS", 5000):
            res = self.convert([src])
        self.assertIn("terlalu besar", res.failed[0].reason)

    def test_empty_input_raises(self):
        with self.assertRaises(DoxifyError):
            self.convert([])


class OutputTests(ConverterTestCase):
    def test_existing_file_not_overwritten(self):
        src = make_jpeg(self.dir / "a.jpg")
        first = self.convert([src]).outputs[0]
        before = first.read_bytes()
        second = self.convert([src]).outputs[0]
        self.assertNotEqual(first, second)
        self.assertEqual(second.name, "hasil (1).pdf")
        self.assertEqual(first.read_bytes(), before)

    def test_overwrite_option_replaces(self):
        a = make_jpeg(self.dir / "a.jpg"); b = make_jpeg(self.dir / "b.jpg")
        self.convert([a])
        res = self.convert([a, b], overwrite=True)
        self.assertEqual(res.outputs[0].name, "hasil.pdf")
        self.assertEqual(len(PdfReader(res.outputs[0]).pages), 2)

    def test_source_images_untouched(self):
        src = make_jpeg(self.dir / "a.jpg", with_exif=True)
        before = src.read_bytes()
        self.convert([src])
        self.assertEqual(src.read_bytes(), before)
        self.assertTrue(src.exists())

    def test_separate_mode_one_pdf_per_image(self):
        files = [make_jpeg(self.dir / "satu.jpg"), make_png(self.dir / "dua.png"), make_jpeg(self.dir / "tiga.jpg")]
        res = self.conv.convert(files, self.out_dir / "folder_baru", ConversionSettings(output_mode="separate"))
        names = sorted(p.name for p in res.outputs)
        self.assertEqual(names, ["dua.pdf", "satu.pdf", "tiga.pdf"])
        for p in res.outputs:
            self.assertEqual(len(PdfReader(p).pages), 1)

    def test_separate_mode_same_stem_does_not_collide(self):
        (self.dir / "x").mkdir(); (self.dir / "y").mkdir()
        files = [make_jpeg(self.dir / "x" / "foto.jpg"), make_jpeg(self.dir / "y" / "foto.jpg")]
        res = self.conv.convert(files, self.out_dir, ConversionSettings(output_mode="separate"))
        self.assertEqual(sorted(p.name for p in res.outputs), ["foto (1).pdf", "foto.pdf"])

    def test_unwritable_destination_gives_clear_error(self):
        src = make_jpeg(self.dir / "a.jpg")
        blocker = self.dir / "adalah_file"; blocker.write_text("x")
        with self.assertRaises(OutputError):
            self.conv.convert([src], blocker / "hasil.pdf", ConversionSettings())
        self.assertTempClean()

    def test_no_partial_tmp_files_left_in_output(self):
        src = make_jpeg(self.dir / "a.jpg")
        self.convert([src])
        self.assertEqual([p.name for p in self.out_dir.iterdir()], ["hasil.pdf"])


class ProgressAndCancelTests(ConverterTestCase):
    def test_progress_reports_each_file_then_done(self):
        files = [make_jpeg(self.dir / f"{i}.jpg") for i in range(3)]
        calls = []
        self.conv.convert(files, self.out_dir / "p.pdf", ConversionSettings(), progress=lambda s, t, l: calls.append((s, t, l)))
        self.assertEqual([c[0] for c in calls], [0, 1, 2, 3, 4])
        self.assertTrue(all(c[1] == 4 for c in calls))
        self.assertEqual(calls[-1][2], "Selesai")

    def test_cancel_before_start(self):
        src = make_jpeg(self.dir / "a.jpg")
        token = CancelToken(); token.cancel()
        res = self.conv.convert([src], self.out_dir / "c.pdf", ConversionSettings(), cancel=token)
        self.assertTrue(res.cancelled)
        self.assertEqual(list(self.out_dir.iterdir()), [])
        self.assertTempClean()

    def test_cancel_midway_leaves_nothing(self):
        files = [make_jpeg(self.dir / f"{i}.jpg") for i in range(5)]
        token = CancelToken()
        def progress(step, total, label):
            if step == 2:
                token.cancel()
        res = self.conv.convert(files, self.out_dir / "c.pdf", ConversionSettings(), progress=progress, cancel=token)
        self.assertTrue(res.cancelled)
        self.assertEqual(list(self.out_dir.iterdir()), [])
        self.assertTempClean()

    def test_runs_in_worker_thread(self):
        src = make_jpeg(self.dir / "a.jpg"); holder = {}
        t = threading.Thread(target=lambda: holder.setdefault("r", self.conv.convert([src], self.out_dir / "t.pdf")))
        t.start(); t.join(30)
        self.assertTrue(holder["r"].ok)


class StressTests(ConverterTestCase):
    def test_batch_of_60_images(self):
        files = [make_jpeg(self.dir / f"{i:03d}.jpg", size=(800, 600), color=(i * 4 % 255, 50, 90)) for i in range(60)]
        res = self.convert(files, name="batch.pdf")
        self.assertTrue(res.ok)
        self.assertEqual(len(PdfReader(res.outputs[0]).pages), 60)
        self.assertTempClean()

    def test_large_image(self):
        big = self.dir / "besar.jpg"
        Image.effect_noise((5000, 4000), 80).convert("RGB").save(big, quality=92)
        res = self.convert([big])
        self.assertTrue(res.ok)

    def test_extreme_aspect_ratio(self):
        long_shot = make_png(self.dir / "panjang.png", size=(300, 6000), mode="RGB", color=(30, 60, 90, 255))
        self.assertTrue(self.convert([long_shot]).ok)

    def test_duplicate_files_allowed(self):
        a = make_jpeg(self.dir / "a.jpg")
        r = PdfReader(self.convert([a, a, a]).outputs[0])
        self.assertEqual(len(r.pages), 3)


class OfflineGuardTests(unittest.TestCase):
    """NFR-01: kode aplikasi tidak boleh memakai library jaringan."""

    # selftest.py mengimpor socket hanya untuk MEMBLOKIR upaya koneksi (lihat tes di bawah).
    ALLOWED = {("selftest.py", "socket")}
    FORBIDDEN = ("socket", "urllib", "http.client", "httplib", "requests", "aiohttp", "ftplib",
                 "smtplib", "telnetlib", "xmlrpc", "websocket", "httpx")

    def test_no_network_imports_in_app(self):
        import ast
        root = Path(__file__).resolve().parent.parent / "app"
        offenders = []
        for py in root.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for n in names:
                    if (py.name, n) in self.ALLOWED:
                        continue
                    if any(n == f or n.startswith(f + ".") for f in self.FORBIDDEN):
                        offenders.append((py.name, n))
        self.assertEqual(offenders, [])

    def test_selftest_only_references_socket_to_block_it(self):
        """selftest.py boleh mengimpor socket hanya untuk memblokir/mencatat upaya koneksi.
        Pastikan tidak ada satu pun PEMANGGILAN fungsi jaringan di dalamnya."""
        import ast
        tree = ast.parse((Path(__file__).resolve().parent.parent / "app" / "selftest.py").read_text(encoding="utf-8"))
        network_calls = {"connect", "connect_ex", "sendto", "send", "sendall", "bind", "listen", "accept",
                         "create_connection", "getaddrinfo", "gethostbyname", "socket"}
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if name in network_calls:
                    offenders.append((name, node.lineno))
        self.assertEqual(offenders, [], "selftest.py tidak boleh memanggil fungsi jaringan")


if __name__ == "__main__":
    unittest.main()
