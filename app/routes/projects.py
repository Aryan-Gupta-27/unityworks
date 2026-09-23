import os
from datetime import datetime

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.constants import (
    DISCUSSION_KINDS,
    FILE_FOLDERS,
    PROJECT_CATEGORIES,
    PROJECT_ROLES,
    PROJECT_STATUSES,
    PROJECT_VISIBILITY,
    TASK_PRIORITIES,
    TASK_STATUSES,
)
from app.extensions import db
from app.models import (
    Activity,
    FileItem,
    Idea,
    IdeaInterest,
    Note,
    Project,
    ProjectDiscussion,
    ProjectInvite,
    ProjectMember,
    Task,
    User,
    utcnow,
)
from app.services import (
    can_contribute,
    can_delete_task,
    can_edit_file,
    can_edit_note,
    can_edit_task,
    can_manage,
    can_own,
    can_read_work,
    can_remove_member,
    contains,
    log_activity,
    notify,
    project_membership,
    project_stats,
    remove_stored_file,
    safe_stored_name,
    store_upload,
    unique_slug,
)
from app.validators import clean_http_url, clip


def _project(slug):
    return Project.query.filter_by(slug=slug).first_or_404()


def _pending(project):
    if not current_user.is_authenticated:
        return None
    return ProjectInvite.query.filter_by(
        project_id=project.id, invitee_id=current_user.id, status="pending"
    ).first()


def _locked(project, pending=None, work=False):
    return render_template("workspace/project_locked.html", project=project, pending=pending, work=work), 403


def _allow(project, pending, tab):
    if project_membership(current_user, project) or current_user.is_admin:
        return True
    if project.visibility == "public":
        return True
    return bool(pending and tab == "overview")


def _ctx(project, tab):
    pending = _pending(project)
    if not _allow(project, pending, tab):
        return None, _locked(project, pending)
    return {
        "project": project,
        "tab": tab,
        "member": project_membership(current_user, project),
        "pending": pending,
        "stats": project_stats(project),
        "can_contribute": can_contribute(current_user, project),
        "can_manage": can_manage(current_user, project),
        "can_own": can_own(current_user, project),
    }, None


def _work_ctx(project, tab):
    ctx, blocked = _ctx(project, tab)
    if blocked:
        return None, blocked
    if not can_read_work(current_user, project):
        return None, _locked(project, ctx["pending"], work=True)
    return ctx, None


def _touch(project):
    project.updated_at = utcnow()


def _log(project, summary):
    log_activity(
        current_user.id,
        summary,
        url_for("workspace.project_detail", slug=project.slug),
        project_id=project.id,
    )
    _touch(project)


def _workers(project):
    return [row for row in project.memberships if row.role in {"owner", "manager", "contributor"}]


def _parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        return False


def _assignee(project, raw):
    if not raw:
        return None, None
    try:
        user_id = int(raw)
    except (TypeError, ValueError):
        return None, "Assign the task to a project member."
    person = db.session.get(User, user_id)
    row = project_membership(person, project) if person else None
    if not row or row.role == "viewer":
        return None, "Assign the task to someone who can work on it."
    return row, None


def _groups(project, folder=None):
    query = FileItem.query.filter_by(project_id=project.id)
    if folder in FILE_FOLDERS:
        query = query.filter_by(folder=folder)
    buckets = {}
    order = []
    for row in query.order_by(FileItem.created_at.desc()).all():
        key = row.group_key or f"id-{row.id}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(row)
    return [sorted(buckets[key], key=lambda item: (item.version, item.id), reverse=True) for key in order]


def _back_tasks(slug, board=False):
    if board or request.form.get("next") == "board":
        return redirect(url_for("workspace.project_board", slug=slug))
    return redirect(url_for("workspace.project_tasks", slug=slug))


