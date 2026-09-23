from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import (
    Activity,
    Community,
    CommunityInvitation,
    CommunityMember,
    ConversationParticipant,
    Message,
    Notification,
    Project,
    ProjectMember,
)
from app.services import conversation_unread

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
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(4)
        .all()
    )
    return render_template(
        "dashboard/index.html",
        community_count=community_count,
        group_count=group_count,
        group_invites=group_invites,
        all_invites=all_invites,
        recent_messages=recent_messages,
        unread_by_conv=unread_by_conv,
        activity=activity,
        projects=projects,
        communities=communities,
        notifications=notifications,
    )
