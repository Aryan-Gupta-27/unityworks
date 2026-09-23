from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Conversation, ConversationParticipant, Message, User, utcnow
from app.services import (
    contains,
    conversation_unread,
    get_or_create_dm,
    mark_conversation_read,
    notify,
    participant_of,
    render_simple,
    unread_message_count,
)
from app.validators import clip

messages_bp = Blueprint("messages", __name__)


def _inbox_context(active_id=None):
    parts = (
        ConversationParticipant.query.filter_by(user_id=current_user.id)
        .join(Conversation)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    q = (request.args.get("q") or "").strip()
    rows = []
    for part in parts:
        last = (
            Message.query.filter_by(conversation_id=part.conversation_id, is_deleted=False)
            .order_by(Message.created_at.desc())
            .first()
        )
        if q:
            hay = part.conversation.title_for(current_user)
            body = last.body if last else ""
            if q.lower() not in hay.lower() and q.lower() not in body.lower():
                matched = Message.query.filter(
                    Message.conversation_id == part.conversation_id,
                    contains(Message.body, q),
                ).first()
                if not matched:
                    continue
        rows.append(
            {
                "conversation": part.conversation,
                "last": last,
                "unread": conversation_unread(part, current_user),
            }
        )
    return rows, q


@messages_bp.route("/messages")
@login_required
def inbox():
    rows, q = _inbox_context()
    return render_template("messages/inbox.html", rows=rows, q=q, active=None, messages=[])


@messages_bp.route("/messages/start", methods=["POST"])
@login_required
def start():
    username = (request.form.get("username") or "").strip().lower()
    user_id = request.form.get("user_id", type=int)
    other = None
    if user_id:
        other = db.session.get(User, user_id)
    elif username:
        other = User.query.filter_by(username=username).first()
    if not other or other.status != "active":
        flash("Couldn't find that student.", "error")
        return redirect(url_for("messages.inbox"))
    if other.id == current_user.id:
        flash("You can't message yourself.", "error")
        return redirect(url_for("messages.inbox"))
    conv = get_or_create_dm(current_user, other)
    db.session.commit()
    return redirect(url_for("messages.thread", conversation_id=conv.id))


@messages_bp.route("/messages/group", methods=["POST"])
@login_required
def create_group():
    title, title_error = clip(request.form.get("title"), 80, required=True, label="Title")
    raw = request.form.get("usernames") or ""
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    if title_error or len(names) < 1:
        flash(title_error or "Add at least one username.", "error")
        return redirect(url_for("messages.inbox"))
    users = []
    for name in names:
        user = User.query.filter_by(username=name, status="active").first()
        if not user or user.id == current_user.id:
            flash(f"No active student named {name}.", "error")
            return redirect(url_for("messages.inbox"))
        users.append(user)
    conv = Conversation(title=title, is_group=True, updated_at=utcnow())
    db.session.add(conv)
    db.session.flush()
    db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=current_user.id, last_read_at=utcnow()))
    for user in users:
        db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=user.id))
        notify(
            user.id,
            "new_message",
            f"{current_user.name} added you to {title}",
            "Group conversation",
            url_for("messages.thread", conversation_id=conv.id),
            actor_id=current_user.id,
        )
    db.session.commit()
    flash("Group conversation created.", "success")
    return redirect(url_for("messages.thread", conversation_id=conv.id))


@messages_bp.route("/messages/<int:conversation_id>")
@login_required
def thread(conversation_id):
    conv = db.session.get(Conversation, conversation_id) or abort(404)
    if not participant_of(current_user, conv):
        abort(403)
    before = request.args.get("before", type=int)
    query = Message.query.filter_by(conversation_id=conv.id)
    if before:
        query = query.filter(Message.id < before)
    messages = query.order_by(Message.created_at.desc()).limit(50).all()
    messages.reverse()
    mark_conversation_read(conv, current_user)
    db.session.commit()
    rows, q = _inbox_context(conv.id)
    return render_template(
        "messages/thread.html",
        rows=rows,
        q=q,
        active=conv,
        messages=messages,
        has_earlier=bool(messages) and Message.query.filter(
            Message.conversation_id == conv.id, Message.id < messages[0].id
        ).count() > 0,
    )


@messages_bp.route("/messages/<int:conversation_id>/send", methods=["POST"])
@login_required
def send(conversation_id):
    conv = db.session.get(Conversation, conversation_id) or abort(404)
    if not participant_of(current_user, conv):
        abort(403)
    body, body_error = clip(request.form.get("body"), 2000, required=True, label="Message")
    if body_error:
        flash(body_error, "error")
        return redirect(url_for("messages.thread", conversation_id=conv.id))
    msg = Message(conversation_id=conv.id, sender_id=current_user.id, body=body)
    db.session.add(msg)
    conv.updated_at = utcnow()
    mark_conversation_read(conv, current_user)
    link = url_for("messages.thread", conversation_id=conv.id)
    for part in conv.participants:
        notify(
            part.user_id,
            "new_message",
            f"New message from {current_user.name}",
            body[:180],
            link,
            actor_id=current_user.id,
        )
    db.session.commit()
    return redirect(link)


@messages_bp.route("/messages/<int:conversation_id>/updates")
@login_required
def updates(conversation_id):
    conv = db.session.get(Conversation, conversation_id) or abort(404)
    if not participant_of(current_user, conv):
        abort(403)
    after = request.args.get("after", 0, type=int)
    messages = (
        Message.query.filter(Message.conversation_id == conv.id, Message.id > after)
        .order_by(Message.created_at.asc())
        .limit(50)
        .all()
    )
    if request.args.get("mark") == "1":
        mark_conversation_read(conv, current_user)
        db.session.commit()
    payload = []
    for msg in messages:
        payload.append(
            {
                "id": msg.id,
                "html": "This message was deleted." if msg.is_deleted else render_simple(msg.body),
                "mine": msg.sender_id == current_user.id,
                "sender": msg.sender.name if msg.sender else "Student",
                "created": msg.created_at.strftime("%d %b · %H:%M UTC"),
                "edited": bool(msg.edited_at),
                "deleted": msg.is_deleted,
            }
        )
    return jsonify(
        {
            "messages": payload,
            "unread_messages": unread_message_count(current_user),
        }
    )


@messages_bp.route("/messages/<int:conversation_id>/messages/<int:message_id>/edit", methods=["POST"])
@login_required
def edit_message(conversation_id, message_id):
    msg = Message.query.filter_by(id=message_id, conversation_id=conversation_id).first_or_404()
    if msg.sender_id != current_user.id or msg.is_deleted or not participant_of(current_user, msg.conversation):
        abort(403)
    body, body_error = clip(request.form.get("body"), 2000, required=True, label="Message")
    if body_error:
        flash(body_error, "error")
        return redirect(url_for("messages.thread", conversation_id=conversation_id))
    msg.body = body
    msg.edited_at = utcnow()
    db.session.commit()
    flash("Message updated.", "success")
    return redirect(url_for("messages.thread", conversation_id=conversation_id))


@messages_bp.route("/messages/<int:conversation_id>/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_message(conversation_id, message_id):
    msg = Message.query.filter_by(id=message_id, conversation_id=conversation_id).first_or_404()
    if msg.sender_id != current_user.id or not participant_of(current_user, msg.conversation):
        abort(403)
    msg.is_deleted = True
    msg.body = ""
    db.session.commit()
    flash("Message deleted.", "success")
    return redirect(url_for("messages.thread", conversation_id=conversation_id))
