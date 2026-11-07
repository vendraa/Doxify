import tempfile
import unittest
from pathlib import Path

from app.utils.filenames import MAX_PATH_LENGTH, build_pdf_path, sanitize_stem, unique_path


class FilenameTests(unittest.TestCase):
    def test_forbidden_characters_replaced(self):
        self.assertEqual(sanitize_stem('a<b>c:d"e/f\\g|h?i*j'), "a_b_c_d_e_f_g_h_i_j")

    def test_trailing_dots_spaces_stripped(self):
        self.assertEqual(sanitize_stem("  laporan.. "), "laporan")

    def test_reserved_names_prefixed(self):
        self.assertEqual(sanitize_stem("CON"), "_CON")
        self.assertEqual(sanitize_stem("lpt1.final"), "_lpt1.final")

    def test_empty_becomes_default(self):
        self.assertEqual(sanitize_stem("..."), "dokumen")

    def test_unicode_and_spaces_kept(self):
        self.assertEqual(sanitize_stem("Scan KTP — Budi é"), "Scan KTP — Budi é")

    def test_build_adds_pdf_once(self):
        self.assertEqual(build_pdf_path("C:/x", "hasil.pdf").name, "hasil.pdf")
        self.assertEqual(build_pdf_path("C:/x", "hasil").name, "hasil.pdf")
        self.assertEqual(build_pdf_path("C:/x", "HASIL.PDF").name, "HASIL.pdf")

    def test_long_name_shortened_within_max_path(self):
        p = build_pdf_path("/tmp/" + "d" * 50, "n" * 500)
        self.assertLessEqual(len(str(p)) + len(" (99)"), MAX_PATH_LENGTH)

    def test_directory_too_long_rejected(self):
        with self.assertRaises(ValueError):
            build_pdf_path("/" + "d" * 300, "x")

    def test_unique_path_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "a.pdf"
            self.assertEqual(unique_path(base), base)
            base.write_bytes(b"x")
            self.assertEqual(unique_path(base).name, "a (1).pdf")
            (Path(d) / "a (1).pdf").write_bytes(b"x")
            self.assertEqual(unique_path(base).name, "a (2).pdf")


if __name__ == "__main__":
    unittest.main()
