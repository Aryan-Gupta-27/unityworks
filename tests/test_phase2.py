from app.extensions import db
from app.models import Community, CommunityMember, Notification, User
from tests.conftest import login, make_user, register


def _two_students(app):
    register_id = None
    c1 = app.test_client()
    c2 = app.test_client()
    register(c1, username="mira", email="mira@example.com", name="Mira Chen")
    register(c2, username="leo", email="leo@example.com", name="Leo Mensah")
    return c1, c2


def test_create_join_leave_community(app):
    owner, other = _two_students(app)
    created = owner.post(
        "/communities/new",
        data={
            "name": "Robotics Lab",
            "description": "Build robots and share lab notes with the cohort.",
            "category": "Other",
            "kind": "community",
            "visibility": "public",
        },
        follow_redirects=True,
    )
    assert b"Robotics Lab" in created.data
    with app.app_context():
        community = Community.query.filter_by(name="Robotics Lab").first()
        slug = community.slug
        assert CommunityMember.query.filter_by(community_id=community.id).count() == 1
    joined = other.post(f"/communities/{slug}/join", follow_redirects=True)
    assert b"Welcome" in joined.data or b"Robotics Lab" in joined.data
    left = other.post(f"/communities/{slug}/leave", follow_redirects=True)
    assert left.status_code == 200
    with app.app_context():
        community = Community.query.filter_by(slug=slug).first()
        assert CommunityMember.query.filter_by(community_id=community.id).count() == 1


def test_community_permissions_and_discussion(app):
    owner, member = _two_students(app)
    owner.post(
        "/communities/new",
        data={
            "name": "Web Circle",
            "description": "A room for interface notes and critiques.",
            "category": "Web Development",
            "kind": "community",
            "visibility": "public",
        },
    )
    with app.app_context():
        slug = Community.query.filter_by(name="Web Circle").first().slug
        member_id = User.query.filter_by(username="leo").first().id
        owner_id = User.query.filter_by(username="mira").first().id
    member.post(f"/communities/{slug}/join")
    denied = member.post(
        f"/communities/{slug}/edit",
        data={"name": "Hijack", "description": "nope not allowed", "category": "Other", "visibility": "public"},
    )
    assert denied.status_code == 403
    outsider = app.test_client()
    register(outsider, username="kabir", email="kabir@example.com", name="Kabir Nair")
    blocked_post = outsider.post(f"/communities/{slug}/posts", data={"title": "Nope", "body": "Should not land."})
    assert blocked_post.status_code == 403
    posted = owner.post(
        f"/communities/{slug}/posts",
        data={"title": "Critique thread", "body": "Bring one screen and one question."},
        follow_redirects=False,
    )
    assert posted.status_code == 302
    with app.app_context():
        from app.models import Post
        post_id = Post.query.filter_by(title="Critique thread").first().id
    commented = member.post(f"/posts/{post_id}/comments", data={"body": "I will bring the first screen."}, follow_redirects=True)
    assert b"first screen" in commented.data
    with app.app_context():
        note = Notification.query.filter_by(kind="comment").first()
        assert note is not None
        assert note.is_read is False
    removed = member.post(f"/communities/{slug}/members/{owner_id}/remove")
    assert removed.status_code == 403
    cannot_delete = member.post(f"/posts/{post_id}/delete")
    assert cannot_delete.status_code == 403
    promoted = owner.post(
        f"/communities/{slug}/members/{member_id}/role",
        data={"role": "moderator"},
        follow_redirects=True,
    )
    assert promoted.status_code == 200
    deleted = member.post(f"/posts/{post_id}/delete", follow_redirects=True)
    assert deleted.status_code == 200


def test_messages_unread_and_search(app):
    a, b = _two_students(app)
    started = a.post("/messages/start", data={"username": "leo"}, follow_redirects=False)
    assert started.status_code == 302
    location = started.headers["Location"]
    conv_id = location.rstrip("/").split("/")[-1]
    a.post(f"/messages/{conv_id}/send", data={"body": "Are we still on for Thursday?"})
    inbox = b.get("/messages")
    assert b"Thursday" in inbox.data or b"unread" in inbox.data
    thread = b.get(f"/messages/{conv_id}")
    assert b"Thursday" in thread.data
    cleared = b.get("/messages")
    assert b'class="thread-link unread"' not in cleared.data
    found = a.get("/search?q=leo&type=users")
    assert b"Leo Mensah" in found.data
    community = a.post(
        "/communities/new",
        data={
            "name": "Photography Walk",
            "description": "Saturday frames and kind critique.",
            "category": "Photography",
            "kind": "community",
            "visibility": "public",
        },
    )
    searched = b.get("/search?q=Photography&type=communities")
    assert b"Photography Walk" in searched.data


def test_deactivated_user_blocked_from_social(app):
    a, b = _two_students(app)
    with app.app_context():
        user = User.query.filter_by(username="leo").first()
        user.status = "inactive"
        db.session.commit()
    response = a.post("/messages/start", data={"username": "leo"}, follow_redirects=True)
    assert b"find that student" in response.data or b"not available" in response.data
