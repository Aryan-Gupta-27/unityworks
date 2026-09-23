import html
import os
import re
import uuid
from datetime import datetime, timedelta

from flask import current_app, url_for
from markupsafe import Markup
from werkzeug.utils import secure_filename

from app.constants import ALLOWED_FILE_EXT, FILE_FOLDERS, NOTIFY_CATEGORIES, RESERVED_SLUGS
from app.extensions import db
from app.models import (
    AcademicResource,
    Achievement,
    Activity,
    Answer,
    CommunityMember,
    Conversation,
    ConversationParticipant,
    FileItem,
    Message,
    Note,
    Notification,
    Project,
    ProjectMember,
    Reaction,
    Task,
    User,
    Event,
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


def activity_area(link="", project_id=None):
    path = link or ""
    if project_id or path.startswith("/projects"):
        return "project"
    if path.startswith(("/communities", "/groups", "/clubs")):
        return "community"
    if path.startswith(("/academics", "/questions")):
        return "academic"
    if path.startswith(("/profile", "/showcase", "/u/")):
        return "portfolio"
    return "system"


def notify(user_id, kind, title, body="", link="", actor_id=None):
    if not user_id or user_id == actor_id:
        return None
    user = db.session.get(User, user_id)
    if not user:
        return None
    category = NOTIFY_CATEGORIES.get(kind, "system")
    if category in user.muted_set:
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


def log_activity(user_id, summary, link="", project_id=None):
    if not user_id:
        return None
    path = (link or "")[:240]
    item = Activity(
        user_id=user_id,
        summary=summary[:240],
        link=path,
        project_id=project_id,
        area=activity_area(path, project_id),
    )
    db.session.add(item)
    return item


def remind_due(user):
    """Create one reminder per upcoming task or event. Skips muted categories."""
    if not user:
        return
    soon = utcnow() + timedelta(days=2)
    if "tasks" not in user.muted_set:
        tasks = (
            Task.query.filter(
                Task.assignee_id == user.id,
                Task.status != "DONE",
                Task.deadline.isnot(None),
                Task.deadline <= soon,
            )
            .all()
        )
        for task in tasks:
            if not task.project:
                continue
            link = f"/projects/{task.project.slug}/tasks"
            body = task.title[:300]
            exists = Notification.query.filter_by(
                user_id=user.id, kind="task_deadline", link=link, body=body
            ).first()
            if exists:
                continue
            db.session.add(
                Notification(
                    user_id=user.id,
                    kind="task_deadline",
                    title=f"Deadline in {task.project.name}"[:140],
                    body=body,
                    link=link[:240],
                )
            )
    if "events" not in user.muted_set:
        events = Event.query.filter(
            Event.creator_id == user.id,
            Event.starts_at >= utcnow(),
            Event.starts_at <= soon,
        ).all()
        for event in events:
            body = event.title[:300]
            exists = Notification.query.filter_by(
                user_id=user.id, kind="event_reminder", link="/events", body=body
            ).first()
            if exists:
                continue
            db.session.add(
                Notification(
                    user_id=user.id,
                    kind="event_reminder",
                    title="Upcoming event",
                    body=body,
                    link="/events",
                )
            )


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


def project_membership(user, project):
    if not user or not getattr(user, "is_authenticated", False) or not project:
        return None
    return ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()


def can_view_project(user, project, pending=None):
    if project_membership(user, project):
        return True
    if user and getattr(user, "is_authenticated", False) and user.is_admin:
        return True
    if pending:
        return True
    return bool(user and getattr(user, "is_authenticated", False) and project.visibility == "public")


def can_read_work(user, project):
    if project_membership(user, project):
        return True
    return bool(user and getattr(user, "is_authenticated", False) and user.is_admin)


def can_contribute(user, project):
    row = project_membership(user, project)
    return bool(row and row.role in {"owner", "manager", "contributor"})


def can_manage(user, project):
    row = project_membership(user, project)
    return bool(row and row.role in {"owner", "manager"})


def can_own(user, project):
    row = project_membership(user, project)
    return bool(row and row.role == "owner")


def can_edit_task(user, project, task):
    row = project_membership(user, project)
    if not row:
        return False
    if row.role in {"owner", "manager"}:
        return True
    if row.role != "contributor":
        return False
    return task.created_by == user.id or task.assignee_id == user.id


def can_delete_task(user, project, task):
    if can_manage(user, project):
        return True
    row = project_membership(user, project)
    return bool(row and row.role == "contributor" and task.created_by == user.id)


def can_edit_note(user, project, note):
    if can_manage(user, project):
        return True
    row = project_membership(user, project)
    return bool(row and row.role == "contributor" and note.user_id == user.id)


def can_edit_file(user, project, item):
    if can_manage(user, project):
        return True
    row = project_membership(user, project)
    return bool(row and row.role == "contributor" and item.owner_id == user.id)


def can_remove_member(actor, project, target):
    actor_row = project_membership(actor, project)
    if not actor_row or not target or target.user_id == actor.id:
        return False
    if actor_row.role == "owner":
        return target.role != "owner"
    if actor_row.role == "manager":
        return target.role in {"contributor", "viewer"}
    return False


def project_stats(project):
    tasks = list(project.tasks)
    now = utcnow()
    total = len(tasks)
    done = sum(1 for task in tasks if task.status == "DONE")
    overdue = sum(1 for task in tasks if task.deadline and task.deadline < now and task.status != "DONE")
    file_groups = (
        db.session.query(FileItem.group_key)
        .filter(FileItem.project_id == project.id, FileItem.group_key != "")
        .distinct()
        .count()
    )
    loose = FileItem.query.filter(FileItem.project_id == project.id, FileItem.group_key == "").count()
    return {
        "tasks": total,
        "completed": done,
        "pending": total - done,
        "overdue": overdue,
        "members": len(project.memberships),
        "files": file_groups + loose,
        "notes": Note.query.filter_by(project_id=project.id).count(),
        "completion": round(100 * done / total) if total else 0,
    }


def folder_for(filename, chosen=None):
    if chosen in FILE_FOLDERS:
        return chosen
    ext = os.path.splitext(filename or "")[1].lower()
    mapping = {
        ".pdf": "Documents",
        ".docx": "Documents",
        ".txt": "Documents",
        ".md": "Documents",
        ".png": "Images",
        ".jpg": "Images",
        ".jpeg": "Images",
        ".webp": "Images",
        ".gif": "Images",
        ".pptx": "Presentations",
        ".py": "Code",
        ".js": "Code",
        ".html": "Code",
        ".css": "Code",
        ".json": "Code",
        ".zip": "Resources",
        ".csv": "Resources",
        ".xlsx": "Resources",
    }
    return mapping.get(ext, "Other")


def store_upload(storage, owner_id, project_id=None, folder=None, group_key=None, version=1):
    if not storage or not storage.filename:
        return None, "Choose a file to upload."
    filename = secure_filename(storage.filename)
    if not filename:
        return None, "Choose a file with a usable name."
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_FILE_EXT:
        return None, "That file type is not allowed."
    stored = f"{uuid.uuid4().hex}{ext}"
    directory = current_app.config["FILE_FOLDER"]
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, stored)
    storage.save(path)
    item = FileItem(
        owner_id=owner_id,
        project_id=project_id,
        stored_name=stored,
        original_name=filename[:180],
        size=os.path.getsize(path),
        mime=storage.mimetype or "",
        folder=folder_for(filename, folder),
        group_key=group_key or uuid.uuid4().hex,
        version=version or 1,
    )
    return item, None


