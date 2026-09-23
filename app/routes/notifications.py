from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Notification
from app.services import safe_next

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications")
@login_required
def index():
    filt = request.args.get("filter", "all")
    if filt not in {"all", "unread", "read"}:
        filt = "all"
    query = Notification.query.filter_by(user_id=current_user.id)
    if filt == "unread":
        query = query.filter_by(is_read=False)
    elif filt == "read":
        query = query.filter_by(is_read=True)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Notification.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    counts = {
        "all": Notification.query.filter_by(user_id=current_user.id).count(),
        "unread": Notification.query.filter_by(user_id=current_user.id, is_read=False).count(),
        "read": Notification.query.filter_by(user_id=current_user.id, is_read=True).count(),
    }
    return render_template("notifications/list.html", pagination=pagination, filt=filt, counts=counts)


@notifications_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("notifications.index"))


@notifications_bp.route("/notifications/<int:nid>/read", methods=["POST"])
@login_required
def read_one(nid):
    item = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    item.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.index"))


@notifications_bp.route("/notifications/<int:nid>/open")
@login_required
def open_notification(nid):
    item = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    item.is_read = True
    db.session.commit()
    return redirect(safe_next(item.link) or url_for("notifications.index"))
