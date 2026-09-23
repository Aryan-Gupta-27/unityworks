from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constants import EXPERIENCE_LEVELS
from app.models import User
from app.services import contains

discover_bp = Blueprint("discover", __name__)


@discover_bp.route("/discover")
@login_required
def index():
    skill = (request.args.get("skill") or "").strip()
    interest = (request.args.get("interest") or "").strip()
    college = (request.args.get("college") or "").strip()
    experience = (request.args.get("experience") or "").strip()
    q = (request.args.get("q") or "").strip()
    query = User.query.filter(User.status == "active", User.id != current_user.id)
    if q:
        query = query.filter(contains(User.name, q) | contains(User.username, q) | contains(User.headline, q))
    if skill:
        query = query.filter(contains(User.skills, skill))
    if interest:
        query = query.filter(contains(User.interests, interest))
    if college:
        query = query.filter(contains(User.college, college))
    if experience in EXPERIENCE_LEVELS:
        query = query.filter_by(experience=experience)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(User.name.asc()).paginate(page=page, per_page=12, error_out=False)
    colleges = [
        row[0]
        for row in User.query.with_entities(User.college)
        .filter(User.college != "", User.status == "active")
        .distinct()
        .order_by(User.college.asc())
        .limit(12)
        .all()
    ]
    return render_template(
        "discover/students.html",
        pagination=pagination,
        skill=skill,
        interest=interest,
        college=college,
        experience=experience,
        q=q,
        levels=EXPERIENCE_LEVELS,
        colleges=colleges,
    )


@discover_bp.route("/find-teammates")
@login_required
def teammates():
    return redirect(url_for("discover.index", **request.args))
