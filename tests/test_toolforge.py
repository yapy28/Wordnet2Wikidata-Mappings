"""Review app (toolforge/app.py): voting rules, allowlist, exports. Runs on an in-memory database."""
import json
import os
import sys
import unittest
from pathlib import Path

os.environ["FLASK_APP_AUTOCREATE"] = "0"  # do not build the module-level app (it would create review.db)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolforge"))
import app as review  # noqa: E402

GROUPS = json.loads((Path(review.HERE) / "groups.json").read_text(encoding="utf-8"))["groups"]
G = next(g for g in GROUPS if g["prop"] == "P8814" and len(g["qids"]) == 2)
OTHER = [q for q in G["qids"]][1]


def make_client():
    app = review.create_app({"DATABASE_URL": "sqlite:///:memory:", "DEV_LOGIN": True, "TESTING": True,
                             "ALLOWED_USERS": ["alice", "bob"]})
    return app.test_client()


def login(client, name):
    client.get(f"/login?as={name}")


def vote(client, action, keep="", note=""):
    return client.post("/vote", data={"prop": G["prop"], "value": G["value"], "action": action,
                                      "keep_qid": keep, "note": note})


class GroupStatus(unittest.TestCase):
    def v(self, action, keep=""):
        return {"action": action, "keep_qid": keep}

    def test_single_vote_is_pending(self):
        self.assertEqual(review.group_status([self.v("keep", "Q1")])[0], "pending")

    def test_two_agreeing_votes_accept(self):
        self.assertEqual(review.group_status([self.v("keep", "Q1"), self.v("keep", "Q1")]),
                         ("accepted", ("keep", "Q1")))

    def test_same_action_different_keep_is_conflict(self):
        self.assertEqual(review.group_status([self.v("keep", "Q1"), self.v("keep", "Q2")])[0], "conflict")

    def test_two_defers_never_accept(self):
        self.assertNotEqual(review.group_status([self.v("defer"), self.v("defer")])[0], "accepted")

    def test_two_removes_accept_with_no_keep(self):
        self.assertEqual(review.group_status([self.v("remove"), self.v("remove")]),
                         ("accepted", ("remove", "")))

    def test_keep_against_remove_is_conflict(self):
        self.assertEqual(review.group_status([self.v("keep", "Q1"), self.v("remove")])[0], "conflict")


class Flow(unittest.TestCase):
    def setUp(self):
        self.c = make_client()

    def test_anonymous_and_unlisted_users_are_refused(self):
        self.assertEqual(self.c.get("/review").status_code, 401)
        login(self.c, "mallory")
        self.assertEqual(self.c.get("/review").status_code, 403)
        self.assertEqual(vote(self.c, "leave").status_code, 403)

    def test_invalid_votes_are_rejected(self):
        login(self.c, "alice")
        self.assertEqual(vote(self.c, "delete").status_code, 400)
        self.assertEqual(vote(self.c, "keep", keep="Q0").status_code, 400)  # not in the group
        self.assertEqual(self.c.post("/vote", data={"prop": "P8814", "value": "nope", "action": "leave"}).status_code, 400)

    def test_two_reviewers_agreeing_export_the_removals(self):
        keep = G["qids"][0]
        for name in ("alice", "bob"):
            login(self.c, name)
            self.assertEqual(vote(self.c, "keep", keep).status_code, 302)
        qs = self.c.get("/export/quickstatements.txt").get_data(as_text=True)
        self.assertEqual(qs.strip().splitlines(), [f'-{q}|{G["prop"]}|"{G["value"]}"' for q in G["qids"] if q != keep])
        self.assertIn(f'{G["prop"]},{G["value"]},keep,{keep},', self.c.get("/export/decisions.csv").get_data(as_text=True))

    def test_one_vote_is_not_enough(self):
        login(self.c, "alice")
        vote(self.c, "keep", G["qids"][0])
        self.assertEqual(self.c.get("/export/quickstatements.txt").get_data(as_text=True), "")

    def test_revoting_replaces_the_old_vote(self):
        login(self.c, "alice")
        vote(self.c, "keep", G["qids"][0])
        vote(self.c, "leave")
        login(self.c, "bob")
        vote(self.c, "leave")
        self.assertEqual(self.c.get("/export/quickstatements.txt").get_data(as_text=True), "")
        self.assertIn(f'{G["prop"]},{G["value"]},leave,,', self.c.get("/export/decisions.csv").get_data(as_text=True))

    def test_leave_never_exports_a_removal(self):
        for name in ("alice", "bob"):
            login(self.c, name)
            vote(self.c, "leave")
        self.assertEqual(self.c.get("/export/quickstatements.txt").get_data(as_text=True), "")

    def test_remove_exports_every_qid(self):
        for name in ("alice", "bob"):
            login(self.c, name)
            self.assertEqual(vote(self.c, "remove", keep=G["qids"][0]).status_code, 302)
        qs = self.c.get("/export/quickstatements.txt").get_data(as_text=True)
        self.assertEqual(qs.strip().splitlines(), [f'-{q}|{G["prop"]}|"{G["value"]}"' for q in G["qids"]])
        self.assertIn(f'{G["prop"]},{G["value"]},remove,,', self.c.get("/export/decisions.csv").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
