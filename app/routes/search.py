from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import AcademicResource, Community, Project, Question, User
from app.services import contains

search_bp = Blueprint("search", __name__)


@search_bp.route("/search")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    kind = request.args.get("type", "all")
    if kind not in {"all", "users", "communities", "projects", "resources", "questions"}:
        kind = "all"
    results = {"users": [], "communities": [], "projects": [], "resources": [], "questions": []}
    if len(q) >= 1:
        if kind in {"all", "users"}:
            results["users"] = (
                User.query.filter(User.status == "active")
                .filter(
                    contains(User.name, q)
                    | contains(User.username, q)
                    | contains(User.skills, q)
                    | contains(User.interests, q)
                    | contains(User.college, q)
                    | contains(User.bio, q)
                )
                .order_by(User.name.asc())
                .limit(20)
                .all()
            )
        if kind in {"all", "communities"}:
            results["communities"] = (
                Community.query.filter(
                    contains(Community.name, q)
                    | contains(Community.description, q)
                    | contains(Community.category, q)
                )
                .order_by(Community.name.asc())
                .limit(20)
                .all()
            )
        if kind in {"all", "projects"}:
            results["projects"] = (
                Project.query.filter(contains(Project.name, q) | contains(Project.description, q))
                .order_by(Project.name.asc())
                .limit(20)
                .all()
            )
        if kind in {"all", "resources"}:
            results["resources"] = (
                AcademicResource.query.filter(
                    contains(AcademicResource.title, q)
                    | contains(AcademicResource.subject, q)
                    | contains(AcademicResource.description, q)
                )
                .order_by(AcademicResource.created_at.desc())
                .limit(20)
                .all()
            )
        if kind in {"all", "questions"}:
            results["questions"] = (
                Question.query.filter(
                    contains(Question.title, q) | contains(Question.body, q) | contains(Question.tags, q)
                )
                .order_by(Question.created_at.desc())
                .limit(20)
                .all()
            )
    total = sum(len(v) for v in results.values())
    return render_template("search/results.html", q=q, kind=kind, results=results, total=total)
