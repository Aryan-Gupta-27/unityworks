from flask import Blueprint, render_template

from app.models import Community

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def landing():
    communities = (
        Community.query.filter_by(visibility="public", kind="community")
        .order_by(Community.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template("landing.html", communities=communities)


@main_bp.route("/about")
def about():
    return render_template("about.html")
