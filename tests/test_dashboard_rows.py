import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import generate_dashboard as gd


def v(qid, value, real, category="ONE_IN_MEMBERS_DESC_MISMATCH", field="synset_id"):
    row = {"qid": qid, "wikidata_label": qid.lower(), "wikidata_description": "", "synset_id": "", "ili": "",
           "synset_ili": "", "synset_definition": "", "synset_members": "a|b", "synset_source": "OEWN",
           "category": category, "is_real_violation": "TRUE" if real else "FALSE", "confidence": "90"}
    row[field] = value
    return row


class BuildRowsTests(unittest.TestCase):
    def test_roles(self):
        fixes = [{"remove": "Q2", "prop": "P8814", "value": "s1", "keep": "Q1"}]
        rows = gd.build_rows([v("Q1", "s1", True), v("Q2", "s1", True), v("Q3", "s2", False)],
                             fixes, "synset_id", "P8814", {}, {})
        self.assertEqual([r["role"] for r in rows], ["keep", "remove", "valid"])
        self.assertEqual(rows[1]["keep"], "Q1")

    def test_weak_decision_is_flagged_for_review(self):
        fixes = [{"remove": "Q2", "prop": "P8814", "value": "s1", "keep": "Q1"}]
        weak = gd.build_rows([v("Q1", "s1", True, "DIFFERENT_CONCEPTS"), v("Q2", "s1", True, "DIFFERENT_CONCEPTS")],
                             fixes, "synset_id", "P8814", {}, {("P8814", "s1"): "similarity_note"})
        self.assertTrue(all(r["rev"] for r in weak))

    def test_source_backed_decision_is_not_flagged(self):
        fixes = [{"remove": "Q2", "prop": "P8814", "value": "s1", "keep": "Q1"}]
        cc = {("P8814", "s1"): {"source_qids": ["Q1"]}}
        rows = gd.build_rows([v("Q1", "s1", True, "DIFFERENT_CONCEPTS"), v("Q2", "s1", True, "DIFFERENT_CONCEPTS")],
                             fixes, "synset_id", "P8814", cc, {("P8814", "s1"): "source"})
        self.assertFalse(any(r["rev"] for r in rows))
        self.assertEqual([r["se"] for r in rows], ["yes", "other"])

    def test_tie_in_p5063_is_flagged_even_outside_review_categories(self):
        fixes = [{"remove": "Q2", "prop": "P5063", "value": "i1", "keep": "Q1"}]
        rows = gd.build_rows([v("Q1", "i1", True, "DISSIMILAR_QIDS", "ili"), v("Q2", "i1", True, "DISSIMILAR_QIDS", "ili")],
                             fixes, "ili", "P5063", {}, {("P5063", "i1"): "score_tie"})
        self.assertTrue(all(r["rev"] for r in rows))

    def test_decision_remove_marks_every_item_and_is_not_weak(self):
        fixes = [{"remove": "Q1", "prop": "P8814", "value": "s1", "keep": ""},
                 {"remove": "Q2", "prop": "P8814", "value": "s1", "keep": ""}]
        rows = gd.build_rows([v("Q1", "s1", True, "DIFFERENT_CONCEPTS"), v("Q2", "s1", True, "DIFFERENT_CONCEPTS")],
                             fixes, "synset_id", "P8814", {}, {("P8814", "s1"): "decision_remove"})
        self.assertEqual([r["role"] for r in rows], ["remove", "remove"])
        self.assertTrue(all(r["keep"] == "" for r in rows))
        self.assertFalse(any(r["rev"] for r in rows))


class LoadFixesTests(unittest.TestCase):
    def write_qs(self, text):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        tmp.write(text)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def test_kept_group_line_has_the_keep_qid(self):
        fixes = gd.load_fixes(self.write_qs("-Q2|P8814|s1|S248|Q1\n"))
        self.assertEqual(fixes, [{"remove": "Q2", "prop": "P8814", "value": "s1", "keep": "Q1"}])

    def test_remove_all_line_has_no_keep_part(self):
        fixes = gd.load_fixes(self.write_qs("-Q2|P8814|s1\n"))
        self.assertEqual(fixes, [{"remove": "Q2", "prop": "P8814", "value": "s1", "keep": ""}])

    def test_comments_and_blank_lines_are_skipped(self):
        self.assertEqual(gd.load_fixes(self.write_qs("# header\n\n")), [])


if __name__ == "__main__":
    unittest.main()
