import tempfile
import unittest
from pathlib import Path

from app.converters.base import ConversionResult, FailedFile
from app.ui.logic import (
    FileListState, format_size, natural_key, summarize_rejections,
    summarize_result, suggest_output_name,
)
from tests.helpers import make_jpeg, make_png


class StateTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.state = FileListState()

    def files(self, *names):
        out = []
        for n in names:
            p = self.dir / n
            (make_png if n.lower().endswith(".png") else make_jpeg)(p)
            out.append(p)
        return out

    def names(self):
        return [p.name for p in self.state.paths]


class AddTests(StateTestCase):
    def test_add_keeps_given_order(self):
        a, b, c = self.files("c.jpg", "a.png", "b.jpeg")
        rep = self.state.add([a, b, c])
        self.assertEqual(self.names(), ["c.jpg", "a.png", "b.jpeg"])
        self.assertEqual(len(rep.added), 3)

    def test_duplicates_skipped_and_reported(self):
        (a,) = self.files("a.jpg")
        self.state.add([a])
        rep = self.state.add([a, str(a)])
        self.assertEqual(len(self.state), 1)
        self.assertEqual(len(rep.duplicates), 2)

    def test_duplicate_within_same_batch(self):
        (a,) = self.files("a.jpg")
        rep = self.state.add([a, a])
        self.assertEqual((len(rep.added), len(rep.duplicates)), (1, 1))

    def test_unsupported_and_missing_rejected(self):
        (a,) = self.files("a.jpg")
        txt = self.dir / "x.txt"; txt.write_text("x")
        rep = self.state.add([a, txt, self.dir / "hilang.png"])
        self.assertEqual(self.names(), ["a.jpg"])
        reasons = {p.name: r for p, r in rep.rejected}
        self.assertIn("tidak didukung", reasons["x.txt"])
        self.assertIn("tidak ditemukan", reasons["hilang.png"])

    def test_uppercase_extension_accepted(self):
        (a,) = self.files("FOTO.JPG")
        self.assertEqual(len(self.state.add([a]).added), 1)

    def test_folder_expanded_in_natural_order(self):
        sub = self.dir / "scan"; sub.mkdir()
        for n in ("foto10.jpg", "foto2.jpg", "foto1.png", "catatan.txt"):
            (make_png if n.endswith(".png") else make_jpeg)(sub / n) if n != "catatan.txt" else (sub / n).write_text("x")
        self.state.add([sub])
        self.assertEqual(self.names(), ["foto1.png", "foto2.jpg", "foto10.jpg"])

    def test_empty_folder_rejected(self):
        sub = self.dir / "kosong"; sub.mkdir()
        rep = self.state.add([sub])
        self.assertEqual(len(self.state), 0)
        self.assertIn("tidak berisi gambar", rep.rejected[0][1])

    def test_size_recorded_and_total(self):
        (a,) = self.files("a.jpg")
        self.state.add([a])
        self.assertEqual(self.state.entries[0].size, a.stat().st_size)
        self.assertEqual(self.state.total_size, a.stat().st_size)

    def test_unicode_and_spaces(self):
        p = make_jpeg(self.dir / "Scan KTP — Budi é.jpg")
        self.assertEqual(len(self.state.add([p]).added), 1)


