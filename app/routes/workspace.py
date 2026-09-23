import os
import uuid
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.constants import ALLOWED_FILE_EXT, PROJECT_STATUSES, TASK_STATUSES
from app.extensions import db
from app.models import (
    AcademicResource,
    Activity,
    Answer,
    Event,
    FileItem,
    Idea,
    Note,
    Project,
    ProjectInvite,
    ProjectMember,
    Question,
    Task,
    User,
    utcnow,
)
from app.services import log_activity, notify, unique_slug
from app.validators import clip

workspace_bp = Blueprint("workspace", __name__)


def _project(slug):
    return Project.query.filter_by(slug=slug).first_or_404()


def _is_member(project, user=None):
    user = user or current_user
    return ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()


@workspace_bp.route("/notes")
@login_required
def notes():
    rows = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
    return render_template("workspace/notes.html", notes=rows)


@workspace_bp.route("/notes/new", methods=["GET", "POST"])
@login_required
def note_new():
    return _save_note(None)


@workspace_bp.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
@login_required
def note_edit(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    return _save_note(note)


def _save_note(note):
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        title, title_error = clip(form.get("title"), 140, required=True, label="Title")
        body, body_error = clip(form.get("body"), 20000, label="Note")
        if title_error:
            errors["title"] = title_error
        if body_error:
            errors["body"] = body_error
        if not errors:
            if note is None:
                note = Note(user_id=current_user.id)
                db.session.add(note)
            note.title = title
            note.body = body or ""
            log_activity(current_user.id, f"You saved the note {title}.", url_for("workspace.notes"))
            db.session.commit()
            flash("Note saved.", "success")
            return redirect(url_for("workspace.notes"))
    return render_template("workspace/note_form.html", errors=errors, form=form, note=note)


@workspace_bp.route("/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def note_delete(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    flash("Note deleted.", "success")
    return redirect(url_for("workspace.notes"))


@workspace_bp.route("/files")
@login_required
def files():
    rows = FileItem.query.filter_by(owner_id=current_user.id).order_by(FileItem.created_at.desc()).all()
    return render_template("workspace/files.html", files=rows)


@workspace_bp.route("/files/upload", methods=["POST"])
@login_required
def upload_file():
    storage = request.files.get("file")
    if not storage or not storage.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("workspace.files"))
    filename = secure_filename(storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_FILE_EXT:
        flash("That file type isn't allowed.", "error")
        return redirect(url_for("workspace.files"))
    stored = f"{uuid.uuid4().hex}{ext}"
    folder = current_app.config["FILE_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, stored)
    storage.save(path)
    item = FileItem(
        owner_id=current_user.id,
        stored_name=stored,
        original_name=filename[:180] or "file",
        size=os.path.getsize(path),
        mime=storage.mimetype or "",
    )
    db.session.add(item)
    log_activity(current_user.id, f"File uploaded: {item.original_name}", url_for("workspace.files"))
    db.session.commit()
    flash("File uploaded.", "success")
    return redirect(url_for("workspace.files"))


@workspace_bp.route("/files/<int:file_id>/download")
@login_required
def download_file(file_id):
    item = FileItem.query.filter_by(id=file_id, owner_id=current_user.id).first_or_404()
    return send_from_directory(
        current_app.config["FILE_FOLDER"],
        item.stored_name,
        as_attachment=True,
        download_name=item.original_name,
    )


@workspace_bp.route("/files/<int:file_id>/delete", methods=["POST"])
@login_required
def delete_file(file_id):
    item = FileItem.query.filter_by(id=file_id, owner_id=current_user.id).first_or_404()
    path = os.path.join(current_app.config["FILE_FOLDER"], item.stored_name)
    if os.path.isfile(path):
        os.remove(path)
    db.session.delete(item)
    db.session.commit()
    flash("File deleted.", "success")
    return redirect(url_for("workspace.files"))


@workspace_bp.route("/projects")
@login_required
def projects():
    rows = (
        Project.query.join(ProjectMember)
        .filter(ProjectMember.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    discover = (
        Project.query.filter(~Project.id.in_([p.id for p in rows] or [0]))
        .order_by(Project.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template("workspace/projects.html", projects=rows, discover=discover)


@workspace_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def project_new():
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name, name_error = clip(form.get("name"), 80, required=True, label="Name")
        description, desc_error = clip(form.get("description"), 2000, label="Description")
        status = form.get("status") or "Planning"
        if name_error:
            errors["name"] = name_error
        if desc_error:
            errors["description"] = desc_error
        if status not in PROJECT_STATUSES:
            errors["status"] = "Choose a status."
        if not errors:
            project = Project(
                name=name,
                slug=unique_slug(Project, name),
                description=description or "",
                status=status,
                creator_id=current_user.id,
            )
            db.session.add(project)
            db.session.flush()
            db.session.add(ProjectMember(project_id=project.id, user_id=current_user.id, role="owner"))
            link = url_for("workspace.project_detail", slug=project.slug)
            log_activity(current_user.id, f"You created the project {project.name}.", link)
            db.session.commit()
            flash("Project created.", "success")
            return redirect(link)
    return render_template("workspace/project_form.html", errors=errors, form=form, statuses=PROJECT_STATUSES)


@workspace_bp.route("/projects/<slug>")
@login_required
def project_detail(slug):
    project = _project(slug)
    member = _is_member(project)
    pending = ProjectInvite.query.filter_by(
        project_id=project.id, invitee_id=current_user.id, status="pending"
    ).first()
    return render_template(
        "workspace/project_detail.html",
        project=project,
        member=member,
        pending=pending,
        statuses=TASK_STATUSES,
    )


@workspace_bp.route("/projects/<slug>/invite", methods=["POST"])
@login_required
def project_invite(slug):
    project = _project(slug)
    member = _is_member(project)
    if not member or member.role != "owner":
        abort(403)
    username = (request.form.get("username") or "").strip().lower()
    user = User.query.filter_by(username=username, status="active").first()
    if not user:
        flash("No active student with that username.", "error")
        return redirect(url_for("workspace.project_detail", slug=slug))
    if _is_member(project, user):
        flash("They are already on the project.", "info")
        return redirect(url_for("workspace.project_detail", slug=slug))
    existing = ProjectInvite.query.filter_by(project_id=project.id, invitee_id=user.id, status="pending").first()
    if not existing:
        db.session.add(ProjectInvite(project_id=project.id, inviter_id=current_user.id, invitee_id=user.id))
        notify(
            user.id,
            "project_invitation",
            f"Invitation to {project.name}",
            f"{current_user.name} invited you to collaborate.",
            url_for("workspace.project_detail", slug=slug),
            actor_id=current_user.id,
        )
        db.session.commit()
    flash(f"Invitation sent to {user.name}.", "success")
    return redirect(url_for("workspace.project_detail", slug=slug))


@workspace_bp.route("/project-invites/<int:invite_id>/respond", methods=["POST"])
@login_required
def project_respond(invite_id):
    invite = db.session.get(ProjectInvite, invite_id) or abort(404)
    if invite.invitee_id != current_user.id or invite.status != "pending":
        abort(403)
    decision = request.form.get("status")
    if decision not in {"accepted", "declined"}:
        abort(400)
    invite.status = decision
    if decision == "accepted" and not _is_member(invite.project):
        db.session.add(ProjectMember(project_id=invite.project_id, user_id=current_user.id, role="member"))
        notify(
            invite.inviter_id,
            "project_invitation",
            f"{current_user.name} joined {invite.project.name}",
            "",
            url_for("workspace.project_detail", slug=invite.project.slug),
            actor_id=current_user.id,
        )
        log_activity(
            current_user.id,
            f"You joined the project {invite.project.name}.",
            url_for("workspace.project_detail", slug=invite.project.slug),
        )
    db.session.commit()
    flash("Invitation updated.", "success")
    return redirect(url_for("workspace.project_detail", slug=invite.project.slug))


@workspace_bp.route("/projects/<slug>/tasks", methods=["POST"])
@login_required
def add_task(slug):
    project = _project(slug)
    if not _is_member(project):
        abort(403)
    title, title_error = clip(request.form.get("title"), 140, required=True, label="Task")
    if title_error:
        flash(title_error, "error")
        return redirect(url_for("workspace.project_detail", slug=slug))
    assignee_id = request.form.get("assignee_id", type=int)
    assignee = None
    if assignee_id:
        person = db.session.get(User, assignee_id)
        assignee = _is_member(project, person) if person else None
        if not assignee:
            flash("Assign the task to a project member.", "error")
            return redirect(url_for("workspace.project_detail", slug=slug))
    task = Task(
        project_id=project.id,
        title=title,
        assignee_id=assignee.user_id if assignee else None,
        created_by=current_user.id,
        status="To do",
    )
    db.session.add(task)
    if assignee and assignee.user_id != current_user.id:
        notify(
            assignee.user_id,
            "task_assignment",
            f"Task assigned in {project.name}",
            title,
            url_for("workspace.project_detail", slug=slug),
            actor_id=current_user.id,
        )
    db.session.commit()
    flash("Task added.", "success")
    return redirect(url_for("workspace.project_detail", slug=slug))


@workspace_bp.route("/events", methods=["GET", "POST"])
@login_required
def events():
    errors = {}
    if request.method == "POST":
        title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
        description, _ = clip(request.form.get("description"), 1000, label="Description")
        location, loc_error = clip(request.form.get("location"), 140, label="Location")
        raw = (request.form.get("starts_at") or "").strip()
        starts = None
        try:
            starts = datetime.fromisoformat(raw)
        except ValueError:
            errors["starts_at"] = "Choose a date and time."
        if title_error:
            errors["title"] = title_error
        if loc_error:
            errors["location"] = loc_error
        if not errors and starts:
            event = Event(
                creator_id=current_user.id,
                title=title,
                description=description or "",
                location=location or "",
                starts_at=starts,
            )
            db.session.add(event)
            log_activity(current_user.id, f"You scheduled {title}.", url_for("workspace.events"))
            db.session.commit()
            flash("Event added.", "success")
            return redirect(url_for("workspace.events"))
    upcoming = Event.query.filter(Event.starts_at >= utcnow()).order_by(Event.starts_at.asc()).all()
    past = Event.query.filter(Event.starts_at < utcnow()).order_by(Event.starts_at.desc()).limit(8).all()
    return render_template("workspace/events.html", upcoming=upcoming, past=past, errors=errors)


@workspace_bp.route("/ideas", methods=["GET", "POST"])
@login_required
def ideas():
    errors = {}
    if request.method == "POST":
        title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
        description, desc_error = clip(request.form.get("description"), 1000, required=True, label="Description")
        skills, _ = clip(request.form.get("skills_needed"), 200, label="Skills")
        if title_error:
            errors["title"] = title_error
        if desc_error:
            errors["description"] = desc_error
        if not errors:
            idea = Idea(
                author_id=current_user.id,
                title=title,
                description=description,
                skills_needed=skills or "",
            )
            db.session.add(idea)
            db.session.commit()
            flash("Idea shared.", "success")
            return redirect(url_for("workspace.ideas"))
    rows = Idea.query.order_by(Idea.created_at.desc()).all()
    return render_template("workspace/ideas.html", ideas=rows, errors=errors)


@workspace_bp.route("/questions")
@login_required
def questions():
    rows = Question.query.order_by(Question.created_at.desc()).all()
    return render_template("workspace/questions.html", questions=rows)


@workspace_bp.route("/questions/new", methods=["GET", "POST"])
@login_required
def question_new():
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        title, title_error = clip(form.get("title"), 160, required=True, label="Title")
        body, body_error = clip(form.get("body"), 5000, required=True, label="Question")
        tags, _ = clip(form.get("tags"), 200, label="Tags")
        if title_error:
            errors["title"] = title_error
        if body_error:
            errors["body"] = body_error
        if not errors:
            item = Question(author_id=current_user.id, title=title, body=body, tags=tags or "")
            db.session.add(item)
            db.session.flush()
            log_activity(current_user.id, "You asked a question.", url_for("workspace.question_detail", question_id=item.id))
            db.session.commit()
            flash("Question posted.", "success")
            return redirect(url_for("workspace.question_detail", question_id=item.id))
    return render_template("workspace/question_form.html", errors=errors, form=form)


@workspace_bp.route("/questions/<int:question_id>")
@login_required
def question_detail(question_id):
    item = db.session.get(Question, question_id) or abort(404)
    return render_template("workspace/question_detail.html", question=item)


@workspace_bp.route("/questions/<int:question_id>/answer", methods=["POST"])
@login_required
def answer(question_id):
    item = db.session.get(Question, question_id) or abort(404)
    body, body_error = clip(request.form.get("body"), 4000, required=True, label="Answer")
    if body_error:
        flash(body_error, "error")
        return redirect(url_for("workspace.question_detail", question_id=item.id))
    db.session.add(Answer(question_id=item.id, author_id=current_user.id, body=body))
    notify(
        item.author_id,
        "comment",
        f"{current_user.name} answered your question",
        body[:180],
        url_for("workspace.question_detail", question_id=item.id),
        actor_id=current_user.id,
    )
    db.session.commit()
    flash("Answer posted.", "success")
    return redirect(url_for("workspace.question_detail", question_id=item.id))


@workspace_bp.route("/academics", methods=["GET", "POST"])
@login_required
def academics():
    errors = {}
    if request.method == "POST":
        title, title_error = clip(request.form.get("title"), 160, required=True, label="Title")
        subject, subject_error = clip(request.form.get("subject"), 80, required=True, label="Subject")
        description, _ = clip(request.form.get("description"), 1000, label="Description")
        link = (request.form.get("link") or "").strip()
        if title_error:
            errors["title"] = title_error
        if subject_error:
            errors["subject"] = subject_error
        if link and not link.startswith(("http://", "https://")):
            errors["link"] = "Use a full http or https link."
        if len(link) > 300:
            errors["link"] = "That link is too long."
        if not errors:
            db.session.add(
                AcademicResource(
                    author_id=current_user.id,
                    title=title,
                    subject=subject,
                    description=description or "",
                    link=link,
                )
            )
            db.session.commit()
            flash("Resource shared.", "success")
            return redirect(url_for("workspace.academics"))
    resources = AcademicResource.query.order_by(AcademicResource.created_at.desc()).all()
    return render_template("workspace/academics.html", resources=resources, errors=errors)


@workspace_bp.route("/activity")
@login_required
def activity():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Activity.query.filter_by(user_id=current_user.id)
        .order_by(Activity.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template("workspace/activity.html", pagination=pagination)
