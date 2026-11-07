import io
import unittest
from pathlib import Path
import tempfile

from PIL import Image, ImageChops

from app.utils.metadata import build_orientation_segment, strip_jpeg_metadata
from tests.helpers import make_jpeg


class StripMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _roundtrip(self, **kw):
        src = make_jpeg(self.dir / "a.jpg", **kw)
        original = src.read_bytes()
        return original, strip_jpeg_metadata(original, kw.get("orientation") or 1)

    def test_gps_and_camera_removed(self):
        original, stripped = self._roundtrip(with_exif=True)
        self.assertIn(b"TestCam", original)
        self.assertNotIn(b"TestCam", stripped)
        self.assertNotIn(b"RahasiaSoftware", stripped)
        exif = Image.open(io.BytesIO(stripped)).getexif()
        self.assertNotIn(0x8825, exif)
        self.assertNotIn(0x010F, exif)

    def test_pixels_identical_lossless(self):
        original, stripped = self._roundtrip(with_exif=True, size=(321, 123))
        a = Image.open(io.BytesIO(original)).convert("RGB")
        b = Image.open(io.BytesIO(stripped)).convert("RGB")
        self.assertIsNone(ImageChops.difference(a, b).getbbox())
        self.assertLess(len(stripped), len(original))

    def test_orientation_preserved_only(self):
        _, stripped = self._roundtrip(with_exif=True, orientation=6)
        exif = Image.open(io.BytesIO(stripped)).getexif()
        self.assertEqual(exif.get(0x0112), 6)
        self.assertEqual(set(exif.keys()), {0x0112})

    def test_cmyk_jpeg_still_decodes(self):
        original, stripped = self._roundtrip(mode="CMYK")
        self.assertEqual(Image.open(io.BytesIO(stripped)).mode, "CMYK")

    def test_progressive_jpeg_supported(self):
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), (5, 90, 160)).save(buf, "JPEG", progressive=True, quality=85)
        stripped = strip_jpeg_metadata(buf.getvalue())
        img = Image.open(io.BytesIO(stripped)); img.load()
        self.assertEqual(img.size, (300, 200))

    def test_truncated_jpeg_rejected(self):
        original, _ = self._roundtrip()
        with self.assertRaises(ValueError):
            strip_jpeg_metadata(original[: len(original) // 2])

    def test_not_jpeg_rejected(self):
        with self.assertRaises(ValueError):
            strip_jpeg_metadata(b"bukan jpeg sama sekali")

    def test_orientation_segment_validation(self):
        with self.assertRaises(ValueError):
            build_orientation_segment(9)


if __name__ == "__main__":
    unittest.main()
