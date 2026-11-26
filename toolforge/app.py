"""
Review app for duplicate WordNet-to-Wikidata mappings (Toolforge).

Invited reviewers log in with their Wikimedia account (OAuth), vote keep / leave / defer / remove
on each duplicate group, and a group is accepted when two reviewers agree. 'remove' means no item
keeps the value: every statement in the group is removed. The app never edits Wikidata:
accepted removals are exported as QuickStatements for a person to run.

Groups come from groups.json (scripts/export_groups.py). Votes live in a SQL database:
SQLite locally, ToolsDB on Toolforge (set DATABASE_URL).
"""
import csv
import io
import json
import os
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, UniqueConstraint, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

HERE = Path(__file__).resolve().parent
ACTIONS = ("keep", "leave", "defer", "remove")
AGREE = 2  # reviewers who must pick the same decision for a group to be accepted
USER_AGENT = "Wordnet2Wikidata-review (https://github.com/Yapy28/Wordnet2Wikidata-Mappings)"

meta = MetaData()
votes = Table(
    "votes", meta,
    Column("prop", String(8), nullable=False),
    Column("value", String(32), nullable=False),
    Column("reviewer", String(100), nullable=False),
    Column("action", String(8), nullable=False),
    Column("keep_qid", String(16), nullable=False, default=""),
    Column("note", Text, nullable=False, default=""),
    Column("ts", DateTime, nullable=False),
    UniqueConstraint("prop", "value", "reviewer", name="one_vote_per_reviewer"),
)


