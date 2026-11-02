"""Consistency checks on the generated outputs in data/output/<run>/ (skipped if not generated)."""
import csv
import re
import unittest
from collections import Counter, defaultdict

from tests import _paths
import generate_dashboard as gd

RUN = _paths.RUN_DIR
NEEDED = ["p8814_violations_final.csv", "p5063_violations_final.csv", "keep_decisions.csv", "source_crosscheck.csv",
          "quickstatements/p8814_fixes_quickstatements.txt", "quickstatements/p5063_fixes_quickstatements.txt"]
HAVE_DATA = all((RUN / n).exists() for n in NEEDED)


def rows(name):
    with open(RUN / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@unittest.skipUnless(HAVE_DATA, "generate the outputs first")
class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.fix = {"P8814": gd.load_fixes(RUN / "quickstatements/p8814_fixes_quickstatements.txt"),
                    "P5063": gd.load_fixes(RUN / "quickstatements/p5063_fixes_quickstatements.txt")}
        self.decisions = {(r["prop"], r["value"]): r for r in rows("keep_decisions.csv")}
        p5063 = {}
        for r in rows("p5063_violations_final.csv"):
            p5063.setdefault((r["qid"], r["ili"]), r)  # raw export repeats each pair
        self.violations = {"P8814": rows("p8814_violations_final.csv"), "P5063": list(p5063.values())}
        self.field = {"P8814": "synset_id", "P5063": "ili"}
        self.reasons = {k: d["reason"] for k, d in self.decisions.items()}
        self.dnotes = {k: d.get("note", "") for k, d in self.decisions.items()}
        # groups held by a human decision: no removals, keep_qid empty
        self.held = {k for k, d in self.decisions.items() if d["reason"] in ("decision_leave", "defer")}

    def real_groups(self, prop):
        g = defaultdict(set)
        for r in self.violations[prop]:
            if r["is_real_violation"] == "TRUE":
                g[r[self.field[prop]]].add(r["qid"])
        return g

    def test_removals_equal_real_rows_minus_groups(self):
        for prop in ("P8814", "P5063"):
            g = self.real_groups(prop)
            active = {v: q for v, q in g.items() if (prop, v) not in self.held}
            self.assertEqual(len(self.fix[prop]), sum(len(q) for q in active.values()) - len(active), prop)

    def test_roles_partition_every_row(self):
        for prop, field in (("P8814", "synset_id"), ("P5063", "ili")):
            rows_ = gd.build_rows(self.violations[prop], self.fix[prop], field, prop, {}, self.reasons, self.dnotes)
            counts = Counter(r["role"] for r in rows_)
            held_groups = sum(1 for v in self.real_groups(prop) if (prop, v) in self.held)
            self.assertEqual(counts["unresolved"], 0, prop)
            self.assertEqual(sum(counts.values()), len(self.violations[prop]))
            self.assertEqual(counts["remove"], len(self.fix[prop]))
            self.assertEqual(counts["keep"], len(self.real_groups(prop)) - held_groups)

    def test_every_group_has_one_keep_inside_the_group(self):
        for prop in ("P8814", "P5063"):
            for value, qids in self.real_groups(prop).items():
                d = self.decisions[(prop, value)]
                if (prop, value) in self.held:
                    self.assertEqual(d["keep_qid"], "")
                    self.assertEqual(d["remove_qids"], "")
                    continue
                self.assertIn(d["keep_qid"], qids)
                self.assertEqual(set(d["remove_qids"].split("|")), qids - {d["keep_qid"]})

    def test_removal_lines_match_decisions(self):
        for prop in ("P8814", "P5063"):
            for f in self.fix[prop]:
                d = self.decisions[(prop, f["value"])]
                self.assertEqual(f["keep"], d["keep_qid"])
                self.assertIn(f["remove"], d["remove_qids"].split("|"))
                self.assertNotEqual(f["remove"], f["keep"])

    def test_source_pick_is_always_the_keep_unless_decided(self):
        for r in rows("source_crosscheck.csv"):
            key = (r["prop"], r["value"])
            if r["source_pick"] and key in self.decisions:
                d = self.decisions[key]
                if d["reason"] in ("decision", "decision_leave", "defer"):
                    continue  # a human decision overrides the source pick by design
                self.assertEqual(d["keep_qid"], r["source_pick"])

    def test_no_qid_is_removed_where_it_is_also_kept_for_same_value(self):
        for prop in ("P8814", "P5063"):
            removed = {(f["value"], f["remove"]) for f in self.fix[prop]}
            kept = {(f["value"], f["keep"]) for f in self.fix[prop]}
            self.assertFalse(removed & kept)

    def test_quickstatements_lines_are_well_formed(self):
        for prop, name in (("P8814", "p8814"), ("P5063", "p5063")):
            pattern = re.compile(rf"^-Q\d+\|{prop}\|[^|]+\|S248\|Q\d+$")
            for line in (RUN / f"quickstatements/{name}_fixes_quickstatements.txt").read_text().splitlines():
                if line.startswith("-Q"):
                    self.assertRegex(line, pattern)


if __name__ == "__main__":
    unittest.main()
