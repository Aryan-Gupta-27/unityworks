from datetime import timedelta

from app.extensions import db
from app.models import User
from tests.conftest import login, make_user, register


def test_register_login_logout(client):
    response = register(client)
    assert response.status_code == 200
    assert b"Welcome back" in response.data or b"Dashboard" in response.data or b"Your day" in response.data
    page = client.get("/dashboard")
    assert page.status_code == 200
    assert b"Aarav" in page.data
    logged_out = client.post("/logout", follow_redirects=True)
    assert logged_out.status_code == 200
    assert b"signed out" in logged_out.data.lower() or b"Your Study Life" in logged_out.data


def test_invalid_login(client):
    register(client)
    client.post("/logout")
    response = login(client, "aarav@example.com", "wrong-password")
    assert b"match our records" in response.data
    assert client.get("/dashboard", follow_redirects=False).status_code == 302


def test_duplicate_email_and_username(client):
    register(client, username="aarav", email="aarav@example.com")
    client.post("/logout")
    email_clash = register(client, username="other", email="aarav@example.com")
    assert b"already exists" in email_clash.data
    name_clash = register(client, username="Aarav", email="new@example.com")
    assert b"already taken" in name_clash.data


def test_protected_route_redirects(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_unauthorized_admin_route(app, client):
    register(client)
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 403
    client.post("/logout")
    make_user(app, "adminuser", "admin@example.com", role="admin", password="UnityAdmin#2026")
    login(client, "adminuser", "UnityAdmin#2026")
    allowed = client.get("/admin")
    assert allowed.status_code == 200
    assert b"Accounts" in allowed.data


def test_profile_editing(client):
    register(client)
    response = client.post(
        "/profile/edit",
        data={
            "action": "profile",
            "headline": "Building quietly",
            "bio": "I like study groups that ship.",
            "skills": "Python, Flask",
            "education": "B.Tech CSE",
            "interests": "Research",
            "college": "Sangam Institute",
            "program": "CSE",
            "academic_year": "Year 3",
            "experience": "Intermediate",
        },
        follow_redirects=True,
    )
    assert b"Building quietly" in response.data
    assert b"Python" in response.data


def test_invalid_forms(client):
    response = client.post(
        "/register",
        data={"name": "A", "username": "ab", "email": "not-an-email", "password": "short", "confirm": "other"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"valid email" in response.data or b"at least" in response.data or b"Passwords" in response.data


def test_session_expiration(app, client):
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=1)
    register(client)
    with client.session_transaction() as sess:
        from datetime import datetime, timedelta as td
        sess["expires_at"] = (datetime.utcnow() - td(seconds=5)).isoformat()
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_deactivated_user_cannot_stay(app, client):
    register(client, username="sam", email="sam@example.com")
    with app.app_context():
        user = User.query.filter_by(username="sam").first()
        user.status = "inactive"
        db.session.commit()
    blocked = client.get("/dashboard", follow_redirects=True)
    assert b"deactivated" in blocked.data.lower()
    again = login(client, "sam@example.com")
    assert b"deactivated" in again.data.lower()
