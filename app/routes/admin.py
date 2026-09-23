from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.decorators import admin_required
from app.extensions import db
from app.models import CommunityMember, User
from app.services import contains

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/", strict_slashes=False)
@admin_required
def index():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    role = (request.args.get("role") or "").strip()
    query = User.query
    if q:
        query = query.filter(
            contains(User.name, q) | contains(User.username, q) | contains(User.email, q)
        )
    if status in {"active", "inactive"}:
        query = query.filter_by(status=status)
    if role in {"student", "admin"}:
        query = query.filter_by(role=role)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    stats = {
        "users": User.query.count(),
        "active": User.query.filter_by(status="active").count(),
        "inactive": User.query.filter_by(status="inactive").count(),
        "admins": User.query.filter_by(role="admin").count(),
    }
    return render_template("admin/users.html", pagination=pagination, stats=stats, q=q, status=status, role=role)


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = db.session.get(User, user_id)
    if not user:
        from flask import abort
        abort(404)
    memberships = CommunityMember.query.filter_by(user_id=user.id).all()
    return render_template("admin/user_detail.html", user=user, memberships=memberships)


@admin_bp.route("/users/<int:user_id>/status", methods=["POST"])
@admin_required
def set_status(user_id):
    user = db.session.get(User, user_id)
    if not user:
        from flask import abort
        abort(404)
    status = request.form.get("status")
    if status not in {"active", "inactive"}:
        flash("Choose a valid account status.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))
    if user.id == current_user.id and status == "inactive":
        flash("You can't deactivate your own account.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))
    if user.role == "admin" and status == "inactive":
        others = User.query.filter(User.role == "admin", User.status == "active", User.id != user.id).count()
        if others == 0:
            flash("You can't deactivate the last active administrator.", "error")
            return redirect(url_for("admin.user_detail", user_id=user.id))
    user.status = status
    db.session.commit()
    flash(f"{user.name} is now {status}.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))