def safe_stored_name(name):
    if not name or not isinstance(name, str):
        return None
    if name != os.path.basename(name) or ".." in name or "/" in name or "\\" in name:
        return None
    return name


def remove_stored_file(stored_name):
    name = safe_stored_name(stored_name)
    if not name:
        return
    path = os.path.join(current_app.config["FILE_FOLDER"], name)
    if os.path.isfile(path):
        os.remove(path)


def save_file(storage):
    if not storage or not storage.filename:
        return None, "Choose a file to upload."
    filename = secure_filename(storage.filename)
    if not filename:
        return None, "Choose a file with a usable name."
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_FILE_EXT:
        return None, "That file type is not allowed."
    stored = f"{uuid.uuid4().hex}{ext}"
    directory = current_app.config["FILE_FOLDER"]
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, stored)
    storage.save(path)
    return {
        "stored_name": stored,
        "original_name": filename[:180],
        "size": os.path.getsize(path),
    }, None


def sync_achievements(user):
    """Record badges the student has already earned. Does not commit."""
    if not user or not getattr(user, "id", None):
        return []
    earned = set()
    if Project.query.filter_by(creator_id=user.id).first():
        earned.add("first_project")
    if ProjectMember.query.filter(ProjectMember.user_id == user.id, ProjectMember.role != "owner").first():
        earned.add("project_contributor")
    if CommunityMember.query.filter_by(user_id=user.id).first():
        earned.add("community_contributor")
    if Answer.query.filter_by(author_id=user.id, accepted=True).first():
        earned.add("helpful_answer")
    if AcademicResource.query.filter_by(author_id=user.id).first():
        earned.add("resource_contributor")
    if Task.query.filter_by(assignee_id=user.id, status="DONE").count() >= 10:
        earned.add("tasks_10")
    published = (
        Project.query.join(ProjectMember)
        .filter(ProjectMember.user_id == user.id, Project.published.is_(True))
        .first()
    )
    if user.bio and user.skills and (user.certifications or user.honors or published):
        earned.add("portfolio_builder")
    have = {row.code for row in Achievement.query.filter_by(user_id=user.id).all()}
    added = []
    for code in sorted(earned - have):
        row = Achievement(user_id=user.id, code=code)
        db.session.add(row)
        added.append(row)
    return added
