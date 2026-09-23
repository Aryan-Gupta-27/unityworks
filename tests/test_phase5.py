import sqlite3
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urlparse

import pytest

from app import create_app
from app.extensions import db
from app.models import Activity, Event, FileItem, Notification, Project, ProjectInvite, Task, User
from scripts.backup import backup, orphans, restore
from tests.conftest import register


def _soon(hours=8):
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=hours)


def test_production_refuses_default_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("UNITYWORKS_SEED", "0")
    with pytest.raises(RuntimeError):
        create_app("production")


def test_backup_round_trip(tmp_path):
    instance = tmp_path / "instance"
    files = instance / "uploads" / "files"
    files.mkdir(parents=True)
    (files / "keep.txt").write_text("keep")
    (files / "loose.txt").write_text("loose")
    conn = sqlite3.connect(instance / "unityworks.db")
    conn.execute("CREATE TABLE files (stored_name TEXT)")
    conn.execute("INSERT INTO files (stored_name) VALUES ('keep.txt')")
    conn.commit()
    conn.close()

    target = backup(instance, tmp_path / "backups")
    assert (target / "unityworks.db").exists()
    assert (target / "uploads" / "files" / "keep.txt").read_text() == "keep"
    restored = restore(target, tmp_path / "restored")
    assert (restored / "unityworks.db").exists()
    assert orphans(instance) == ["loose.txt"]
    with pytest.raises(FileExistsError):
        restore(target, tmp_path / "restored")


