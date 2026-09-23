from io import BytesIO

from app.extensions import db
from app.models import FileItem, Idea, Notification, Project, ProjectInvite, ProjectMember, Task, User
from app.schema import upgrade_schema
from tests.conftest import register


def test_legacy_project_values_migrate(app):
    with app.app_context():
        user = User(name="Old Student", username="oldstu", email="old@example.com", role="student")
        user.set_password("Student#2026")
        db.session.add(user)
        db.session.flush()
        project = Project(name="Old Board", slug="old-board", creator_id=user.id, status="On hold")
        db.session.add(project)
        db.session.flush()
        db.session.add(ProjectMember(project_id=project.id, user_id=user.id, role="member"))
        db.session.add(Task(project_id=project.id, title="Old task", created_by=user.id, status="To do"))
        db.session.commit()
        upgrade_schema()
        assert Project.query.filter_by(slug="old-board").one().status == "Planning"
        assert ProjectMember.query.filter_by(project_id=project.id).one().role == "contributor"
        assert Task.query.filter_by(title="Old task").one().status == "TODO"


def test_project_collaboration_workflow(app):
    owner = app.test_client()
    mate = app.test_client()
    stranger = app.test_client()
    register(owner, username="aarav", email="aarav@example.com", name="Aarav Shah")
    register(mate, username="mira", email="mira@example.com", name="Mira Chen")
    register(stranger, username="leo", email="leo@example.com", name="Leo Mensah")

    created = owner.post(
        "/projects/new",
        data={
            "name": "Campus Map",
            "description": "A map of open labs after seven.",
            "category": "Web Development",
            "status": "Active",
            "visibility": "private",
        },
        follow_redirects=True,
    )
    assert created.status_code == 200
    assert b"Campus Map" in created.data
    assert b"Overview" in created.data
    assert b"Board" in created.data

    with app.app_context():
        project = Project.query.filter_by(name="Campus Map").one()
        slug = project.slug
        assert project.visibility == "private"
        assert ProjectMember.query.filter_by(project_id=project.id, role="owner").count() == 1

    blocked = stranger.get(f"/projects/{slug}")
    assert blocked.status_code == 403
    hidden = stranger.get("/search?q=Campus+Map&type=projects")
    assert b"No matches" in hidden.data

    owner.post(f"/projects/{slug}/invite", data={"username": "mira", "role": "contributor"})
    inbox = mate.get("/invitations")
    assert b"Campus Map" in inbox.data
    with app.app_context():
        invite_id = ProjectInvite.query.filter_by(status="pending").one().id
        mira_id = User.query.filter_by(username="mira").one().id
    accepted = mate.post(
        f"/project-invites/{invite_id}/respond",
        data={"status": "accepted"},
        follow_redirects=True,
    )
    assert b"Campus Map" in accepted.data
    with app.app_context():
        role = ProjectMember.query.filter_by(user_id=mira_id).one().role
        assert role == "contributor"

    owner.post(f"/projects/{slug}/invite", data={"username": "leo", "role": "viewer"})
    with app.app_context():
        viewer_invite = ProjectInvite.query.filter_by(status="pending").one().id
    stranger.post(f"/project-invites/{viewer_invite}/respond", data={"status": "accepted"})
    denied = stranger.post(f"/projects/{slug}/tasks", data={"title": "Should fail"})
    assert denied.status_code == 403

    made = owner.post(
        f"/projects/{slug}/tasks",
        data={
            "title": "Sketch the lab hours",
            "description": "Which labs stay open after 7.",
            "assignee_id": mira_id,
            "priority": "High",
            "deadline": "2026-10-01",
            "status": "TODO",
        },
        follow_redirects=True,
    )
    assert b"Sketch the lab hours" in made.data
    with app.app_context():
        task = Task.query.filter_by(title="Sketch the lab hours").one()
        task_id = task.id
        assert task.assignee_id == mira_id
        assert task.priority == "High"
        assert Notification.query.filter_by(kind="task_assignment", user_id=mira_id).first() is not None

    moved = mate.post(
        f"/projects/{slug}/tasks/{task_id}/status",
        data={"status": "DONE"},
        follow_redirects=True,
    )
    assert moved.status_code == 200
    with app.app_context():
        assert Task.query.get(task_id).status == "DONE"

    uploaded = owner.post(
        f"/projects/{slug}/files",
        data={"file": (BytesIO(b"lab hours v1"), "hours.txt"), "folder": "Documents"},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"hours.txt" in uploaded.data
    with app.app_context():
        item = FileItem.query.filter_by(original_name="hours.txt").one()
        file_id = item.id
        assert item.folder == "Documents"
        assert item.version == 1

    versioned = owner.post(
        f"/projects/{slug}/files/{file_id}/version",
        data={"file": (BytesIO(b"lab hours v2"), "hours-v2.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"v2" in versioned.data
    stranger_upload = stranger.post(
        f"/projects/{slug}/files",
        data={"file": (BytesIO(b"nope"), "nope.txt")},
        content_type="multipart/form-data",
    )
    assert stranger_upload.status_code == 403

    noted = owner.post(
        f"/projects/{slug}/notes",
        data={"title": "Open labs", "body": "The small lab stays open on Fridays."},
        follow_redirects=True,
    )
    assert b"Open labs" in noted.data
    found = owner.get(f"/projects/{slug}/notes?q=Fridays")
    assert b"Open labs" in found.data
    missed = owner.get(f"/projects/{slug}/notes?q=zzzz-no-match")
    assert b"Open labs" not in missed.data
    personal = owner.get("/notes")
    assert b"Open labs" not in personal.data

    discussed = mate.post(
        f"/projects/{slug}/discussions",
        data={"kind": "update", "title": "Hours sketched", "body": "Table is in the files tab."},
        follow_redirects=True,
    )
    assert b"Hours sketched" in discussed.data
    assert b"Update" in discussed.data

    owner.post(
        f"/projects/{slug}/settings",
        data={
            "name": "Campus Map",
            "description": "A map of open labs after seven.",
            "category": "Web Development",
            "status": "Completed",
            "visibility": "public",
        },
    )
    published = owner.post(f"/projects/{slug}/publish", follow_redirects=True)
    assert published.status_code == 200
    with app.app_context():
        saved = Project.query.filter_by(slug=slug).one()
        assert saved.status == "Completed"
        assert saved.published is True
    showcase = stranger.get("/showcase")
    assert b"Campus Map" in showcase.data
    public = stranger.get(f"/showcase/{slug}")
    assert public.status_code == 200
    assert b"Campus Map" in public.data

    with app.app_context():
        owner_id = User.query.filter_by(username="aarav").one().id
    assert stranger.post(f"/projects/{slug}/members/{owner_id}/remove").status_code == 403
    assert mate.post(f"/projects/{slug}/delete").status_code == 403


def test_idea_becomes_a_project(app):
    client = app.test_client()
    register(client, username="mira", email="mira@example.com", name="Mira Chen")
    client.post(
        "/ideas",
        data={
            "title": "Attendance tool",
            "description": "A phone check-in for club secretaries.",
            "skills_needed": "Flask",
        },
    )
    with app.app_context():
        idea_id = Idea.query.filter_by(title="Attendance tool").one().id
    started = client.post(f"/ideas/{idea_id}/start", follow_redirects=True)
    assert started.status_code == 200
    assert b"Attendance tool" in started.data
    assert b"Overview" in started.data
    with app.app_context():
        idea = Idea.query.filter_by(title="Attendance tool").one()
        project = Project.query.get(idea.project_id)
        assert project is not None
        assert project.visibility == "private"
        assert project.status == "Planning"


def test_reject_project_invite(app):
    owner = app.test_client()
    mate = app.test_client()
    register(owner, username="aarav", email="aarav@example.com", name="Aarav Shah")
    register(mate, username="mira", email="mira@example.com", name="Mira Chen")
    owner.post(
        "/projects/new",
        data={
            "name": "Quiet Build",
            "description": "A small private build.",
            "category": "Other",
            "status": "Planning",
            "visibility": "private",
        },
    )
    with app.app_context():
        slug = Project.query.filter_by(name="Quiet Build").one().slug
    owner.post(f"/projects/{slug}/invite", data={"username": "mira", "role": "manager"})
    with app.app_context():
        invite_id = ProjectInvite.query.filter_by(status="pending").one().id
    mate.post(f"/project-invites/{invite_id}/respond", data={"status": "declined"})
    with app.app_context():
        assert ProjectMember.query.count() == 1
        assert ProjectInvite.query.one().status == "declined"
