# Review app (Toolforge)

Invited reviewers log in with their Wikimedia account, vote keep / leave / defer / remove per duplicate
group, and a group is accepted when two reviewers agree. `remove` means no item keeps the value: every
statement in the group is removal-proposed. The app never edits Wikidata; it exports
QuickStatements (`/export/quickstatements.txt`) and a `decisions.csv` (`/export/decisions.csv`).
Plan and decisions: `docs/INTERACTIVE_PLAN.md`. Status: first slice, works locally, not deployed.

## Run locally

```bash
.venv/bin/pip install -r toolforge/requirements.txt
.venv/bin/python scripts/export_groups.py          # writes toolforge/groups.json from the latest run
cd toolforge
DEV_LOGIN=1 ALLOWED_USERS=alice,bob ../.venv/bin/flask --app app run
# log in as a test user: http://127.0.0.1:5000/login?as=alice   (DEV_LOGIN is for local use only)
```

Votes go to `toolforge/review.db` (SQLite, git-ignored). Tests: `python -m unittest tests.test_toolforge`.

## Configuration

Environment variables (on Toolforge set with `toolforge envvars create NAME`; locally just export them):

| Key | Meaning |
|---|---|
| `SECRET_KEY` | Flask session key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `ALLOWED_USERS` | Reviewer allowlist: comma-separated Wikimedia usernames. |
| `CONSUMER_KEY`, `CONSUMER_SECRET` | OAuth consumer from meta.wikimedia.org (see below). |
| `DATABASE_URL` | Optional SQLAlchemy URL. Default: ToolsDB built from `TOOL_TOOLSDB_USER` / `TOOL_TOOLSDB_PASSWORD` (injected by Toolforge), else a local SQLite file. |
| `OAUTH_MWURI` | Optional. Default `https://meta.wikimedia.org/w/index.php`. |

A git-ignored `toolforge/config.toml` (same keys) also works for local use.

## Deploy checklist (Build Service route, from Wikitech)

Needs you (accounts and approvals cannot be scripted):
1. Wikimedia developer account, Phabricator link, Toolforge membership (requested 2026-11-19, waiting for approval; log out and in of Toolsadmin after approval), SSH key (done, `~/.ssh/toolforge_ed25519`).
2. Create the tool in Toolsadmin (for example `wordnet-review`) and **create its git repository there**; the Build Service needs a *public* repo and builds from its **root**, so the app lives in its own repo (`gitlab.wikimedia.org/toolforge-repos/<tool>`), not in this one.
3. Register the OAuth consumer at `Special:OAuthConsumerRegistration/propose` on meta.wikimedia.org:
   callback `https://<tool>.toolforge.org/oauth-callback`, grants "Basic rights" only (the app never edits).
   Testing with your own account works before the consumer is approved.

Then:
```
# laptop: copy app.py, templates/, groups.json, requirements.txt, Procfile into the tool repo; commit; push
ssh -i ~/.ssh/toolforge_ed25519 <shell-user>@login.toolforge.org
become <tool>
toolforge envvars create SECRET_KEY            # also ALLOWED_USERS, CONSUMER_KEY, CONSUMER_SECRET (hidden prompt)
toolforge build start https://gitlab.wikimedia.org/toolforge-repos/<tool>.git
toolforge build show                           # wait for "Status: ok"
toolforge webservice buildservice start --mount=none
```
ToolsDB: the database `<user>__reviews` (user = `TOOL_TOOLSDB_USER`) must be created once by hand
(`sql tools` shell, `CREATE DATABASE ...`); the app creates its table itself.
Updates: push, `toolforge build start` again, then restart the webservice (the docs do not spell this out).

## Not verified yet
- `login` / `oauth-callback` follow the Wikitech tutorial's `mwoauth` calls but have **not** been run against Wikimedia (no consumer yet).
- Python version: the Build Service reads `.python-version` (default used for now); the available versions are not listed on the pages read.
- ToolsDB via PyMySQL + SQLAlchemy has not been tried (local tests use SQLite).
- Exact `CREATE DATABASE` / `sql` shell steps and how a restart after a rebuild works.
- Refreshing `groups.json`: for now regenerate with `scripts/export_groups.py` and copy it into the tool repo.
