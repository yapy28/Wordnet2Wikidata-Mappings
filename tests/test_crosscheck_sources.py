import csv
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from tests import _paths  # noqa: F401
import crosscheck_sources as cs


class ClassifyTests(unittest.TestCase):
    def test_not_found(self):
        self.assertEqual(cs.classify(["Q1", "Q2"], [], False), (cs.MISSING, ""))

    def test_found_without_qid(self):
        self.assertEqual(cs.classify(["Q1", "Q2"], [], True), (cs.NO_QID, ""))

    def test_source_names_other_qid(self):
        self.assertEqual(cs.classify(["Q1", "Q2"], ["Q9"], True), (cs.OTHER, ""))

    def test_exactly_one_group_qid_is_picked(self):
        self.assertEqual(cs.classify(["Q1", "Q2"], ["Q2", "Q9"], True), (cs.PICK, "Q2"))

    def test_source_lists_several_gives_no_pick(self):
        self.assertEqual(cs.classify(["Q1", "Q2"], ["Q1", "Q2"], True), (cs.SEVERAL, ""))


class NormalizeTests(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(cs.normalize_qids(None), [])
        self.assertEqual(cs.normalize_qids("Q1"), ["Q1"])
        self.assertEqual(cs.normalize_qids("Q1|Q2"), ["Q1", "Q2"])
        self.assertEqual(cs.normalize_qids(["Q1", " Q2 "]), ["Q1", "Q2"])


class EndToEndTests(unittest.TestCase):
    def test_crosscheck_over_synthetic_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "yaml").mkdir()
            (tmp / "yaml" / "noun.test.yaml").write_text(
                "00000001-n:\n  definition: [a thing]\n  partOfSpeech: n\n  ili: i1\n  wikidata: Q2\n"
                "00000002-n:\n  definition: [other]\n  partOfSpeech: n\n  ili: i2\n"
                "not-a-synset:\n  hello: world\n", encoding="utf-8")
            synsets = defaultdict(list)
            cs.read_yaml_tree(tmp / "yaml", "OEWN", synsets)
            self.assertEqual(sorted(synsets), ["00000001-n", "00000002-n"])  # non-synset entries skipped
            by_ili = defaultdict(list)
            for entries in synsets.values():
                for e in entries:
                    by_ili[e["ili"]].append(e)

            run = tmp / "run"
            run.mkdir()
            cols = ["qid", "synset_id", "ili", "is_real_violation"]
            for name, rows in (("p8814", [("Q1", "00000001-n", "", "TRUE"), ("Q2", "00000001-n", "", "TRUE"),
                                          ("Q3", "00000002-n", "", "TRUE"), ("Q4", "00000002-n", "", "TRUE")]),
                               ("p5063", [("Q1", "", "i1", "TRUE"), ("Q2", "", "i1", "TRUE")])):
                with open(run / f"{name}_violations_final.csv", "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(cols)
                    w.writerows(rows)
            out = {(r["prop"], r["value"]): r for r in cs.crosscheck(run, synsets, by_ili)}
            self.assertEqual(out[("P8814", "00000001-n")]["source_pick"], "Q2")
            self.assertEqual(out[("P8814", "00000002-n")]["status"], cs.NO_QID)
            self.assertEqual(out[("P5063", "i1")]["source_pick"], "Q2")


if __name__ == "__main__":
    unittest.main()