def test_student_journey(app):
    owner = app.test_client()
    mate = app.test_client()
    stranger = app.test_client()
    register(owner, username="aarav", email="aarav@example.com", name="Aarav Shah")
    register(mate, username="mira", email="mira@example.com", name="Mira Chen")
    register(stranger, username="leo", email="leo@example.com", name="Leo Mensah")

    owner.post(
        "/profile/edit",
        data={"bio": "Quiet labs.", "skills": "Flask", "college": "Unity College", "interests": "Maps"},
    )
    mate.post(
        "/profile/edit",
        data={"bio": "Writes the notes.", "skills": "Writing", "college": "Unity College", "interests": "Maps"},
    )
    found = owner.get("/discover?skill=Writing")
    assert b"Mira Chen" in found.data

    owner.post(
        "/communities/new",
        data={
            "kind": "community",
            "name": "Night Lab",
            "description": "After-hours study room.",
            "category": "Academics",
            "visibility": "public",
        },
    )
    joined = mate.post("/communities/night-lab/join", follow_redirects=True)
    assert joined.status_code == 200
    assert b"Night Lab" in joined.data

    owner.post(
        "/communities/new",
        data={
            "kind": "community",
            "name": "Closed Stack",
            "description": "Private room.",
            "category": "Other",
            "visibility": "private",
        },
    )
    hidden = stranger.get("/search?q=Closed+Stack&type=communities")
    assert b"No matches" in hidden.data
    assert b"/communities/closed-stack" not in hidden.data

    created = owner.post(
        "/projects/new",
        data={
            "name": "Lab Hours Board",
            "description": "A board of open labs.",
            "category": "Web Development",
            "status": "Active",
            "visibility": "private",
        },
        follow_redirects=True,
    )
    assert b"Lab Hours Board" in created.data
    with app.app_context():
        slug = Project.query.filter_by(name="Lab Hours Board").one().slug
        mira_id = User.query.filter_by(username="mira").one().id
        assert Activity.query.filter_by(area="project").count() >= 1

    empty = owner.post(
        "/projects/new",
        data={"name": "", "description": "", "category": "Other", "status": "Planning", "visibility": "public"},
    )
    assert b"required" in empty.data

    owner.post(f"/projects/{slug}/invite", data={"username": "mira", "role": "contributor"})
    with app.app_context():
        invite_id = ProjectInvite.query.filter_by(status="pending").one().id
    mate.post(f"/project-invites/{invite_id}/respond", data={"status": "accepted"})

    deadline = _soon(8).strftime("%Y-%m-%d")
    owner.post(
        f"/projects/{slug}/tasks",
        data={
            "title": "Sketch the hours",
            "description": "Which labs stay open.",
            "assignee_id": mira_id,
            "priority": "High",
            "deadline": deadline,
            "status": "TODO",
        },
    )
    board = mate.get("/dashboard")
    assert b"Sketch the hours" in board.data
    assert b"Pending tasks" in board.data
    notes = mate.get("/notifications")
    assert b"Deadline" in notes.data

    owner.post(
        f"/projects/{slug}/files",
        data={"file": (BytesIO(b"hours"), "hours.txt"), "folder": "Documents"},
        content_type="multipart/form-data",
    )
    owner.post(
        f"/projects/{slug}/notes",
        data={"title": "Friday lab", "body": "The small lab stays open."},
    )
    discussed = mate.post(
        f"/projects/{slug}/discussions",
        data={"kind": "update", "title": "Hours sketched", "body": "Table is in the files tab."},
        follow_redirects=True,
    )
    assert b"Hours sketched" in discussed.data
    with app.app_context():
        assert Notification.query.filter_by(kind="project_comment").count() >= 1
        task_id = Task.query.filter_by(title="Sketch the hours").one().id
        file_id = FileItem.query.filter_by(original_name="hours.txt").one().id

    mate.post(f"/projects/{slug}/tasks/{task_id}/status", data={"status": "DONE"})
    owner.post(
        f"/projects/{slug}/settings",
        data={
            "name": "Lab Hours Board",
            "description": "A board of open labs.",
            "category": "Web Development",
            "status": "Completed",
            "visibility": "public",
            "technologies": "Flask",
        },
    )
    owner.post(f"/projects/{slug}/publish")
    showcase = mate.get("/showcase")
    assert b"Lab Hours Board" in showcase.data
    found_project = mate.get("/search?q=Lab+Hours&type=projects")
    assert b"Lab Hours Board" in found_project.data
    activity = owner.get("/activity?area=project")
    assert b"project" in activity.data
    assert stranger.get(f"/projects/{slug}/files/{file_id}/download").status_code == 403

    when = _soon(20).strftime("%Y-%m-%dT%H:%M")
    owner.post(
        "/events",
        data={
            "title": "Night Lab Meetup",
            "starts_at": when,
            "category": "Meetup",
            "location": "Hall",
            "description": "Bring a notebook.",
            "registration_link": "https://example.com/night",
        },
    )
    events = mate.get("/search?q=Night+Lab+Meetup&type=events")
    assert b"Night Lab Meetup" in events.data
    bad = owner.post(
        "/events",
        data={
            "title": "Bad link night",
            "starts_at": when,
            "category": "Event",
            "registration_link": "javascript:alert(1)",
            "location": "Hall",
            "description": "no",
        },
    )
    assert b"http://" in bad.data
    with app.app_context():
        assert Event.query.filter_by(title="Bad link night").count() == 0

    mate.post("/notifications/preferences", data={"mute": "messages"})
    started = owner.post("/messages/start", data={"username": "mira"})
    thread = started.headers["Location"]
    owner.post(f"{thread}/send", data={"body": "hello from the lab"})
    with app.app_context():
        mira = User.query.filter_by(username="mira").one()
        assert "messages" in mira.muted_set
        assert Notification.query.filter_by(user_id=mira.id, kind="new_message").count() == 0

    rejected = owner.post(
        "/files/upload",
        data={"file": (BytesIO(b"MZ"), "virus.exe")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"not allowed" in rejected.data
    assert owner.get("/questions/99999").status_code == 404
    assert owner.get("/admin").status_code == 403
    owner.post("/logout")
    duplicate = owner.post(
        "/register",
        data={
            "name": "Other Aarav",
            "username": "aarav",
            "email": "other@example.com",
            "password": "Student#2026",
            "confirm": "Student#2026",
        },
    )
    assert b"already taken" in duplicate.data


def test_file_edges(app):
    client = app.test_client()
    register(client, username="aarav", email="aarav@example.com", name="Aarav Shah")
    uploaded = client.post(
        "/files/upload",
        data={"file": (BytesIO(b"notes"), "notes.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"notes.txt" in uploaded.data
    with app.app_context():
        item = FileItem.query.filter_by(original_name="notes.txt").one()
        file_id = item.id
        item.stored_name = "../secret.txt"
        db.session.commit()
    assert client.get(f"/files/{file_id}/download").status_code == 404
    with app.app_context():
        FileItem.query.get(file_id).stored_name = "safe.txt"
        db.session.commit()
    client.post(f"/files/{file_id}/delete")
    assert client.get(f"/files/{file_id}/download").status_code == 404

    app.config["MAX_CONTENT_LENGTH"] = 64
    oversized = client.post(
        "/files/upload",
        data={"file": (BytesIO(b"x" * 200), "big.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"too large" in oversized.data.lower()
