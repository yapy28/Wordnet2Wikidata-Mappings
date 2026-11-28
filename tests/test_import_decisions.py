import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from tests import _paths  # noqa: F401
import import_decisions as imp

HEAD = ["Property", "Synset / ILI", "Decision", "Keep QID", "Note"]
KNOWN = {("P8814", "0000-n"): {"items": "Q1 - a  [KEEP]\nQ2 - b  [REMOVE]"},
         ("P5063", "i1"): {"items": "Q3 - c  [VALID]\nQ4 - d  [VALID]"}}


class ReadDecisionsTests(unittest.TestCase):
    def write(self, tabs):
        wb = Workbook()
        wb.remove(wb.active)
        for title, rows in tabs.items():
            ws = wb.create_sheet(title)
            ws.append(HEAD)
            for r in rows:
                ws.append(r)
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        wb.save(tmp.name)
        return tmp.name

    def test_groups_tab(self):
        p = self.write({"Groups": [["P8814", "0000-n", "keep one", "Q2", "n"], ["P5063", "i1", "keep all", "Q3", ""]]})
        self.assertEqual(imp.read_decisions(p, KNOWN), {("P8814", "0000-n"): ("keep one", "Q2", "n"),
                                                        ("P5063", "i1"): ("keep all", "", "")})

    def test_old_words_are_rewritten(self):
        p = self.write({"Groups": [["P8814", "0000-n", "Keep", "Q1", ""], ["P5063", "i1", "leave", "", ""]]})
        self.assertEqual(imp.read_decisions(p, KNOWN), {("P8814", "0000-n"): ("keep one", "Q1", ""),
                                                        ("P5063", "i1"): ("keep all", "", "")})

    def test_old_two_tab_sheet_still_reads_and_catches_conflicts(self):
        ok = self.write({"Review queue": [["P8814", "0000-n", "defer", "", ""]],
                         "All groups": [["P8814", "0000-n", "decide later", "", ""]]})
        self.assertEqual(imp.read_decisions(ok, KNOWN), {("P8814", "0000-n"): ("decide later", "", "")})
        clash = self.write({"Review queue": [["P8814", "0000-n", "defer", "", ""]],
                            "All groups": [["P8814", "0000-n", "keep", "Q1", ""]]})
        with self.assertRaises(SystemExit):
            imp.read_decisions(clash, KNOWN)

    def test_sheet_without_a_decision_tab_exits(self):
        with self.assertRaises(SystemExit):
            imp.read_decisions(self.write({"Sheet1": [["P8814", "0000-n", "keep one", "Q1", ""]]}), KNOWN)

    def test_unknown_decision_and_keep_outside_group_exit(self):
        for row in (["P8814", "0000-n", "delete", "", ""], ["P8814", "0000-n", "keep one", "Q9", ""]):
            with self.assertRaises(SystemExit):
                imp.read_decisions(self.write({"Groups": [row]}), KNOWN)


if __name__ == "__main__":
    unittest.main()
