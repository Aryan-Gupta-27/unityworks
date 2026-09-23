# Operations

UnityWorks is one Flask application, one SQLite database, and one uploads folder. Do not add a second database for normal use.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000. The development server binds `0.0.0.0:5000` and does not enable the debugger unless `FLASK_DEBUG=1`.

Demo accounts are created only when the database is empty and `UNITYWORKS_SEED` is not `0`. They are for the local demo. Do not reuse those passwords on a public host.

## Architecture

- `app/models.py` holds the tables. Roles are checked in route handlers, not only in templates.
- `app/routes/` is the HTTP surface: auth, dashboard, profile, communities, messages, workspace, search, notifications, admin.
- `app/services.py` is shared behavior: notifications, activity, uploads, permissions.
- `app/schema.py` adds missing columns to an existing SQLite file. `create_all()` does not do that.
- Templates share the glass stylesheet in `app/static/css/main.css`.

Activity has one model. The `area` column is `project`, `community`, `academic`, `portfolio`, or `system`. Notifications have a category derived from `kind`, plus a mute list on the user.

## Environment

| Variable | Purpose |
| --- | --- |
| `UNITYWORKS_CONFIG` | `development`, `production`, or `testing` |
| `SECRET_KEY` | Required in production. The development default is refused. |
| `DATABASE_URL` | Optional. Unset uses `instance/unityworks.db`. |
| `UNITYWORKS_SEED` | `0` skips demo seed and enrichment. |
| `SESSION_COOKIE_SECURE` | Production defaults to `1`. Set `0` only for local HTTP. |
| `BEHIND_PROXY` | `1` trusts one proxy hop for HTTPS and host. |
| `PORT` | Development server port. Default `5000`. |
| `FLASK_DEBUG` | `1` turns the development debugger on. Leave it off in production. |

## Database and files

The application database is `instance/unityworks.db`. Uploads live in `instance/uploads/avatars` and `instance/uploads/files`. Stored names are random. Download routes reject names that contain a path.

Allowed upload extensions and the 16 MB limit are enforced on the server. Deleting a file or academic resource removes the stored file. `python scripts/backup.py orphans` lists files that no row references. It does not delete them.

Schema changes for an existing file run on startup through `upgrade_schema()`. Do not call the SQLite inspector in the middle of those uncommitted writes.

## Deploy

```bash
export UNITYWORKS_CONFIG=production
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export UNITYWORKS_SEED=0
export SESSION_COOKIE_SECURE=1
export BEHIND_PROXY=1
gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
```

`wsgi.py` loads the production config. Production logs to `instance/logs/unityworks.log`. Put TLS in front of gunicorn. Do not run `python run.py` as the public server.

## Tests and git

```bash
python -m pytest
```

Tests use an in-memory database and do not touch `instance/unityworks.db`.

GitHub Actions runs the same command from `.github/workflows/test.yml` on push and pull request. Keep `main` deployable. Use a short-lived branch for a change, open a pull request, and merge after the test job is green. Do not commit `.env`, the live database, or uploads.

## Admin

`/admin` requires an active user whose role is `admin`. The seeded admin exists only when seeding is enabled. Admins can deactivate accounts. Deactivated users are signed out on the next request.

## Backup and restore

Backup copies the database with SQLite's backup API and copies `instance/uploads`. It does not delete the live files.

```bash
python scripts/backup.py backup --instance instance --dest backups
python scripts/backup.py orphans --instance instance
python scripts/backup.py restore --from backups/20260923-170000 --dest /tmp/unityworks-restore
```

Restore refuses to overwrite an existing destination database or uploads folder. To replace a live database, stop the app, move the current `instance/` aside, restore into an empty directory, then point the app at that directory. Do not delete the live demo database as part of a routine backup.
