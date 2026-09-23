from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.constants import ACTIVITY_AREAS, EVENT_CATEGORIES, RESOURCE_KINDS, SUBJECTS
from app.extensions import db
from app.models import (
    AcademicResource,
    Activity,
    Answer,
    AnswerVote,
    Community,
    Event,
    FileItem,
    Idea,
    IdeaInterest,
    Note,
    Post,
    Question,
    utcnow,
)
from app.services import (
    contains,
    log_activity,
    notify,
    remove_stored_file,
    safe_stored_name,
    save_file,
    store_upload,
    sync_achievements,
)
from app.validators import clean_http_url, clip

workspace_bp = Blueprint("workspace", __name__)


@workspace_bp.route("/notes")
@login_required
def notes():
    q = (request.args.get("q") or "").strip()
    query = Note.query.filter_by(user_id=current_user.id).filter(Note.project_id.is_(None))
    if q:
        query = query.filter(contains(Note.title, q) | contains(Note.body, q))
    rows = query.order_by(Note.updated_at.desc()).all()
    return render_template("workspace/notes.html", notes=rows, q=q)


@workspace_bp.route("/notes/new", methods=["GET", "POST"])
@login_required
def note_new():
    return _save_note(None)


@workspace_bp.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
@login_required
def note_edit(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id, project_id=None).first_or_404()
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
    note = Note.query.filter_by(id=note_id, user_id=current_user.id, project_id=None).first_or_404()
    db.session.delete(note)
    db.session.commit()
    flash("Note deleted.", "success")
    return redirect(url_for("workspace.notes"))


