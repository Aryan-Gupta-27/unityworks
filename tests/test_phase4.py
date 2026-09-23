from io import BytesIO

from app.extensions import db
from app.models import (
    Achievement,
    Answer,
    Community,
    Event,
    Idea,
    IdeaInterest,
    Project,
    ProjectInvite,
    Question,
    User,
)
from tests.conftest import register


def test_academic_resource_question_and_achievement(app):
    student = app.test_client()
    register(student, username="aarav", email="aarav@example.com", name="Aarav Shah")
    uploaded = student.post(
        "/academics",
        data={
            "title": "Week 3 notes",
            "subject": "Programming",
            "kind": "Notes",
            "description": "Loops, then functions.",
            "tags": "week3, python",
            "link": "",
            "file": (BytesIO(b"for item in items: pass\n"), "notes.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert uploaded.status_code == 200
    assert b"Week 3 notes" in uploaded.data
    found = student.get("/search?q=week3&type=resources")
    assert b"Week 3 notes" in found.data
    page = student.get("/academics?q=python&subject=Programming")
    assert b"Week 3 notes" in page.data

    asked = student.post(
        "/questions/new",
        data={
            "title": "When is a list the wrong tool?",
            "body": "I keep reaching for a list when I want a lookup.",
            "subject": "Programming",
            "tags": "python",
        },
        follow_redirects=True,
    )
    assert b"When is a list the wrong tool?" in asked.data
    with app.app_context():
        question_id = Question.query.filter_by(title="When is a list the wrong tool?").one().id
    denied = student.post(f"/questions/{question_id}/answer", data={"body": "Use a dict when the key matters."}, follow_redirects=True)
    assert b"Use a dict" in denied.data
    with app.app_context():
        answer_id = Answer.query.filter_by(question_id=question_id).one().id
    assert student.post(f"/answers/{answer_id}/accept").status_code == 302
    with app.app_context():
        assert Answer.query.get(answer_id).accepted is False

    mate = app.test_client()
    register(mate, username="mira", email="mira@example.com", name="Mira Chen")
    answered = mate.post(
        f"/questions/{question_id}/answer",
        data={"body": "A dict is the lookup. A list is the order."},
        follow_redirects=True,
    )
    assert b"A dict is the lookup" in answered.data
    with app.app_context():
        mira_answer = Answer.query.filter(Answer.author_id != Answer.query.filter_by(question_id=question_id).first().author_id).order_by(Answer.id.desc()).first()
        # The second answer is Mira's.
        mira_answer = Answer.query.filter_by(question_id=question_id).order_by(Answer.id.desc()).first()
        answer_id = mira_answer.id
    assert student.post(f"/answers/{answer_id}/edit", data={"body": "hijack"}).status_code == 403
    edited = mate.post(
        f"/answers/{answer_id}/edit",
        data={"body": "A dict is the lookup. A list keeps order."},
        follow_redirects=True,
    )
    assert b"keeps order" in edited.data
    voted = student.post(f"/answers/{answer_id}/vote", data={"value": "up"}, follow_redirects=True)
    assert b"keeps order" in voted.data
    with app.app_context():
        assert Answer.query.get(answer_id).score == 1
    accepted = student.post(f"/answers/{answer_id}/accept", follow_redirects=True)
    assert b"Accepted" in accepted.data
    profile = mate.get("/profile/mira")
    assert b"Helpful Answer" in profile.data
    owner_profile = student.get("/profile/aarav")
    assert b"Resource Contributor" in owner_profile.data
    with app.app_context():
        assert Achievement.query.filter_by(code="helpful_answer").count() == 1


def test_portfolio_privacy_and_showcase(app):
    student = app.test_client()
    register(student, username="sofia", email="sofia@example.com", name="Sofia Alvarez")
    student.post(
        "/profile/edit",
        data={
            "action": "profile",
            "headline": "Prints the poster",
            "bio": "A private sentence about the studio.",
            "skills": "Figma, Print",
            "education": "B.A. Visual Communication",
            "college": "Harbour College",
            "experience": "Intermediate",
            "certifications": "Studio year 2",
            "honors": "Night market lead",
            "experience_note": "Club design lead",
            "mentor_role": "mentor",
            "profile_public": "1",
            "share_skills": "1",
            "share_projects": "1",
        },
        follow_redirects=True,
    )
    public = app.test_client().get("/u/sofia")
    assert public.status_code == 200
    assert b"Figma" in public.data
    assert b"private sentence" not in public.data
    assert b"Studio year 2" not in public.data
    hidden = app.test_client()
    register(hidden, username="leo", email="leo@example.com", name="Leo Mensah")
    hidden.post(
        "/profile/edit",
        data={
            "action": "profile",
            "bio": "Leo keeps this inside.",
            "skills": "C++",
            "college": "Linden",
            "profile_public": "",
        },
        follow_redirects=True,
    )
    closed = app.test_client().get("/u/leo")
    assert b"inside UnityWorks" in closed.data
    assert b"Leo keeps this inside" not in closed.data

    student.post(
        "/projects/new",
        data={
            "name": "Poster Set",
            "description": "A finished poster.",
            "category": "Design",
            "status": "Completed",
            "visibility": "public",
        },
    )
    with app.app_context():
        slug = Project.query.filter_by(name="Poster Set").one().slug
    student.post(
        f"/projects/{slug}/settings",
        data={
            "name": "Poster Set",
            "description": "A finished poster.",
            "category": "Design",
            "status": "Completed",
            "visibility": "public",
            "technologies": "Figma, Print",
            "repo_url": "https://example.com/poster",
            "demo_url": "https://example.com/poster-demo",
        },
    )
    student.post(f"/projects/{slug}/publish")
    showcase = app.test_client().get(f"/showcase/{slug}")
    assert b"Figma" in showcase.data
    assert b"Poster Set" in showcase.data
    assert b"example.com/poster" in showcase.data


def test_event_idea_and_club(app):
    owner = app.test_client()
    mate = app.test_client()
    register(owner, username="mira", email="mira@example.com", name="Mira Chen")
    register(mate, username="kabir", email="kabir@example.com", name="Kabir Nair")
    created = owner.post(
        "/events",
        data={
            "title": "Robotics workshop",
            "description": "Bring a battery.",
            "location": "Lab 2",
            "category": "Workshop",
            "registration_link": "https://example.com/robots",
            "starts_at": "2026-10-02T18:00",
        },
        follow_redirects=True,
    )
    assert b"Robotics workshop" in created.data
    assert b"Register" in created.data
    listed = owner.get("/events?category=Workshop")
    assert b"Robotics workshop" in listed.data
    with app.app_context():
        event = Event.query.filter_by(title="Robotics workshop").one()
        assert event.category == "Workshop"
        assert event.registration_link.startswith("https://")

    owner.post(
        "/ideas",
        data={
            "title": "Club attendance",
            "description": "A phone check-in for secretaries.",
            "skills_needed": "Flask",
        },
    )
    with app.app_context():
        idea_id = Idea.query.filter_by(title="Club attendance").one().id
    mate.post(f"/ideas/{idea_id}/interest")
    with app.app_context():
        assert IdeaInterest.query.filter_by(idea_id=idea_id).count() == 1
    started = owner.post(f"/ideas/{idea_id}/start", follow_redirects=True)
    assert b"Club attendance" in started.data
    inbox = mate.get("/invitations")
    assert b"Club attendance" in inbox.data
    with app.app_context():
        assert ProjectInvite.query.filter_by(status="pending").count() == 1

    club = owner.post(
        "/communities/new",
        data={
            "name": "Literary Club",
            "description": "A quiet room for reading and the magazine.",
            "category": "College Clubs",
            "kind": "club",
            "visibility": "public",
        },
        follow_redirects=True,
    )
    assert b"Literary Club" in club.data
    board = owner.get("/clubs")
    assert b"Literary Club" in board.data
    with app.app_context():
        assert Community.query.filter_by(name="Literary Club").one().kind == "club"

    mate.post(
        "/profile/edit",
        data={"action": "profile", "skills": "Statistics", "mentor_role": "mentee", "college": "Sangam"},
    )
    mentors = owner.get("/discover?mentor=mentee")
    assert b"Kabir" in mentors.data
