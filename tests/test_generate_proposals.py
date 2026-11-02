import unittest

from tests import _paths  # noqa: F401
import generate_proposals_v2 as gp


def qd(qid, label="", notes="", members="", definition="", desc=""):
    return {"qid": qid, "wd_label": label, "notes": notes, "synset_members": members,
            "synset_definition": definition, "wd_description": desc}


class KeepP8814Tests(unittest.TestCase):
    def test_source_pick_beats_every_heuristic(self):
        group = [qd("Q1", notes="QID in members: Q1"), qd("Q2")]
        self.assertEqual(gp.choose_keep_p8814(group, "Q2"), ("Q2", "source"))

    def test_source_pick_outside_group_is_ignored(self):
        group = [qd("Q1", notes="QID in members: Q1"), qd("Q2")]
        self.assertEqual(gp.choose_keep_p8814(group, "Q9"), ("Q1", "members_note"))

    def test_similarity_note(self):
        group = [qd("Q1", notes="Neither | Similarity: Q1:0, Q2:3"), qd("Q2")]
        self.assertEqual(gp.choose_keep_p8814(group), ("Q2", "similarity_note"))

    def test_label_in_members(self):
        group = [qd("Q1", label="cat", members="cat|true cat"), qd("Q2", label="felid")]
        self.assertEqual(gp.choose_keep_p8814(group), ("Q1", "label_in_members"))

    def test_fallback_is_weak(self):
        keep, reason = gp.choose_keep_p8814([qd("Q1"), qd("Q2")])
        self.assertEqual((keep, reason), ("Q1", "fallback"))
        self.assertIn(reason, gp.WEAK_REASONS)


class KeepP5063Tests(unittest.TestCase):
    def test_source_first(self):
        self.assertEqual(gp.choose_keep_p5063([qd("Q1"), qd("Q2")], "Q2"), ("Q2", "source"))

    def test_clear_score_winner(self):
        group = [qd("Q1", label="hoax", members="fraud|hoax"), qd("Q2", label="deception")]
        self.assertEqual(gp.choose_keep_p5063(group), ("Q1", "score"))

    def test_tie_is_weak(self):
        group = [qd("Q1", label="hoax", members="hoax"), qd("Q2", label="hoax", members="hoax")]
        keep, reason = gp.choose_keep_p5063(group)
        self.assertEqual(reason, "score_tie")
        self.assertIn(reason, gp.WEAK_REASONS)

    def test_no_evidence_is_weak(self):
        self.assertEqual(gp.choose_keep_p5063([qd("Q1"), qd("Q2")])[1], "fallback")


if __name__ == "__main__":
    unittest.main()