def default_database_url():
    """DATABASE_URL, else ToolsDB from the credentials Toolforge injects, else a local SQLite file."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    user, password = os.environ.get("TOOL_TOOLSDB_USER"), os.environ.get("TOOL_TOOLSDB_PASSWORD")
    if user and password:  # ToolsDB databases are named <user>__<name>; create it once by hand
        return f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@tools.db.svc.wikimedia.cloud/{user}__reviews"
    return f"sqlite:///{HERE / 'review.db'}"


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite") and ":memory:" in url:
        return create_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    return create_engine(url, pool_recycle=280)


def group_status(group_votes):
    """accepted / conflict / pending for the votes of one group, plus the accepted (action, keep_qid)."""
    tally = Counter((v["action"], v["keep_qid"]) for v in group_votes)
    for decision, n in tally.most_common():
        if n >= AGREE and decision[0] != "defer":
            return "accepted", decision
    if len({(v["action"], v["keep_qid"]) for v in group_votes}) > 1 and len(group_votes) >= AGREE:
        return "conflict", None
    return "pending", None


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE_URL=default_database_url(),
        GROUPS_FILE=str(HERE / "groups.json"),
        ALLOWED_USERS=[u.strip() for u in os.environ.get("ALLOWED_USERS", "").split(",") if u.strip()],
        DEV_LOGIN=os.environ.get("DEV_LOGIN") == "1",
        OAUTH_MWURI=os.environ.get("OAUTH_MWURI", "https://meta.wikimedia.org/w/index.php"),
        CONSUMER_KEY=os.environ.get("CONSUMER_KEY", ""), CONSUMER_SECRET=os.environ.get("CONSUMER_SECRET", ""),
    )
    cfg = HERE / "config.toml"  # secrets on Toolforge; not in git
    if cfg.exists():
        app.config.from_mapping(tomllib.loads(cfg.read_text(encoding="utf-8")))
    if config:
        app.config.update(config)

    engine = make_engine(app.config["DATABASE_URL"])
    meta.create_all(engine)
    data = json.loads(Path(app.config["GROUPS_FILE"]).read_text(encoding="utf-8"))
    groups = {(g["prop"], g["value"]): g for g in data["groups"]}

    def current_user():
        return session.get("user")

    def require_reviewer():
        user = current_user()
        if not user:
            abort(401)
        if user not in app.config["ALLOWED_USERS"]:
            abort(403)
        return user

    def all_votes():
        with engine.connect() as conn:
            rows = conn.execute(select(votes)).mappings().all()
        by_group = defaultdict(list)
        for r in rows:
            by_group[(r["prop"], r["value"])].append(dict(r))
        return by_group

    # ---- login -------------------------------------------------------------------------------
    @app.get("/login")
    def login():
        if app.config["DEV_LOGIN"]:
            session["user"] = request.args.get("as", "dev")
            return redirect(url_for("index"))
        import mwoauth
        consumer = mwoauth.ConsumerToken(app.config["CONSUMER_KEY"], app.config["CONSUMER_SECRET"])
        redirect_url, request_token = mwoauth.initiate(app.config["OAUTH_MWURI"], consumer, user_agent=USER_AGENT)
        session["request_token"] = dict(zip(request_token._fields, request_token))
        return redirect(redirect_url)

    @app.get("/oauth-callback")
    def oauth_callback():
        import mwoauth
        if "request_token" not in session:
            abort(400)
        consumer = mwoauth.ConsumerToken(app.config["CONSUMER_KEY"], app.config["CONSUMER_SECRET"])
        access = mwoauth.complete(app.config["OAUTH_MWURI"], consumer,
                                  mwoauth.RequestToken(**session.pop("request_token")),
                                  request.query_string, user_agent=USER_AGENT)
        identity = mwoauth.identify(app.config["OAUTH_MWURI"], consumer, access, user_agent=USER_AGENT)
        session["user"] = identity["username"]
        return redirect(url_for("index"))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # ---- review ------------------------------------------------------------------------------
    @app.get("/")
    def index():
        user = current_user()
        allowed = user in app.config["ALLOWED_USERS"]
        by_group = all_votes() if allowed else {}
        counts = Counter(group_status(by_group.get(k, []))[0] for k in groups) if allowed else {}
        return render_template("index.html", user=user, allowed=allowed, counts=counts, total=len(groups),
                               run=data["run"])

    @app.get("/review")
    def review():
        user = require_reviewer()
        by_group = all_votes()
        only_weak = request.args.get("all") != "1"
        only_mine = request.args.get("todo", "1") == "1"
        rows = []
        for key, g in groups.items():
            if only_weak and not g["weak"]:
                continue
            gv = by_group.get(key, [])
            mine = next((v for v in gv if v["reviewer"] == user), None)
            if only_mine and mine:
                continue
            status, decision = group_status(gv)
            rows.append({"g": g, "votes": gv, "mine": mine, "status": status, "decision": decision})
            if len(rows) >= 50:
                break
        return render_template("review.html", user=user, rows=rows, only_weak=only_weak, only_mine=only_mine)

    @app.post("/vote")
    def vote():
        user = require_reviewer()
        prop, value = request.form.get("prop", ""), request.form.get("value", "")
        action, keep = request.form.get("action", ""), request.form.get("keep_qid", "")
        group = groups.get((prop, value))
        if group is None or action not in ACTIONS:
            abort(400)
        if action == "keep" and keep not in group["qids"]:
            abort(400)
        if action != "keep":
            keep = ""
        row = {"prop": prop, "value": value, "reviewer": user, "action": action, "keep_qid": keep,
               "note": request.form.get("note", "").strip()[:2000], "ts": datetime.now(timezone.utc).replace(tzinfo=None)}
        with engine.begin() as conn:
            conn.execute(votes.delete().where((votes.c.prop == prop) & (votes.c.value == value)
                                              & (votes.c.reviewer == user)))
            conn.execute(votes.insert().values(**row))
        flash(f"Saved {action} for {value}")
        return redirect(request.referrer or url_for("review"))

    # ---- exports -----------------------------------------------------------------------------
    def accepted():
        out = []
        for key, gv in all_votes().items():
            status, decision = group_status(gv)
            if status == "accepted" and key in groups:
                out.append((groups[key], decision))
        return sorted(out, key=lambda x: (x[0]["prop"], x[0]["value"]))

    @app.get("/export/quickstatements.txt")
    def export_quickstatements():
        require_reviewer()
        lines = []
        for g, (action, keep) in accepted():
            if action == "keep":
                lines += [f'-{q}|{g["prop"]}|"{g["value"]}"' for q in g["qids"] if q != keep]
            elif action == "remove":
                lines += [f'-{q}|{g["prop"]}|"{g["value"]}"' for q in g["qids"]]
        return Response("\n".join(lines) + ("\n" if lines else ""), mimetype="text/plain")

    @app.get("/export/decisions.csv")
    def export_decisions():
        """Accepted decisions in the pipeline's decisions.csv format (prop,value,action,keep_qid,note)."""
        require_reviewer()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["prop", "value", "action", "keep_qid", "note"])
        for g, (action, keep) in accepted():
            w.writerow([g["prop"], g["value"], action, keep, "accepted by 2 reviewers"])
        return Response(buf.getvalue(), mimetype="text/csv")

    return app


app = create_app() if os.environ.get("FLASK_APP_AUTOCREATE", "1") == "1" else None
