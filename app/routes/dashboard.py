from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    AcademicResource,
    Activity,
    Community,
    CommunityInvitation,
    CommunityMember,
    ConversationParticipant,
    Event,
    Message,
    Notification,
    Project,
    ProjectInvite,
    ProjectMember,
    Question,
    Task,
    utcnow,
)
from app.services import conversation_unread, remind_due

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    memberships = (
        CommunityMember.query.filter_by(user_id=current_user.id)
        .join(Community)
        .all()
    )
    community_count = sum(1 for m in memberships if m.community.kind == "community")
    group_count = sum(1 for m in memberships if m.community.kind == "group")
    group_invites = (
        CommunityInvitation.query.filter_by(invitee_id=current_user.id, status="pending", kind="invite")
        .join(Community)
        .filter(Community.kind == "group")
        .all()
    )
    all_invites = CommunityInvitation.query.filter_by(
        invitee_id=current_user.id, status="pending", kind="invite"
    ).all()
    project_invites = ProjectInvite.query.filter_by(invitee_id=current_user.id, status="pending").all()

    parts = ConversationParticipant.query.filter_by(user_id=current_user.id).all()
    conv_ids = [p.conversation_id for p in parts]
    recent_messages = []
    if conv_ids:
        recent_messages = (
            Message.query.filter(Message.conversation_id.in_(conv_ids), Message.is_deleted.is_(False))
            .order_by(Message.created_at.desc())
            .limit(4)
            .all()
        )
    unread_by_conv = {p.conversation_id: conversation_unread(p, current_user) for p in parts}

    activity = (
        Activity.query.filter_by(user_id=current_user.id)
        .order_by(Activity.created_at.desc())
        .limit(6)
        .all()
    )
    projects = (
        Project.query.join(ProjectMember)
        .filter(ProjectMember.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
        .limit(4)
        .all()
    )
    communities = (
        Community.query.join(CommunityMember)
        .filter(CommunityMember.user_id == current_user.id, Community.kind == "community")
        .order_by(Community.updated_at.desc())
        .limit(4)
        .all()
    )
    remind_due(current_user)
    db.session.commit()
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(4)
        .all()
    )
    pending_tasks = (
        Task.query.filter(Task.assignee_id == current_user.id, Task.status != "DONE")
        .order_by(Task.deadline.is_(None), Task.deadline.asc(), Task.created_at.desc())
        .limit(5)
        .all()
    )
    upcoming_events = (
        Event.query.filter(Event.starts_at >= utcnow()).order_by(Event.starts_at.asc()).limit(4).all()
    )
    academic = (
        AcademicResource.query.filter_by(author_id=current_user.id)
        .order_by(AcademicResource.created_at.desc())
        .limit(4)
        .all()
    )
    questions = (
        Question.query.filter_by(author_id=current_user.id)
        .order_by(Question.created_at.desc())
        .limit(3)
        .all()
    )
    published = (
        Project.query.join(ProjectMember)
        .filter(ProjectMember.user_id == current_user.id, Project.published.is_(True))
        .order_by(Project.published_at.desc())
        .limit(3)
        .all()
    )
    return render_template(
        "dashboard/index.html",
        community_count=community_count,
        group_count=group_count,
        group_invites=group_invites,
        all_invites=all_invites,
        project_invites=project_invites,
        recent_messages=recent_messages,
        unread_by_conv=unread_by_conv,
        activity=activity,
        projects=projects,
        communities=communities,
        notifications=notifications,
        pending_tasks=pending_tasks,
        upcoming_events=upcoming_events,
        academic=academic,
        questions=questions,
        published=published,
    )
