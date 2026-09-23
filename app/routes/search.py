from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.constants import PROJECT_STATUSES, SEARCH_TYPES
from app.models import (
    AcademicResource,
    Community,
    CommunityMember,
    Event,
    Idea,
    Project,
    ProjectMember,
    Question,
    User,
)
from app.services import contains

search_bp = Blueprint("search", __name__)


def _date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None


@search_bp.route("/search")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    kind = request.args.get("type", "all")
    if kind not in SEARCH_TYPES:
        kind = "all"
    category = (request.args.get("category") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    skill = (request.args.get("skill") or "").strip()
    status = (request.args.get("status") or "").strip()
    after = _date(request.args.get("after"))
    filters = {
        "category": category,
        "subject": subject,
        "skill": skill,
        "status": status if status in PROJECT_STATUSES else "",
        "after": request.args.get("after") or "",
    }
    results = {
        "users": [],
        "communities": [],
        "projects": [],
        "resources": [],
        "questions": [],
        "events": [],
        "ideas": [],
    }
    wants = bool(q or category or subject or skill or filters["status"] or after)

    def dated(query, column):
        if after:
            return query.filter(column >= after)
        return query

    if wants and kind in {"all", "users"} and (q or skill or after):
        query = User.query.filter(User.status == "active")
        if q:
            query = query.filter(
                contains(User.name, q)
                | contains(User.username, q)
                | contains(User.skills, q)
                | contains(User.interests, q)
                | contains(User.college, q)
                | contains(User.bio, q)
            )
        if skill:
            query = query.filter(contains(User.skills, skill))
        results["users"] = dated(query, User.created_at).order_by(User.name.asc()).limit(20).all()

    if wants and kind in {"all", "communities"} and (q or category or after):
        query = Community.query
        if q:
            query = query.filter(
                contains(Community.name, q) | contains(Community.description, q) | contains(Community.category, q)
            )
        if category:
            query = query.filter(contains(Community.category, category))
        if not current_user.is_admin:
            mine = [row.community_id for row in CommunityMember.query.filter_by(user_id=current_user.id).all()]
            query = query.filter((Community.visibility == "public") | (Community.id.in_(mine or [0])))
        results["communities"] = dated(query, Community.created_at).order_by(Community.name.asc()).limit(20).all()

    if wants and kind in {"all", "projects"} and (q or category or skill or filters["status"] or after):
        mine = [row.project_id for row in ProjectMember.query.filter_by(user_id=current_user.id).all()]
        query = Project.query.filter(
            (Project.visibility == "public") | (Project.published.is_(True)) | (Project.id.in_(mine or [0]))
        )
        if q:
            query = query.filter(
                contains(Project.name, q)
                | contains(Project.description, q)
                | contains(Project.category, q)
                | contains(Project.technologies, q)
            )
        if category:
            query = query.filter(contains(Project.category, category))
        if skill:
            query = query.filter(contains(Project.technologies, skill))
        if filters["status"]:
            query = query.filter_by(status=filters["status"])
        results["projects"] = dated(query, Project.created_at).order_by(Project.name.asc()).limit(20).all()

    if wants and kind in {"all", "resources"} and (q or subject or after):
        query = AcademicResource.query
        if q:
            query = query.filter(
                contains(AcademicResource.title, q)
                | contains(AcademicResource.subject, q)
                | contains(AcademicResource.description, q)
                | contains(AcademicResource.tags, q)
            )
        if subject:
            query = query.filter(contains(AcademicResource.subject, subject))
        results["resources"] = dated(query, AcademicResource.created_at).order_by(AcademicResource.created_at.desc()).limit(20).all()

    if wants and kind in {"all", "questions"} and (q or subject or after):
        query = Question.query
        if q:
            query = query.filter(
                contains(Question.title, q)
                | contains(Question.body, q)
                | contains(Question.tags, q)
                | contains(Question.subject, q)
            )
        if subject:
            query = query.filter(contains(Question.subject, subject))
        results["questions"] = dated(query, Question.created_at).order_by(Question.created_at.desc()).limit(20).all()

    if wants and kind in {"all", "events"} and (q or category or after):
        query = Event.query
        if q:
            query = query.filter(
                contains(Event.title, q) | contains(Event.description, q) | contains(Event.location, q)
            )
        if category:
            query = query.filter(contains(Event.category, category))
        column = Event.starts_at if after else Event.created_at
        if after:
            query = query.filter(Event.starts_at >= after)
        results["events"] = query.order_by(column.asc()).limit(20).all()

    if wants and kind in {"all", "ideas"} and (q or skill or after):
        query = Idea.query
        if q:
            query = query.filter(contains(Idea.title, q) | contains(Idea.description, q) | contains(Idea.skills_needed, q))
        if skill:
            query = query.filter(contains(Idea.skills_needed, skill))
        results["ideas"] = dated(query, Idea.created_at).order_by(Idea.created_at.desc()).limit(20).all()

    total = sum(len(rows) for rows in results.values())
    return render_template(
        "search/results.html",
        q=q,
        kind=kind,
        results=results,
        total=total,
        filters=filters,
        statuses=PROJECT_STATUSES,
        searched=wants,
    )
