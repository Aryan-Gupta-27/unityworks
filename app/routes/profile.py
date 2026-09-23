import os
import uuid

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.constants import ALLOWED_IMAGE_EXT, EXPERIENCE_LEVELS, MENTOR_ROLES, PUBLIC_SECTIONS
from app.extensions import db
from app.models import Achievement, Community, CommunityMember, Project, ProjectMember, User
from app.services import log_activity, sync_achievements
from app.validators import clean_password, clip

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit():
    errors = {}
    if request.method == "POST":
        action = request.form.get("action", "profile")
        if action == "password":
            current = request.form.get("current_password") or ""
            new_password, password_error = clean_password(
                request.form.get("new_password"), request.form.get("confirm_password")
            )
            if not current_user.check_password(current):
                errors["current_password"] = "Current password is incorrect."
            if password_error:
                errors["new_password"] = password_error
            if not errors:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password updated.", "success")
                return redirect(url_for("profile.edit"))
        else:
            headline, e = clip(request.form.get("headline"), 140, label="Headline")
            bio, e2 = clip(request.form.get("bio"), 500, label="Bio")
            skills, e3 = clip(request.form.get("skills"), 300, label="Skills")
            education, e4 = clip(request.form.get("education"), 200, label="Education")
            interests, e5 = clip(request.form.get("interests"), 300, label="Interests")
            college, e6 = clip(request.form.get("college"), 140, label="College")
            program, e7 = clip(request.form.get("program"), 120, label="Program")
            year, e8 = clip(request.form.get("academic_year"), 40, label="Academic year")
            experience = (request.form.get("experience") or "").strip()
            certifications, e9 = clip(request.form.get("certifications"), 400, label="Certifications")
            honors, e10 = clip(request.form.get("honors"), 400, label="Achievements")
            experience_note, e11 = clip(request.form.get("experience_note"), 400, label="Experience")
            mentor_role = (request.form.get("mentor_role") or "").strip()
            for key, err in (
                ("headline", e),
                ("bio", e2),
                ("skills", e3),
                ("education", e4),
                ("interests", e5),
                ("college", e6),
                ("program", e7),
                ("academic_year", e8),
                ("certifications", e9),
                ("honors", e10),
                ("experience_note", e11),
            ):
                if err:
                    errors[key] = err
            if experience and experience not in EXPERIENCE_LEVELS:
                errors["experience"] = "Choose a valid experience level."
            if mentor_role and mentor_role not in MENTOR_ROLES:
                errors["mentor_role"] = "Choose mentor, mentee, or both."
            picture = request.files.get("avatar")
            if picture and picture.filename:
                stored, pic_error = _save_avatar(picture)
                if pic_error:
                    errors["avatar"] = pic_error
                else:
                    _delete_old_avatar(current_user.avatar)
                    current_user.avatar = stored
            if not errors:
                current_user.headline = headline or ""
                current_user.bio = bio or ""
                current_user.skills = skills or ""
                current_user.education = education or ""
                current_user.interests = interests or ""
                current_user.college = college or ""
                current_user.program = program or ""
                current_user.academic_year = year or ""
                current_user.experience = experience
                current_user.certifications = certifications or ""
                current_user.honors = honors or ""
                current_user.experience_note = experience_note or ""
                current_user.mentor_role = mentor_role
                current_user.profile_public = request.form.get("profile_public") == "1"
                current_user.public_sections = ",".join(
                    section for section in PUBLIC_SECTIONS if request.form.get(f"share_{section}") == "1"
                )
                sync_achievements(current_user)
                log_activity(current_user.id, "You updated your profile.", url_for("profile.view", username=current_user.username))
                db.session.commit()
                flash("Profile saved.", "success")
                return redirect(url_for("profile.view", username=current_user.username))
    return render_template(
        "profile/edit.html",
        errors=errors,
        levels=EXPERIENCE_LEVELS,
        mentor_roles=MENTOR_ROLES,
        public_sections=PUBLIC_SECTIONS,
    )


@profile_bp.route("/profile/<username>")
@login_required
def view(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    if user.status != "active" and not current_user.is_admin and user.id != current_user.id:
        abort(404)
    communities = (
        Community.query.join(CommunityMember)
        .filter(CommunityMember.user_id == user.id)
        .order_by(Community.name.asc())
        .all()
    )
    rows = (
        Project.query.join(ProjectMember)
        .filter(ProjectMember.user_id == user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    projects = []
    for project in rows:
        shared = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
        if project.visibility == "public" or project.published or shared or current_user.is_admin or user.id == current_user.id:
            projects.append(project)
    if sync_achievements(user):
        db.session.commit()
    badges = Achievement.query.filter_by(user_id=user.id).order_by(Achievement.earned_at.asc()).all()
    return render_template(
        "profile/view.html",
        user=user,
        communities=communities,
        projects=projects,
        badges=badges,
    )


@profile_bp.route("/u/<username>")
def public(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    if user.status != "active":
        abort(404)
    if sync_achievements(user):
        db.session.commit()
    badges = Achievement.query.filter_by(user_id=user.id).order_by(Achievement.earned_at.asc()).all()
    projects = []
    communities = []
    if user.shares("projects"):
        rows = (
            Project.query.join(ProjectMember)
            .filter(ProjectMember.user_id == user.id)
            .order_by(Project.updated_at.desc())
            .all()
        )
        projects = [project for project in rows if project.visibility == "public" or project.published]
    if user.shares("communities"):
        communities = (
            Community.query.join(CommunityMember)
            .filter(CommunityMember.user_id == user.id, Community.visibility == "public")
            .order_by(Community.name.asc())
            .all()
        )
    return render_template(
        "profile/public.html",
        user=user,
        badges=badges,
        projects=projects,
        communities=communities,
    )


@profile_bp.route("/portfolio")
@login_required
def portfolio_redirect():
    return redirect(url_for("profile.view", username=current_user.username))


@profile_bp.route("/media/avatars/<filename>")
def avatar_file(filename):
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        abort(404)
    folder = current_app.config["AVATAR_FOLDER"]
    path = os.path.join(folder, filename)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(folder, filename)


def _save_avatar(storage):
    filename = secure_filename(storage.filename or "")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return None, "Use a PNG, JPG, or WEBP image."
    try:
        image = Image.open(storage.stream)
        image = image.convert("RGB")
        image.thumbnail((512, 512))
    except (UnidentifiedImageError, OSError):
        return None, "That image could not be read."
    stored = f"{uuid.uuid4().hex}.jpg"
    folder = current_app.config["AVATAR_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    image.save(os.path.join(folder, stored), "JPEG", quality=86, optimize=True)
    return stored, None


def _delete_old_avatar(avatar):
    if not avatar or avatar.startswith("seed:"):
        return
    path = os.path.join(current_app.config["AVATAR_FOLDER"], avatar)
    if os.path.isfile(path):
        os.remove(path)