class EditTests(StateTestCase):
    def setUp(self):
        super().setUp()
        self.state.add(self.files("a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"))

    def test_remove_and_clear(self):
        self.state.remove([1, 3, 99, -1])
        self.assertEqual(self.names(), ["a.jpg", "c.jpg", "e.jpg"])
        self.state.clear()
        self.assertEqual(len(self.state), 0)

    def test_move_up_single(self):
        self.assertEqual(self.state.move_up([2]), [1])
        self.assertEqual(self.names(), ["a.jpg", "c.jpg", "b.jpg", "d.jpg", "e.jpg"])

    def test_move_up_at_top_is_noop(self):
        self.assertEqual(self.state.move_up([0]), [0])
        self.assertEqual(self.names()[0], "a.jpg")

    def test_move_up_block_keeps_internal_order(self):
        self.assertEqual(self.state.move_up([2, 3]), [1, 2])
        self.assertEqual(self.names(), ["a.jpg", "c.jpg", "d.jpg", "b.jpg", "e.jpg"])

    def test_move_up_block_touching_top_does_not_split(self):
        self.assertEqual(self.state.move_up([0, 1]), [0, 1])
        self.assertEqual(self.names(), ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"])

    def test_move_down_single_and_bottom(self):
        self.assertEqual(self.state.move_down([1]), [2])
        self.assertEqual(self.names(), ["a.jpg", "c.jpg", "b.jpg", "d.jpg", "e.jpg"])
        self.assertEqual(self.state.move_down([4]), [4])

    def test_move_down_block(self):
        self.assertEqual(self.state.move_down([1, 2]), [2, 3])
        self.assertEqual(self.names(), ["a.jpg", "d.jpg", "b.jpg", "c.jpg", "e.jpg"])

    def test_move_up_noncontiguous_selection(self):
        self.assertEqual(self.state.move_up([1, 3]), [0, 2])
        self.assertEqual(self.names(), ["b.jpg", "a.jpg", "d.jpg", "c.jpg", "e.jpg"])

    def test_move_to_later_position(self):
        # jatuhkan 'a' di atas 'd' (baris 3): a masuk antara c dan d
        self.assertEqual(self.state.move_to([0], 3), [2])
        self.assertEqual(self.names(), ["b.jpg", "c.jpg", "a.jpg", "d.jpg", "e.jpg"])

    def test_move_to_earlier_position(self):
        self.assertEqual(self.state.move_to([3], 1), [1])
        self.assertEqual(self.names(), ["a.jpg", "d.jpg", "b.jpg", "c.jpg", "e.jpg"])

    def test_move_to_end_and_start(self):
        self.state.move_to([0], 5)
        self.assertEqual(self.names()[-1], "a.jpg")
        self.state.move_to([4], 0)
        self.assertEqual(self.names()[0], "a.jpg")

    def test_move_to_multiple_selection(self):
        self.assertEqual(self.state.move_to([0, 2], 5), [3, 4])
        self.assertEqual(self.names(), ["b.jpg", "d.jpg", "e.jpg", "a.jpg", "c.jpg"])

    def test_move_to_onto_itself_is_noop(self):
        before = self.names()
        self.state.move_to([2], 2)
        self.state.move_to([2], 3)
        self.assertEqual(self.names(), before)

    def test_move_to_ignores_invalid(self):
        before = self.names()
        self.assertEqual(self.state.move_to([], 1), [])
        self.assertEqual(self.state.move_to([99], 1), [])
        self.assertEqual(self.names(), before)


class HelperTests(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1023), "1023 B")
        self.assertEqual(format_size(1536), "1,5 KB")
        self.assertEqual(format_size(5 * 1024 * 1024), "5,0 MB")
        self.assertEqual(format_size(3 * 1024 ** 3), "3,0 GB")

    def test_natural_key(self):
        names = ["f10.jpg", "f2.jpg", "F1.jpg"]
        self.assertEqual(sorted(names, key=natural_key), ["F1.jpg", "f2.jpg", "f10.jpg"])

    def test_suggest_output_name(self):
        self.assertEqual(suggest_output_name([Path("/x/KTP depan.jpg")]), "KTP depan.pdf")
        self.assertEqual(suggest_output_name([Path("a.jpg"), Path("b.jpg")]), "gabungan.pdf")


class SummaryTests(unittest.TestCase):
    def test_success_merged(self):
        r = ConversionResult(outputs=[Path("/o/h.pdf")], converted=[Path("a.jpg"), Path("b.jpg")])
        s = summarize_result(r, "merged")
        self.assertEqual(s.kind, "success")
        self.assertIn("2 gambar digabung", s.text)
        self.assertEqual(s.reveal_path, Path("/o/h.pdf"))

    def test_success_separate(self):
        r = ConversionResult(outputs=[Path("/o/a.pdf"), Path("/o/b.pdf")], converted=[Path("a.jpg"), Path("b.jpg")])
        s = summarize_result(r, "separate")
        self.assertIn("2 PDF dibuat", s.text)
        self.assertEqual(s.kind, "success")

    def test_warning_when_some_failed(self):
        r = ConversionResult(outputs=[Path("/o/h.pdf")], converted=[Path("a.jpg")],
                             failed=[FailedFile(Path("rusak.jpg"), "File rusak")])
        s = summarize_result(r, "merged")
        self.assertEqual(s.kind, "warning")
        self.assertIn("1 berhasil, 1 dilewati", s.text)
        self.assertEqual(s.details, "rusak.jpg: File rusak")

    def test_all_failed_is_error(self):
        r = ConversionResult(failed=[FailedFile(Path("x.jpg"), "rusak")])
        s = summarize_result(r, "merged")
        self.assertEqual(s.kind, "error")
        self.assertIsNone(s.reveal_path)

    def test_cancelled_variants(self):
        s = summarize_result(ConversionResult(cancelled=True), "merged")
        self.assertEqual(s.kind, "cancelled")
        self.assertIn("Tidak ada file yang disimpan", s.text)
        s = summarize_result(ConversionResult(cancelled=True, outputs=[Path("/o/a.pdf")]), "separate")
        self.assertIn("1 PDF sudah tersimpan", s.text)

    def test_details_truncated(self):
        r = ConversionResult(outputs=[Path("/o/h.pdf")], converted=[Path("a.jpg")],
                             failed=[FailedFile(Path(f"{i}.jpg"), "rusak") for i in range(25)])
        lines = summarize_result(r, "merged").details.splitlines()
        self.assertEqual(len(lines), 21)
        self.assertIn("dan 5 file lainnya", lines[-1])

    def test_summarize_rejections(self):
        from app.ui.logic import AddReport
        rep = AddReport(rejected=[(Path("x.txt"), "Format tidak didukung")])
        self.assertEqual(summarize_rejections(rep), "x.txt: Format tidak didukung")


if __name__ == "__main__":
    unittest.main()
