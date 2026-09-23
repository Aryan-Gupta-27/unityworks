import html
import re
from datetime import datetime

from flask import url_for
from markupsafe import Markup

from app.constants import RESERVED_SLUGS
from app.extensions import db
from app.models import (
    CommunityMember,
    Conversation,
    ConversationParticipant,
    Message,
    Notification,
    Activity,
    Reaction,
    utcnow,
)


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    slug = slug[:60].strip("-")
    return slug or "item"


def unique_slug(model, value, exclude_id=None):
    base = slugify(value)
    if base in RESERVED_SLUGS:
        base = f"{base}-space"
    slug = base
    n = 2
    while True:
        query = model.query.filter_by(slug=slug)
        if exclude_id:
            query = query.filter(model.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{base}-{n}"
        n += 1


def like_pattern(q):
    escaped = (q or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def contains(column, q):
    return column.ilike(like_pattern(q), escape="\\")


def safe_next(value):
    if not value or not isinstance(value, str):
        return None
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    return value


def render_simple(text):
    s = html.escape(text or "")
    s = re.sub(
        r"(https?://[^\s<]+)",
        r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
        s,
    )
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s.replace("\n", "<br>")


def rich(text):
    return Markup(render_simple(text))


def notify(user_id, kind, title, body="", link="", actor_id=None):
    if not user_id or user_id == actor_id:
        return None
    item = Notification(
        user_id=user_id,
        actor_id=actor_id,
        kind=kind,
        title=title[:140],
        body=(body or "")[:300],
        link=(link or "")[:240],
    )
    db.session.add(item)
    return item


def log_activity(user_id, summary, link=""):
    if not user_id:
        return None
    item = Activity(user_id=user_id, summary=summary[:240], link=(link or "")[:240])
    db.session.add(item)
    return item


def membership_of(user, community):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return CommunityMember.query.filter_by(user_id=user.id, community_id=community.id).first()


def can_view_community(user, community):
    if not community.is_private:
        return True
    if user and getattr(user, "is_authenticated", False) and user.is_admin:
        return True
    return membership_of(user, community) is not None


def can_participate(user, community):
    return membership_of(user, community) is not None


def can_moderate(user, community):
    member = membership_of(user, community)
    if member and member.role in {"owner", "moderator"}:
        return True
    return bool(user and getattr(user, "is_authenticated", False) and user.is_admin)


def can_edit_community(user, community):
    member = membership_of(user, community)
    if member and member.role == "owner":
        return True
    return bool(user and getattr(user, "is_authenticated", False) and user.is_admin)


def like_count(post):
    return Reaction.query.filter_by(post_id=post.id).count()


def user_liked(post, user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return (
        Reaction.query.filter_by(user_id=user.id, post_id=post.id).filter(Reaction.comment_id.is_(None)).first()
        is not None
    )


def get_or_create_dm(user_a, user_b):
    ids_a = {
        p.conversation_id
        for p in ConversationParticipant.query.filter_by(user_id=user_a.id).all()
    }
    ids_b = {
        p.conversation_id
        for p in ConversationParticipant.query.filter_by(user_id=user_b.id).all()
    }
    for cid in ids_a & ids_b:
        conv = db.session.get(Conversation, cid)
        if conv and not conv.is_group and len(conv.participants) == 2:
            return conv
    conv = Conversation(is_group=False, updated_at=utcnow())
    db.session.add(conv)
    db.session.flush()
    db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=user_a.id, last_read_at=utcnow()))
    db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=user_b.id))
    return conv


def unread_message_count(user):
    total = 0
    parts = ConversationParticipant.query.filter_by(user_id=user.id).all()
    for part in parts:
        query = Message.query.filter(
            Message.conversation_id == part.conversation_id,
            Message.sender_id != user.id,
            Message.is_deleted.is_(False),
        )
        if part.last_read_at:
            query = query.filter(Message.created_at > part.last_read_at)
        total += query.count()
    return total


def conversation_unread(part, user):
    query = Message.query.filter(
        Message.conversation_id == part.conversation_id,
        Message.sender_id != user.id,
        Message.is_deleted.is_(False),
    )
    if part.last_read_at:
        query = query.filter(Message.created_at > part.last_read_at)
    return query.count()


def mark_conversation_read(conversation, user):
    part = ConversationParticipant.query.filter_by(
        conversation_id=conversation.id, user_id=user.id
    ).first()
    if part:
        part.last_read_at = utcnow()
    return part


def participant_of(user, conversation):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return ConversationParticipant.query.filter_by(
        conversation_id=conversation.id, user_id=user.id
    ).first()


def format_dt(value):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%d %b · %H:%M UTC")


def format_ago(value):
    if not value:
        return ""
    delta = utcnow() - value
    seconds = int(delta.total_seconds())
    if seconds < 45:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    return format_dt(value)


def avatar_url(user):
    if not user or not user.avatar:
        return None
    if user.avatar.startswith("seed:"):
        return url_for("static", filename="img/avatars/" + user.avatar.split(":", 1)[1])
    return url_for("profile.avatar_file", filename=user.avatar)
