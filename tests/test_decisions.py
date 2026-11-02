import csv
import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import generate_proposals_v2 as gp


def decision_row(prop, value, action, keep_qid="", note=""):
    return {"prop": prop, "value": value, "action": action, "keep_qid": keep_qid, "note": note}


class LoadDecisionsTests(unittest.TestCase):
    def write(self, rows):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
        w = csv.DictWriter(tmp, fieldnames=["prop", "value", "action", "keep_qid", "note"])
        w.writeheader()
        w.writerows(rows)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def test_missing_file_is_empty(self):
        self.assertEqual(gp.load_decisions(path="/nonexistent/decisions.csv"), {})

    def test_empty_action_rows_are_ignored(self):
        # template rows the student has not decided yet
        self.assertEqual(gp.load_decisions(path=self.write([decision_row("P8814", "0000-n", "")])), {})

    def test_keep_leave_defer(self):
        p = self.write([decision_row("P8814", "0000-n", "keep", "Q1", "n1"),
                        decision_row("P5063", "i1", "leave", note="n2"),
                        decision_row("P5063", "i2", "defer")])
        d = gp.load_decisions(path=p)
        self.assertEqual(d[("P8814", "0000-n")], {"action": "keep", "keep_qid": "Q1", "note": "n1"})
        self.assertEqual(d[("P5063", "i1")]["action"], "leave")
        self.assertEqual(d[("P5063", "i2")]["note"], "")

    def test_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            gp.load_decisions(path=self.write([decision_row("P8814", "0000-n", "delete")]))

    def test_duplicate_group_raises(self):
        p = self.write([decision_row("P8814", "0000-n", "keep", "Q1"),
                        decision_row("P8814", "0000-n", "leave")])
        with self.assertRaises(ValueError):
            gp.load_decisions(path=p)


class ApplyDecisionTests(unittest.TestCase):
    group = [{"qid": "Q1"}, {"qid": "Q2"}]

    def test_keep_uses_decided_qid(self):
        d = {"action": "keep", "keep_qid": "Q2", "note": "x"}
        self.assertEqual(gp.apply_decision(d, self.group, ("P8814", "s")), ("Q2", "decision"))

    def test_keep_qid_outside_group_raises(self):
        d = {"action": "keep", "keep_qid": "Q9", "note": ""}
        with self.assertRaises(ValueError):
            gp.apply_decision(d, self.group, ("P8814", "s"))

    def test_leave_holds_as_decision_leave(self):
        d = {"action": "leave", "keep_qid": "", "note": ""}
        self.assertEqual(gp.apply_decision(d, self.group, ("P8814", "s")), ("hold", "decision_leave"))

    def test_defer_holds(self):
        d = {"action": "defer", "keep_qid": "", "note": ""}
        self.assertEqual(gp.apply_decision(d, self.group, ("P8814", "s")), ("hold", "defer"))


class UnknownDecisionTests(unittest.TestCase):
    def test_unknown_group_raises(self):
        with self.assertRaises(ValueError):
            gp.check_unknown_decisions({("P8814", "nope-n"): {}}, {("P8814", "real-n"), ("P5063", "i1")})

    def test_known_groups_pass(self):
        gp.check_unknown_decisions({("P8814", "real-n"): {}}, {("P8814", "real-n"), ("P5063", "i1")})


if __name__ == "__main__":
    unittest.main()