@login_required
def projects():
    rows = (
        Project.query.join(ProjectMember)
        .filter(ProjectMember.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    discover = (
        Project.query.filter(
            Project.visibility == "public",
            Project.status != "Archived",
            ~Project.id.in_([row.id for row in rows] or [0]),
        )
        .order_by(Project.updated_at.desc())
        .limit(6)
        .all()
    )
    return render_template(
        "workspace/projects.html",
        projects=[row for row in rows if row.status != "Archived"],
        archived=[row for row in rows if row.status == "Archived"],
        discover=discover,
    )


@login_required
def project_new():
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name, name_error = clip(form.get("name"), 80, required=True, label="Name")
        description, desc_error = clip(form.get("description"), 2000, label="Description")
        category = form.get("category") or "Other"
        status = form.get("status") or "Planning"
        visibility = form.get("visibility") or "public"
        if name_error:
            errors["name"] = name_error
        if desc_error:
            errors["description"] = desc_error
        if category not in PROJECT_CATEGORIES:
            errors["category"] = "Choose a category."
        if status not in PROJECT_STATUSES:
            errors["status"] = "Choose a status."
        if visibility not in PROJECT_VISIBILITY:
            errors["visibility"] = "Choose who can see this project."
        if not errors:
            project = Project(
                name=name,
                slug=unique_slug(Project, name),
                description=description or "",
                category=category,
                status=status,
                visibility=visibility,
                creator_id=current_user.id,
            )
            db.session.add(project)
            db.session.flush()
            db.session.add(ProjectMember(project_id=project.id, user_id=current_user.id, role="owner"))
            _log(project, f"{current_user.name} created the project")
            db.session.commit()
            flash("Project created.", "success")
            return redirect(url_for("workspace.project_detail", slug=project.slug))
    return render_template(
        "workspace/project_form.html",
        errors=errors,
        form=form,
        statuses=PROJECT_STATUSES,
        categories=PROJECT_CATEGORIES,
    )


@login_required
def project_detail(slug):
    project = _project(slug)
    ctx, blocked = _ctx(project, "overview")
    if blocked:
        return blocked
    activity = (
        Activity.query.filter_by(project_id=project.id).order_by(Activity.created_at.desc()).limit(8).all()
    )
    tasks = sorted(project.tasks, key=lambda task: task.updated_at or task.created_at, reverse=True)[:6]
    return render_template("workspace/project_detail.html", activity=activity, recent_tasks=tasks, **ctx)


@login_required
def project_tasks(slug):
    project = _project(slug)
    if request.method == "POST":
        if not can_contribute(current_user, project):
            abort(403)
        title, title_error = clip(request.form.get("title"), 140, required=True, label="Task")
        description, desc_error = clip(request.form.get("description"), 4000, label="Description")
        priority = request.form.get("priority") or "Medium"
        status = request.form.get("status") or "TODO"
        deadline = _parse_date(request.form.get("deadline"))
        assignee, assign_error = _assignee(project, request.form.get("assignee_id"))
        if title_error or desc_error or assign_error or deadline is False or priority not in TASK_PRIORITIES or status not in TASK_STATUSES:
            flash(title_error or desc_error or assign_error or "Check the task fields and try again.", "error")
            return redirect(url_for("workspace.project_tasks", slug=slug))
        task = Task(
            project_id=project.id,
            title=title,
            description=description or "",
            assignee_id=assignee.user_id if assignee else None,
            priority=priority,
            deadline=deadline,
            status=status,
            created_by=current_user.id,
        )
        db.session.add(task)
        _log(project, f"{current_user.name} created a task")
        if status == "DONE":
            _log(project, f"{current_user.name} completed {title}")
        if assignee and assignee.user_id != current_user.id:
            notify(
                assignee.user_id,
                "task_assignment",
                f"Task assigned in {project.name}",
                title,
                url_for("workspace.project_tasks", slug=slug),
                actor_id=current_user.id,
            )
        db.session.commit()
        flash("Task added.", "success")
        return redirect(url_for("workspace.project_tasks", slug=slug))
    ctx, blocked = _ctx(project, "tasks")
    if blocked:
        return blocked
    tasks = sorted(project.tasks, key=lambda task: ((task.deadline or datetime.max), task.created_at))
    return render_template(
        "workspace/project_tasks.html",
        tasks=tasks,
        workers=_workers(project),
        priorities=TASK_PRIORITIES,
        statuses=TASK_STATUSES,
        **ctx,
    )


@login_required
def project_board(slug):
    project = _project(slug)
    ctx, blocked = _ctx(project, "board")
    if blocked:
        return blocked
    columns = {status: [] for status in TASK_STATUSES}
    movable = set()
    for task in project.tasks:
        columns.setdefault(task.status, []).append(task)
        if can_edit_task(current_user, project, task):
            movable.add(task.id)
    return render_template(
        "workspace/project_board.html",
        columns=columns,
        statuses=TASK_STATUSES,
        movable=movable,
        **ctx,
    )


@login_required
def task_status(slug, task_id):
    project = _project(slug)
    task = Task.query.filter_by(id=task_id, project_id=project.id).first_or_404()
    if not can_edit_task(current_user, project, task):
        abort(403)
    status = request.form.get("status") or ""
    if status not in TASK_STATUSES:
        abort(400)
    previous = task.status
    task.status = status
    task.updated_at = utcnow()
    if status == "DONE" and previous != "DONE":
        _log(project, f"{current_user.name} completed {task.title}")
    elif status != previous:
        _log(project, f"{current_user.name} moved {task.title} to {status}")
    else:
        _touch(project)
    db.session.commit()
    return _back_tasks(slug)


@login_required
def task_update(slug, task_id):
    project = _project(slug)
    task = Task.query.filter_by(id=task_id, project_id=project.id).first_or_404()
    if not can_edit_task(current_user, project, task):
        abort(403)
    title, title_error = clip(request.form.get("title"), 140, required=True, label="Task")
    description, desc_error = clip(request.form.get("description"), 4000, label="Description")
    priority = request.form.get("priority") or "Medium"
    status = request.form.get("status") or task.status
    deadline = _parse_date(request.form.get("deadline"))
    assignee, assign_error = _assignee(project, request.form.get("assignee_id"))
    if title_error or desc_error or assign_error or deadline is False or priority not in TASK_PRIORITIES or status not in TASK_STATUSES:
        flash(title_error or desc_error or assign_error or "Check the task fields and try again.", "error")
        return redirect(url_for("workspace.project_tasks", slug=slug))
    previous_assignee = task.assignee_id
    previous_status = task.status
    task.title = title
    task.description = description or ""
    task.priority = priority
    task.deadline = deadline
    task.status = status
    task.assignee_id = assignee.user_id if assignee else None
    task.updated_at = utcnow()
    if status == "DONE" and previous_status != "DONE":
        _log(project, f"{current_user.name} completed {task.title}")
    else:
        _touch(project)
    if assignee and assignee.user_id != current_user.id and assignee.user_id != previous_assignee:
        notify(
            assignee.user_id,
            "task_assignment",
            f"Task assigned in {project.name}",
            title,
            url_for("workspace.project_tasks", slug=slug),
            actor_id=current_user.id,
        )
    db.session.commit()
    flash("Task updated.", "success")
    return redirect(url_for("workspace.project_tasks", slug=slug))


@login_required
def task_delete(slug, task_id):
    project = _project(slug)
    task = Task.query.filter_by(id=task_id, project_id=project.id).first_or_404()
    if not can_delete_task(current_user, project, task):
        abort(403)
    db.session.delete(task)
    _touch(project)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("workspace.project_tasks", slug=slug))


@login_required
def project_members(slug):
    project = _project(slug)
    ctx, blocked = _ctx(project, "members")
    if blocked:
        return blocked
    pending_invites = []
    if ctx["can_manage"]:
        pending_invites = (
            ProjectInvite.query.filter_by(project_id=project.id, status="pending")
            .order_by(ProjectInvite.created_at.desc())
            .all()
        )
    invite_roles = ["contributor", "viewer"]
    if ctx["can_own"]:
        invite_roles = ["manager", "contributor", "viewer"]
    return render_template(
        "workspace/project_members.html",
        pending_invites=pending_invites,
        invite_roles=invite_roles,
        roles=PROJECT_ROLES,
        **ctx,
    )


@login_required
def project_invite(slug):
    project = _project(slug)
    if not can_manage(current_user, project):
        abort(403)
    username = (request.form.get("username") or "").strip().lstrip("@").lower()
    role = (request.form.get("role") or "contributor").strip().lower()
    allowed = {"contributor", "viewer"}
    if can_own(current_user, project):
        allowed.add("manager")
    if role not in allowed:
        flash("You cannot invite that role.", "error")
        return redirect(url_for("workspace.project_members", slug=slug))
    user = User.query.filter_by(username=username, status="active").first()
    if not user:
        flash("No active student with that username.", "error")
        return redirect(url_for("workspace.project_members", slug=slug))
    if user.id == current_user.id or project_membership(user, project):
        flash("They are already on the project.", "info")
        return redirect(url_for("workspace.project_members", slug=slug))
    existing = ProjectInvite.query.filter_by(project_id=project.id, invitee_id=user.id, status="pending").first()
    if existing:
        existing.role = role
    else:
        db.session.add(
            ProjectInvite(project_id=project.id, inviter_id=current_user.id, invitee_id=user.id, role=role)
        )
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
    return redirect(url_for("workspace.project_members", slug=slug))


@login_required
def project_invite_cancel(slug, invite_id):
    project = _project(slug)
    if not can_manage(current_user, project):
        abort(403)
    invite = ProjectInvite.query.filter_by(id=invite_id, project_id=project.id, status="pending").first_or_404()
    db.session.delete(invite)
    db.session.commit()
    flash("Invitation cancelled.", "success")
    return redirect(url_for("workspace.project_members", slug=slug))


@login_required
def project_respond(invite_id):
    invite = db.session.get(ProjectInvite, invite_id) or abort(404)
    if invite.invitee_id != current_user.id or invite.status != "pending":
        abort(403)
    decision = request.form.get("status")
    if decision not in {"accepted", "declined"}:
        abort(400)
    invite.status = decision
    project = invite.project
    if decision == "accepted" and not project_membership(current_user, project):
        role = invite.role if invite.role in {"manager", "contributor", "viewer"} else "contributor"
        db.session.add(ProjectMember(project_id=project.id, user_id=current_user.id, role=role))
        notify(
            invite.inviter_id,
            "project_invitation",
            f"{current_user.name} joined {project.name}",
            "",
            url_for("workspace.project_detail", slug=project.slug),
            actor_id=current_user.id,
        )
        _log(project, f"{current_user.name} joined the project")
        flash("You joined the project.", "success")
    else:
        flash("Invitation declined.", "info")
    db.session.commit()
    return redirect(url_for("workspace.project_detail", slug=project.slug))


@login_required
def project_member_role(slug, user_id):
    project = _project(slug)
    target = ProjectMember.query.filter_by(project_id=project.id, user_id=user_id).first_or_404()
    new_role = (request.form.get("role") or "").strip().lower()
    if new_role not in PROJECT_ROLES:
        abort(400)
    actor = project_membership(current_user, project)
    if not actor:
        abort(403)
    if new_role == "owner":
        if actor.role != "owner" or target.user_id == current_user.id:
            abort(403)
        actor.role = "manager"
        target.role = "owner"
        _log(project, f"{current_user.name} transferred ownership to {target.user.name}")
    elif actor.role == "owner":
        if target.role == "owner":
            flash("Transfer ownership before changing the owner role.", "error")
            return redirect(url_for("workspace.project_members", slug=slug))
        target.role = new_role
        _touch(project)
    elif actor.role == "manager" and target.role in {"contributor", "viewer"} and new_role in {"contributor", "viewer"}:
        target.role = new_role
        _touch(project)
    else:
        abort(403)
    db.session.commit()
    flash("Role updated.", "success")
    return redirect(url_for("workspace.project_members", slug=slug))


@login_required
def project_member_remove(slug, user_id):
    project = _project(slug)
    target = ProjectMember.query.filter_by(project_id=project.id, user_id=user_id).first_or_404()
    if not can_remove_member(current_user, project, target):
        abort(403)
    name = target.user.name
    removed_id = target.user_id
    db.session.delete(target)
    notify(
        removed_id,
        "project_invitation",
        f"Removed from {project.name}",
        f"{current_user.name} removed you from the project.",
        url_for("workspace.projects"),
        actor_id=current_user.id,
    )
    _log(project, f"{name} was removed from the project")
    db.session.commit()
    flash("Member removed.", "success")
    return redirect(url_for("workspace.project_members", slug=slug))


@login_required
def project_leave(slug):
    project = _project(slug)
    member = project_membership(current_user, project)
    if not member:
        abort(403)
    if member.role == "owner" and sum(1 for row in project.memberships if row.role == "owner") <= 1:
        flash("Transfer ownership or delete the project before leaving.", "error")
        return redirect(url_for("workspace.project_members", slug=slug))
    db.session.delete(member)
    _log(project, f"{current_user.name} left the project")
    db.session.commit()
    flash("You left the project.", "success")
    return redirect(url_for("workspace.projects"))


@login_required
def project_files(slug):
    project = _project(slug)
    if request.method == "POST":
        if not can_contribute(current_user, project):
            abort(403)
        folder = request.form.get("folder") or None
        item, error = store_upload(request.files.get("file"), current_user.id, project.id, folder=folder)
        if error:
            flash(error, "error")
            return redirect(url_for("workspace.project_files", slug=slug))
        db.session.add(item)
        _log(project, f"{current_user.name} uploaded {item.original_name}")
        db.session.commit()
        flash("File uploaded.", "success")
        return redirect(url_for("workspace.project_files", slug=slug, folder=item.folder))
    ctx, blocked = _work_ctx(project, "files")
    if blocked:
        return blocked
    folder = request.args.get("folder") or ""
    return render_template(
        "workspace/project_files.html",
        groups=_groups(project, folder or None),
        folders=FILE_FOLDERS,
        active_folder=folder if folder in FILE_FOLDERS else "",
        **ctx,
    )


@login_required
def project_file_download(slug, file_id):
    project = _project(slug)
    if not can_read_work(current_user, project):
        abort(403)
    item = FileItem.query.filter_by(id=file_id, project_id=project.id).first_or_404()
    name = safe_stored_name(item.stored_name)
    if not name:
        abort(404)
    return send_from_directory(
        current_app.config["FILE_FOLDER"],
        name,
        as_attachment=True,
        download_name=item.original_name,
    )


@login_required
def project_file_rename(slug, file_id):
    project = _project(slug)
    item = FileItem.query.filter_by(id=file_id, project_id=project.id).first_or_404()
    if not can_edit_file(current_user, project, item):
        abort(403)
    name = secure_filename(request.form.get("name") or "")
    ext = os.path.splitext(item.original_name)[1].lower()
    if name and ext and not name.lower().endswith(ext):
        name = f"{name}{ext}"[:180]
    if not name:
        flash("Enter a file name.", "error")
        return redirect(url_for("workspace.project_files", slug=slug))
    rows = FileItem.query.filter_by(project_id=project.id, group_key=item.group_key).all() if item.group_key else [item]
    for row in rows:
        row.original_name = name
    _touch(project)
    db.session.commit()
    flash("File renamed.", "success")
    return redirect(url_for("workspace.project_files", slug=slug))


@login_required
def project_file_version(slug, file_id):
    project = _project(slug)
    if not can_contribute(current_user, project):
        abort(403)
    source = FileItem.query.filter_by(id=file_id, project_id=project.id).first_or_404()
    if not source.group_key:
        source.group_key = source.stored_name
    current = (
        db.session.query(db.func.max(FileItem.version))
        .filter_by(project_id=project.id, group_key=source.group_key)
        .scalar()
        or source.version
        or 1
    )
    item, error = store_upload(
        request.files.get("file"),
        current_user.id,
        project.id,
        folder=source.folder,
        group_key=source.group_key or source.stored_name,
        version=current + 1,
    )
    if error:
        flash(error, "error")
        return redirect(url_for("workspace.project_files", slug=slug))
    db.session.add(item)
    _log(project, f"{current_user.name} uploaded {item.original_name}")
    db.session.commit()
    flash(f"Version {item.version} uploaded.", "success")
    return redirect(url_for("workspace.project_files", slug=slug))


@login_required
def project_file_delete(slug, file_id):
    project = _project(slug)
    item = FileItem.query.filter_by(id=file_id, project_id=project.id).first_or_404()
    if not can_edit_file(current_user, project, item):
        abort(403)
    rows = FileItem.query.filter_by(project_id=project.id, group_key=item.group_key).all() if item.group_key else [item]
    names = [row.stored_name for row in rows]
    for row in rows:
        db.session.delete(row)
    _touch(project)
    db.session.commit()
    for name in names:
        remove_stored_file(name)
    flash("File deleted.", "success")
    return redirect(url_for("workspace.project_files", slug=slug))


@login_required
def project_notes(slug):
    project = _project(slug)
    if request.method == "POST":
        if not can_contribute(current_user, project):
            abort(403)
        title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
        body, body_error = clip(request.form.get("body"), 20000, label="Note")
        if title_error or body_error:
            flash(title_error or body_error, "error")
            return redirect(url_for("workspace.project_notes", slug=slug))
        note = Note(user_id=current_user.id, project_id=project.id, title=title, body=body or "")
        db.session.add(note)
        _log(project, f"{current_user.name} created a note")
        db.session.commit()
        flash("Note saved.", "success")
        return redirect(url_for("workspace.project_notes", slug=slug))
    ctx, blocked = _work_ctx(project, "notes")
    if blocked:
        return blocked
    q = (request.args.get("q") or "").strip()
    query = Note.query.filter_by(project_id=project.id)
    if q:
        query = query.filter(contains(Note.title, q) | contains(Note.body, q))
    notes = query.order_by(Note.updated_at.desc()).all()
    return render_template("workspace/project_notes.html", notes=notes, q=q, **ctx)


@login_required
def project_note_update(slug, note_id):
    project = _project(slug)
    note = Note.query.filter_by(id=note_id, project_id=project.id).first_or_404()
    if not can_edit_note(current_user, project, note):
        abort(403)
    title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
    body, body_error = clip(request.form.get("body"), 20000, label="Note")
    if title_error or body_error:
        flash(title_error or body_error, "error")
        return redirect(url_for("workspace.project_notes", slug=slug))
    note.title = title
    note.body = body or ""
    note.updated_at = utcnow()
    _touch(project)
    db.session.commit()
    flash("Note updated.", "success")
    return redirect(url_for("workspace.project_notes", slug=slug))


@login_required
def project_note_delete(slug, note_id):
    project = _project(slug)
    note = Note.query.filter_by(id=note_id, project_id=project.id).first_or_404()
    if not can_edit_note(current_user, project, note):
        abort(403)
    db.session.delete(note)
    _touch(project)
    db.session.commit()
    flash("Note deleted.", "success")
    return redirect(url_for("workspace.project_notes", slug=slug))


@login_required
def project_discussions(slug):
    project = _project(slug)
    if request.method == "POST":
        if not can_contribute(current_user, project):
            abort(403)
        kind = (request.form.get("kind") or "discussion").strip().lower()
        title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
        body, body_error = clip(request.form.get("body"), 4000, required=True, label="Message")
        if kind not in DISCUSSION_KINDS:
            flash("Choose a discussion type.", "error")
            return redirect(url_for("workspace.project_discussions", slug=slug))
        if title_error or body_error:
            flash(title_error or body_error, "error")
            return redirect(url_for("workspace.project_discussions", slug=slug))
        db.session.add(
            ProjectDiscussion(
                project_id=project.id,
                author_id=current_user.id,
                kind=kind,
                title=title,
                body=body,
            )
        )
        link = url_for("workspace.project_discussions", slug=slug)
        for row in project.memberships:
            notify(
                row.user_id,
                "project_comment",
                f"New post in {project.name}",
                title,
                link,
                actor_id=current_user.id,
            )
        _touch(project)
        db.session.commit()
        flash("Posted to the project.", "success")
        return redirect(url_for("workspace.project_discussions", slug=slug))
    ctx, blocked = _ctx(project, "discussions")
    if blocked:
        return blocked
    kind = request.args.get("kind") or ""
    query = ProjectDiscussion.query.filter_by(project_id=project.id)
    if kind in DISCUSSION_KINDS:
        query = query.filter_by(kind=kind)
    rows = query.order_by(ProjectDiscussion.created_at.desc()).all()
    return render_template(
        "workspace/project_discussions.html",
        discussions=rows,
        kinds=DISCUSSION_KINDS,
        active_kind=kind if kind in DISCUSSION_KINDS else "",
        **ctx,
    )


@login_required
def project_discussion_delete(slug, discussion_id):
    project = _project(slug)
    item = ProjectDiscussion.query.filter_by(id=discussion_id, project_id=project.id).first_or_404()
    if item.author_id != current_user.id and not can_manage(current_user, project):
        abort(403)
    db.session.delete(item)
    _touch(project)
    db.session.commit()
    flash("Discussion removed.", "success")
    return redirect(url_for("workspace.project_discussions", slug=slug))


@login_required
def project_activity(slug):
    project = _project(slug)
    ctx, blocked = _ctx(project, "activity")
    if blocked:
        return blocked
    rows = Activity.query.filter_by(project_id=project.id).order_by(Activity.created_at.desc()).limit(80).all()
    return render_template("workspace/project_activity.html", rows=rows, **ctx)


@login_required
def project_settings(slug):
    project = _project(slug)
    ctx, blocked = _ctx(project, "settings")
    if blocked:
        return blocked
    if not can_manage(current_user, project):
        abort(403)
    errors = {}
    if request.method == "POST":
        name, name_error = clip(request.form.get("name"), 80, required=True, label="Name")
        description, desc_error = clip(request.form.get("description"), 2000, label="Description")
        category = request.form.get("category") or "Other"
        status = request.form.get("status") or project.status
        visibility = request.form.get("visibility") or project.visibility
        technologies, tech_error = clip(request.form.get("technologies"), 200, label="Technologies")
        repo_url, repo_error = clean_http_url(request.form.get("repo_url"), "Repository link")
        demo_url, demo_error = clean_http_url(request.form.get("demo_url"), "Demo link")
        if name_error:
            errors["name"] = name_error
        if desc_error:
            errors["description"] = desc_error
        if category not in PROJECT_CATEGORIES:
            errors["category"] = "Choose a category."
        if status not in PROJECT_STATUSES:
            errors["status"] = "Choose a status."
        if visibility not in PROJECT_VISIBILITY:
            errors["visibility"] = "Choose who can see this project."
        if tech_error:
            errors["technologies"] = tech_error
        if repo_error:
            errors["repo_url"] = repo_error
        if demo_error:
            errors["demo_url"] = demo_error
        if not errors:
            project.name = name
            project.description = description or ""
            project.category = category
            project.status = status
            project.visibility = visibility
            if "technologies" in request.form:
                project.technologies = technologies or ""
            if "repo_url" in request.form:
                project.repo_url = repo_url or ""
            if "demo_url" in request.form:
                project.demo_url = demo_url or ""
            if status != "Completed" and project.published:
                project.published = False
                project.published_at = None
            _touch(project)
            db.session.commit()
            flash("Project updated.", "success")
            return redirect(url_for("workspace.project_settings", slug=slug))
    return render_template(
        "workspace/project_settings.html",
        errors=errors,
        categories=PROJECT_CATEGORIES,
        statuses=PROJECT_STATUSES,
        **ctx,
    )


@login_required
def project_publish(slug):
    project = _project(slug)
    if not can_own(current_user, project):
        abort(403)
    if request.form.get("action") == "unpublish":
        project.published = False
        project.published_at = None
        _touch(project)
        flash("Removed from the public showcase.", "success")
    else:
        if project.status != "Completed":
            flash("Mark the project Completed before publishing it.", "error")
            return redirect(url_for("workspace.project_settings", slug=slug))
        project.published = True
        project.published_at = utcnow()
        _log(project, f"{current_user.name} published {project.name}")
        flash("Project published to your portfolio.", "success")
    db.session.commit()
    return redirect(url_for("workspace.project_settings", slug=slug))


@login_required
def project_delete(slug):
    project = _project(slug)
    if not can_own(current_user, project):
        abort(403)
    files = FileItem.query.filter_by(project_id=project.id).all()
    names = [item.stored_name for item in files]
    for item in files:
        db.session.delete(item)
    for note in Note.query.filter_by(project_id=project.id).all():
        db.session.delete(note)
    for row in Activity.query.filter_by(project_id=project.id).all():
        row.project_id = None
    for idea in Idea.query.filter_by(project_id=project.id).all():
        idea.project_id = None
    db.session.flush()
    name = project.name
    db.session.delete(project)
    log_activity(current_user.id, f"You deleted the project {name}.", url_for("workspace.projects"))
    db.session.commit()
    for stored in names:
        remove_stored_file(stored)
    flash("Project deleted.", "success")
    return redirect(url_for("workspace.projects"))


@login_required
def idea_start(idea_id):
    idea = db.session.get(Idea, idea_id) or abort(404)
    if idea.author_id != current_user.id:
        abort(403)
    if idea.project_id:
        existing = db.session.get(Project, idea.project_id)
        if existing:
            return redirect(url_for("workspace.project_detail", slug=existing.slug))
    description = (idea.description or "").strip()
    if idea.skills_needed:
        description = f"{description}\n\nSkills needed: {idea.skills_needed}".strip()
    project = Project(
        name=(idea.title or "Untitled project")[:80],
        slug=unique_slug(Project, idea.title or "project"),
        description=description[:2000],
        category="Other",
        status="Planning",
        visibility="private",
        creator_id=current_user.id,
    )
    db.session.add(project)
    db.session.flush()
    db.session.add(ProjectMember(project_id=project.id, user_id=current_user.id, role="owner"))
    idea.project_id = project.id
    invited = 0
    for interest in IdeaInterest.query.filter_by(idea_id=idea.id).all():
        if interest.user_id == current_user.id or project_membership(interest.user, project):
            continue
        pending = ProjectInvite.query.filter_by(
            project_id=project.id, invitee_id=interest.user_id, status="pending"
        ).first()
        if pending:
            continue
        db.session.add(
            ProjectInvite(
                project_id=project.id,
                inviter_id=current_user.id,
                invitee_id=interest.user_id,
                role="contributor",
            )
        )
        notify(
            interest.user_id,
            "project_invitation",
            f"Invitation to {project.name}",
            f"{current_user.name} turned an idea you liked into a project.",
            url_for("workspace.project_detail", slug=project.slug),
            actor_id=current_user.id,
        )
        invited += 1
    _log(project, f"{current_user.name} created the project")
    db.session.commit()
    if invited:
        flash("Project created from the idea. Interested students were invited.", "success")
    else:
        flash("Project created from the idea. It starts private.", "success")
    return redirect(url_for("workspace.project_detail", slug=project.slug))


def project_showcase():
    rows = (
        Project.query.filter_by(published=True)
        .order_by(Project.published_at.desc(), Project.updated_at.desc())
        .all()
    )
    return render_template("workspace/showcase.html", projects=rows)


def project_showcase_detail(slug):
    project = Project.query.filter_by(slug=slug, published=True).first_or_404()
    files = []
    if project.visibility == "public":
        files = (
            FileItem.query.filter_by(project_id=project.id)
            .order_by(FileItem.created_at.desc())
            .limit(8)
            .all()
        )
    return render_template("workspace/showcase_detail.html", project=project, stats=project_stats(project), files=files)


def project_showcase_file(slug, file_id):
    project = Project.query.filter_by(slug=slug, published=True, visibility="public").first_or_404()
    item = FileItem.query.filter_by(id=file_id, project_id=project.id).first_or_404()
    name = safe_stored_name(item.stored_name)
    if not name:
        abort(404)
    return send_from_directory(
        current_app.config["FILE_FOLDER"],
        name,
        as_attachment=not (item.mime or "").startswith("image/"),
        download_name=item.original_name,
    )


def register_project_routes(bp):
    bp.add_url_rule("/projects", "projects", projects)
    bp.add_url_rule("/projects/new", "project_new", project_new, methods=["GET", "POST"])
    bp.add_url_rule("/projects/<slug>", "project_detail", project_detail)
    bp.add_url_rule("/projects/<slug>/tasks", "project_tasks", project_tasks, methods=["GET", "POST"])
    bp.add_url_rule("/projects/<slug>/board", "project_board", project_board)
    bp.add_url_rule("/projects/<slug>/tasks/<int:task_id>/status", "task_status", task_status, methods=["POST"])
    bp.add_url_rule("/projects/<slug>/tasks/<int:task_id>/edit", "task_update", task_update, methods=["POST"])
    bp.add_url_rule("/projects/<slug>/tasks/<int:task_id>/delete", "task_delete", task_delete, methods=["POST"])
    bp.add_url_rule("/projects/<slug>/members", "project_members", project_members)
    bp.add_url_rule("/projects/<slug>/invite", "project_invite", project_invite, methods=["POST"])
    bp.add_url_rule(
        "/projects/<slug>/invites/<int:invite_id>/cancel",
        "project_invite_cancel",
        project_invite_cancel,
        methods=["POST"],
    )
    bp.add_url_rule("/project-invites/<int:invite_id>/respond", "project_respond", project_respond, methods=["POST"])
    bp.add_url_rule(
        "/projects/<slug>/members/<int:user_id>/role",
        "project_member_role",
        project_member_role,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/projects/<slug>/members/<int:user_id>/remove",
        "project_member_remove",
        project_member_remove,
        methods=["POST"],
    )
    bp.add_url_rule("/projects/<slug>/leave", "project_leave", project_leave, methods=["POST"])
    bp.add_url_rule("/projects/<slug>/files", "project_files", project_files, methods=["GET", "POST"])
    bp.add_url_rule("/projects/<slug>/files/<int:file_id>/download", "project_file_download", project_file_download)
    bp.add_url_rule(
        "/projects/<slug>/files/<int:file_id>/rename",
        "project_file_rename",
        project_file_rename,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/projects/<slug>/files/<int:file_id>/version",
        "project_file_version",
        project_file_version,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/projects/<slug>/files/<int:file_id>/delete",
        "project_file_delete",
        project_file_delete,
        methods=["POST"],
    )
    bp.add_url_rule("/projects/<slug>/notes", "project_notes", project_notes, methods=["GET", "POST"])
    bp.add_url_rule(
        "/projects/<slug>/notes/<int:note_id>/edit",
        "project_note_update",
        project_note_update,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/projects/<slug>/notes/<int:note_id>/delete",
        "project_note_delete",
        project_note_delete,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/projects/<slug>/discussions",
        "project_discussions",
        project_discussions,
        methods=["GET", "POST"],
    )
    bp.add_url_rule(
        "/projects/<slug>/discussions/<int:discussion_id>/delete",
        "project_discussion_delete",
        project_discussion_delete,
        methods=["POST"],
    )
    bp.add_url_rule("/projects/<slug>/activity", "project_activity", project_activity)
    bp.add_url_rule("/projects/<slug>/settings", "project_settings", project_settings, methods=["GET", "POST"])
    bp.add_url_rule("/projects/<slug>/publish", "project_publish", project_publish, methods=["POST"])
    bp.add_url_rule("/projects/<slug>/delete", "project_delete", project_delete, methods=["POST"])
    bp.add_url_rule("/ideas/<int:idea_id>/start", "idea_start", idea_start, methods=["POST"])
    bp.add_url_rule("/showcase", "project_showcase", project_showcase)
    bp.add_url_rule("/showcase/<slug>", "project_showcase_detail", project_showcase_detail)
    bp.add_url_rule("/showcase/<slug>/files/<int:file_id>", "project_showcase_file", project_showcase_file)
