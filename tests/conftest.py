import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture
def app():
    application = create_app("testing")
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def ctx(app):
    with app.app_context():
        yield


def register(client, username="aarav", email="aarav@example.com", password="Student#2026", name="Aarav Shah"):
    return client.post(
        "/register",
        data={
            "name": name,
            "username": username,
            "email": email,
            "password": password,
            "confirm": password,
        },
        follow_redirects=True,
    )


def login(client, identifier, password="Student#2026"):
    return client.post(
        "/login",
        data={"identifier": identifier, "password": password},
        follow_redirects=True,
    )


def make_user(app, username, email, role="student", password="Student#2026", status="active"):
    with app.app_context():
        user = User(name=username.title(), username=username, email=email, role=role, status=status)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id