@workspace_bp.route("/files")
@login_required
def files():
    page = request.args.get("page", 1, type=int) or 1
    pagination = (
        FileItem.query.filter_by(owner_id=current_user.id)
        .filter(FileItem.project_id.is_(None))
        .order_by(FileItem.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template("workspace/files.html", files=pagination.items, pagination=pagination)


@workspace_bp.route("/files/upload", methods=["POST"])
@login_required
def upload_file():
    item, error = store_upload(request.files.get("file"), current_user.id)
    if error:
        flash(error, "error")
        return redirect(url_for("workspace.files"))
    db.session.add(item)
    log_activity(current_user.id, f"File uploaded: {item.original_name}", url_for("workspace.files"))
    db.session.commit()
    flash("File uploaded.", "success")
    return redirect(url_for("workspace.files"))


@workspace_bp.route("/files/<int:file_id>/download")
@login_required
def download_file(file_id):
    item = FileItem.query.filter_by(id=file_id, owner_id=current_user.id, project_id=None).first_or_404()
    name = safe_stored_name(item.stored_name)
    if not name:
        abort(404)
    return send_from_directory(
        current_app.config["FILE_FOLDER"],
        name,
        as_attachment=True,
        download_name=item.original_name,
    )


@workspace_bp.route("/files/<int:file_id>/delete", methods=["POST"])
@login_required
def delete_file(file_id):
    item = FileItem.query.filter_by(id=file_id, owner_id=current_user.id, project_id=None).first_or_404()
    stored = item.stored_name
    db.session.delete(item)
    db.session.commit()
    remove_stored_file(stored)
    flash("File deleted.", "success")
    return redirect(url_for("workspace.files"))


@workspace_bp.route("/events", methods=["GET", "POST"])
@login_required
def events():
    errors = {}
    category = (request.args.get("category") or "").strip()
    if request.method == "POST":
        title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
        description, _ = clip(request.form.get("description"), 1000, label="Description")
        location, loc_error = clip(request.form.get("location"), 140, label="Location")
        chosen = (request.form.get("category") or "Event").strip()
        link, link_error = clean_http_url(request.form.get("registration_link"), "Registration link")
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
        if chosen not in EVENT_CATEGORIES:
            errors["category"] = "Choose a category."
        if link_error:
            errors["registration_link"] = link_error
        if not errors and starts:
            event = Event(
                creator_id=current_user.id,
                title=title,
                description=description or "",
                location=location or "",
                category=chosen,
                registration_link=link or "",
                starts_at=starts,
            )
            db.session.add(event)
            log_activity(current_user.id, f"You scheduled {title}.", url_for("workspace.events"))
            db.session.commit()
            flash("Event added.", "success")
            return redirect(url_for("workspace.events", category=chosen))
    upcoming_query = Event.query.filter(Event.starts_at >= utcnow())
    past_query = Event.query.filter(Event.starts_at < utcnow())
    if category in EVENT_CATEGORIES:
        upcoming_query = upcoming_query.filter_by(category=category)
        past_query = past_query.filter_by(category=category)
    page = request.args.get("page", 1, type=int) or 1
    pagination = upcoming_query.order_by(Event.starts_at.asc()).paginate(page=page, per_page=12, error_out=False)
    past = past_query.order_by(Event.starts_at.desc()).limit(8).all()
    return render_template(
        "workspace/events.html",
        upcoming=pagination.items,
        past=past,
        errors=errors,
        categories=EVENT_CATEGORIES,
        category=category if category in EVENT_CATEGORIES else "",
        pagination=pagination,
    )


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
    page = request.args.get("page", 1, type=int) or 1
    pagination = Idea.query.order_by(Idea.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    rows = pagination.items
    idea_ids = [row.id for row in rows]
    interests = {}
    mine = set()
    if idea_ids:
        for row in IdeaInterest.query.filter(IdeaInterest.idea_id.in_(idea_ids)).all():
            interests.setdefault(row.idea_id, []).append(row)
            if row.user_id == current_user.id:
                mine.add(row.idea_id)
    return render_template(
        "workspace/ideas.html",
        ideas=rows,
        errors=errors,
        interests=interests,
        mine=mine,
        pagination=pagination,
    )


@workspace_bp.route("/ideas/<int:idea_id>/interest", methods=["POST"])
@login_required
def idea_interest(idea_id):
    idea = db.session.get(Idea, idea_id) or abort(404)
    if idea.author_id == current_user.id:
        abort(403)
    existing = IdeaInterest.query.filter_by(idea_id=idea.id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        flash("Interest removed.", "info")
    else:
        db.session.add(IdeaInterest(idea_id=idea.id, user_id=current_user.id))
        notify(
            idea.author_id,
            "comment",
            f"{current_user.name} is interested in your idea",
            idea.title,
            url_for("workspace.ideas"),
            actor_id=current_user.id,
        )
        flash("Interest noted. The author can invite you when the idea becomes a project.", "success")
    db.session.commit()
    return redirect(url_for("workspace.ideas"))


@workspace_bp.route("/questions")
@login_required
def questions():
    subject = (request.args.get("subject") or "").strip()
    query = Question.query
    if subject in SUBJECTS:
        query = query.filter_by(subject=subject)
    page = request.args.get("page", 1, type=int) or 1
    pagination = query.order_by(Question.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template(
        "workspace/questions.html",
        questions=pagination.items,
        subjects=SUBJECTS,
        subject=subject if subject in SUBJECTS else "",
        pagination=pagination,
    )


@workspace_bp.route("/questions/new", methods=["GET", "POST"])
@login_required
def question_new():
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        title, title_error = clip(form.get("title"), 160, required=True, label="Title")
        body, body_error = clip(form.get("body"), 5000, required=True, label="Question")
        tags, _ = clip(form.get("tags"), 200, label="Tags")
        subject = (form.get("subject") or "").strip()
        if title_error:
            errors["title"] = title_error
        if body_error:
            errors["body"] = body_error
        if subject not in SUBJECTS:
            errors["subject"] = "Choose a subject."
        if not errors:
            item = Question(author_id=current_user.id, title=title, body=body, subject=subject, tags=tags or "")
            db.session.add(item)
            db.session.flush()
            log_activity(current_user.id, "You asked a question.", url_for("workspace.question_detail", question_id=item.id))
            db.session.commit()
            flash("Question posted.", "success")
            return redirect(url_for("workspace.question_detail", question_id=item.id))
    return render_template("workspace/question_form.html", errors=errors, form=form, subjects=SUBJECTS)


@workspace_bp.route("/questions/<int:question_id>")
@login_required
def question_detail(question_id):
    item = db.session.get(Question, question_id) or abort(404)
    answers = sorted(item.answers, key=lambda row: (not row.accepted, -row.score, row.created_at))
    return render_template("workspace/question_detail.html", question=item, answers=answers)


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


def _answer(answer_id):
    return db.session.get(Answer, answer_id) or abort(404)


@workspace_bp.route("/answers/<int:answer_id>/edit", methods=["POST"])
@login_required
def answer_edit(answer_id):
    item = _answer(answer_id)
    if item.author_id != current_user.id:
        abort(403)
    body, body_error = clip(request.form.get("body"), 4000, required=True, label="Answer")
    if body_error:
        flash(body_error, "error")
        return redirect(url_for("workspace.question_detail", question_id=item.question_id))
    item.body = body
    item.updated_at = utcnow()
    db.session.commit()
    flash("Answer updated.", "success")
    return redirect(url_for("workspace.question_detail", question_id=item.question_id))


@workspace_bp.route("/answers/<int:answer_id>/delete", methods=["POST"])
@login_required
def answer_delete(answer_id):
    item = _answer(answer_id)
    if item.author_id != current_user.id:
        abort(403)
    question_id = item.question_id
    db.session.delete(item)
    db.session.commit()
    flash("Answer deleted.", "success")
    return redirect(url_for("workspace.question_detail", question_id=question_id))


@workspace_bp.route("/answers/<int:answer_id>/vote", methods=["POST"])
@login_required
def answer_vote(answer_id):
    item = _answer(answer_id)
    choice = request.form.get("value")
    if choice not in {"up", "down"}:
        abort(400)
    value = 1 if choice == "up" else -1
    existing = AnswerVote.query.filter_by(user_id=current_user.id, answer_id=item.id).first()
    if existing and existing.value == value:
        db.session.delete(existing)
    elif existing:
        existing.value = value
    else:
        db.session.add(AnswerVote(user_id=current_user.id, answer_id=item.id, value=value))
    db.session.commit()
    return redirect(url_for("workspace.question_detail", question_id=item.question_id))


@workspace_bp.route("/answers/<int:answer_id>/accept", methods=["POST"])
@login_required
def answer_accept(answer_id):
    item = _answer(answer_id)
    question = item.question
    if question.author_id != current_user.id:
        abort(403)
    if item.author_id == current_user.id:
        flash("Accept another student's answer.", "error")
        return redirect(url_for("workspace.question_detail", question_id=question.id))
    for row in question.answers:
        row.accepted = row.id == item.id
    notify(
        item.author_id,
        "comment",
        f"{current_user.name} accepted your answer",
        question.title,
        url_for("workspace.question_detail", question_id=question.id),
        actor_id=current_user.id,
    )
    sync_achievements(item.author)
    db.session.commit()
    flash("Answer accepted.", "success")
    return redirect(url_for("workspace.question_detail", question_id=question.id))


@workspace_bp.route("/academics", methods=["GET", "POST"])
@login_required
def academics():
    errors = {}
    subject = (request.args.get("subject") or "").strip()
    q = (request.args.get("q") or "").strip()
    if request.method == "POST":
        title, title_error = clip(request.form.get("title"), 160, required=True, label="Title")
        chosen = (request.form.get("subject") or "").strip()
        kind = (request.form.get("kind") or "Study Resource").strip()
        description, _ = clip(request.form.get("description"), 1000, label="Description")
        tags, _ = clip(request.form.get("tags"), 200, label="Tags")
        link, link_error = clean_http_url(request.form.get("link"), "Link")
        upload = request.files.get("file")
        saved = None
        if title_error:
            errors["title"] = title_error
        if chosen not in SUBJECTS:
            errors["subject"] = "Choose a subject."
        if kind not in RESOURCE_KINDS:
            errors["kind"] = "Choose a resource type."
        if link_error:
            errors["link"] = link_error
        has_file = bool(upload and upload.filename)
        if kind == "Link" and not link:
            errors["link"] = "A link resource needs a link."
        if kind == "PDF" and not has_file:
            errors["file"] = "Upload the PDF."
        if not link and not has_file:
            errors["file"] = errors.get("file") or "Add a file or a link."
        if has_file and not errors:
            saved, file_error = save_file(upload)
            if file_error:
                errors["file"] = file_error
                saved = None
        if not errors:
            resource = AcademicResource(
                author_id=current_user.id,
                title=title,
                subject=chosen,
                kind=kind,
                description=description or "",
                tags=tags or "",
                link=link or "",
                stored_name=(saved or {}).get("stored_name", ""),
                original_name=(saved or {}).get("original_name", ""),
                size=(saved or {}).get("size", 0),
            )
            db.session.add(resource)
            sync_achievements(current_user)
            log_activity(current_user.id, f"You shared {title}.", url_for("workspace.academics"))
            db.session.commit()
            flash("Resource shared.", "success")
            return redirect(url_for("workspace.academics", subject=chosen))
    query = AcademicResource.query
    if subject in SUBJECTS:
        query = query.filter_by(subject=subject)
    if q:
        query = query.filter(
            contains(AcademicResource.title, q)
            | contains(AcademicResource.description, q)
            | contains(AcademicResource.tags, q)
            | contains(AcademicResource.subject, q)
        )
    page = request.args.get("page", 1, type=int) or 1
    pagination = query.order_by(AcademicResource.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    resources = pagination.items
    question_query = Question.query
    if subject in SUBJECTS:
        question_query = question_query.filter_by(subject=subject)
    notes = (
        Note.query.filter_by(user_id=current_user.id)
        .filter(Note.project_id.is_(None))
        .order_by(Note.updated_at.desc())
        .limit(4)
        .all()
    )
    discussions = (
        Post.query.join(Community)
        .filter(Community.category == "Academics", Community.visibility == "public")
        .order_by(Post.created_at.desc())
        .limit(4)
        .all()
    )
    return render_template(
        "workspace/academics.html",
        resources=resources,
        errors=errors,
        subjects=SUBJECTS,
        kinds=RESOURCE_KINDS,
        subject=subject if subject in SUBJECTS else "",
        q=q,
        questions=question_query.order_by(Question.created_at.desc()).limit(5).all(),
        notes=notes,
        discussions=discussions,
        pagination=pagination,
    )


@workspace_bp.route("/academics/<int:resource_id>/file")
@login_required
def academic_file(resource_id):
    item = db.session.get(AcademicResource, resource_id) or abort(404)
    name = safe_stored_name(item.stored_name)
    if not name:
        abort(404)
    return send_from_directory(
        current_app.config["FILE_FOLDER"],
        name,
        as_attachment=True,
        download_name=item.original_name or name,
    )


@workspace_bp.route("/academics/<int:resource_id>/delete", methods=["POST"])
@login_required
def academic_delete(resource_id):
    item = db.session.get(AcademicResource, resource_id) or abort(404)
    if item.author_id != current_user.id and not current_user.is_admin:
        abort(403)
    stored = item.stored_name
    db.session.delete(item)
    db.session.commit()
    remove_stored_file(stored)
    flash("Resource removed.", "success")
    return redirect(url_for("workspace.academics"))


@workspace_bp.route("/activity")
@login_required
def activity():
    area = (request.args.get("area") or "").strip()
    if area not in ACTIVITY_AREAS:
        area = ""
    page = request.args.get("page", 1, type=int) or 1
    query = Activity.query.filter_by(user_id=current_user.id)
    if area:
        query = query.filter_by(area=area)
    pagination = query.order_by(Activity.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template(
        "workspace/activity.html",
        pagination=pagination,
        area=area,
        areas=ACTIVITY_AREAS,
    )


def _attach_project_routes():
    from app.routes.projects import register_project_routes

    register_project_routes(workspace_bp)


_attach_project_routes()
