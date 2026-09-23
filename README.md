# UnityWorks

A student workspace for accounts, profiles, communities, discussions, and messages. One Flask application, one SQLite database, one glass interface.

## Run

```bash
cd unityworks
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The server binds `0.0.0.0:5000`, so that address works on this machine.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Student | aarav@unityworks.app | Student#2026 |
| Admin | admin@unityworks.app | UnityAdmin#2026 |

Other seeded students (`mira`, `leo`, `sofia`, `kabir`) use the same student password.

## Tests

```bash
python -m pytest
```

Tests use an in-memory database. They do not touch `instance/unityworks.db`.

## Layout

```text
unityworks/
├── app/
│   ├── models.py          # users, communities, messages, notifications, projects
│   ├── routes/            # auth, dashboard, profile, admin, social, workspace
│   ├── templates/         # base, landing, app shell, feature pages
│   └── static/            # glass CSS, logo, hero
├── instance/unityworks.db # the only application database
├── tests/
├── config.py
└── run.py
```

Roles (`student`, `admin`) and community roles (`owner`, `moderator`, `member`) are checked on the server.
