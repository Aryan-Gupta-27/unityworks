from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constants import COMMUNITY_CATEGORIES
from app.extensions import db
from app.models import (
    Comment,
    Community,
    CommunityInvitation,
    CommunityMember,
    Post,
    ProjectInvite,
    Reaction,
    User,
)
from app.services import (
    can_edit_community,
    can_moderate,
    can_participate,
    can_view_community,
    contains,
    like_count,
    log_activity,
    membership_of,
    notify,
    unique_slug,
    user_liked,
)
from app.validators import clip

communities_bp = Blueprint("communities", __name__)


def _community(slug):
    return Community.query.filter_by(slug=slug).first_or_404()


def _list(kind):
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    query = Community.query.filter_by(kind=kind)
    if q:
        query = query.filter(contains(Community.name, q) | contains(Community.description, q))
    if category in COMMUNITY_CATEGORIES:
        query = query.filter_by(category=category)
    if not current_user.is_authenticated:
        query = query.filter_by(visibility="public")
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Community.created_at.desc()).paginate(page=page, per_page=9, error_out=False)
    joined = set()
    if current_user.is_authenticated:
        joined = {
            m.community_id
            for m in CommunityMember.query.filter_by(user_id=current_user.id).all()
        }
    return render_template(
        "communities/list.html",
        pagination=pagination,
        kind=kind,
        q=q,
        category=category,
        categories=COMMUNITY_CATEGORIES,
        joined=joined,
    )


@communities_bp.route("/communities")
def index():
    return _list("community")


@communities_bp.route("/groups")
def groups():
    return _list("group")


@communities_bp.route("/communities/new", methods=["GET", "POST"])
@login_required
def create():
    kind = request.values.get("kind", "community")
    if kind not in {"community", "group"}:
        kind = "community"
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name, name_error = clip(form.get("name"), 80, required=True, label="Name")
        description, desc_error = clip(form.get("description"), 1000, required=True, label="Description")
        category = (form.get("category") or "").strip()
        visibility = (form.get("visibility") or "public").strip()
        kind = form.get("kind") if form.get("kind") in {"community", "group"} else "community"
        if name_error:
            errors["name"] = name_error
        if desc_error:
            errors["description"] = desc_error
        if len(name or "") < 3:
            errors["name"] = "Use at least 3 characters."
        if category not in COMMUNITY_CATEGORIES:
            errors["category"] = "Choose a category."
        if visibility not in {"public", "private"}:
            errors["visibility"] = "Choose public or private."
        if not errors:
            community = Community(
                name=name,
                slug=unique_slug(Community, name),
                description=description,
                category=category,
                kind=kind,
                visibility=visibility,
                creator_id=current_user.id,
            )
            db.session.add(community)
            db.session.flush()
            db.session.add(
                CommunityMember(community_id=community.id, user_id=current_user.id, role="owner")
            )
            label = community.kind_label.lower()
            log_activity(
                current_user.id,
                f"You created the {label} {community.name}.",
                url_for("communities.detail", slug=community.slug),
            )
            db.session.commit()
            flash(f"{community.kind_label} created.", "success")
            return redirect(url_for("communities.detail", slug=community.slug))
    return render_template(
        "communities/form.html",
        errors=errors,
        form=form,
        kind=kind,
        categories=COMMUNITY_CATEGORIES,
        community=None,
    )


@communities_bp.route("/communities/<slug>")
@login_required
def detail(slug):
    community = _community(slug)
    member = membership_of(current_user, community)
    if not can_view_community(current_user, community):
        return render_template("communities/locked.html", community=community, member=None), 200
    posts = Post.query.filter_by(community_id=community.id).order_by(Post.created_at.desc()).limit(30).all()
    post_meta = {p.id: {"likes": like_count(p), "liked": user_liked(p, current_user), "comments": len(p.comments)} for p in posts}
    requests = []
    if can_edit_community(current_user, community):
        requests = CommunityInvitation.query.filter_by(
            community_id=community.id, kind="request", status="pending"
        ).all()
    return render_template(
        "communities/detail.html",
        community=community,
        member=member,
        posts=posts,
        post_meta=post_meta,
        requests=requests,
        can_edit=can_edit_community(current_user, community),
        can_moderate=can_moderate(current_user, community),
    )


@communities_bp.route("/communities/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    community = _community(slug)
    if not can_edit_community(current_user, community):
        abort(403)
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name, name_error = clip(form.get("name"), 80, required=True, label="Name")
        description, desc_error = clip(form.get("description"), 1000, required=True, label="Description")
        category = (form.get("category") or "").strip()
        visibility = (form.get("visibility") or "public").strip()
        if name_error:
            errors["name"] = name_error
        if desc_error:
            errors["description"] = desc_error
        if category not in COMMUNITY_CATEGORIES:
            errors["category"] = "Choose a category."
        if visibility not in {"public", "private"}:
            errors["visibility"] = "Choose public or private."
        transfer_id = request.form.get("transfer_to", type=int)
        if not errors:
            community.name = name
            community.description = description
            community.category = category
            community.visibility = visibility
            if community.slug != slugify_keep(community, name):
                community.slug = unique_slug(Community, name, exclude_id=community.id)
            if transfer_id and transfer_id != current_user.id:
                target = CommunityMember.query.filter_by(community_id=community.id, user_id=transfer_id).first()
                owner = membership_of(current_user, community)
                if target and owner and owner.role == "owner":
                    target.role = "owner"
                    owner.role = "moderator"
                    notify(
                        target.user_id,
                        "community_invitation",
                        f"You are now owner of {community.name}",
                        "Ownership was transferred to you.",
                        url_for("communities.detail", slug=community.slug),
                        actor_id=current_user.id,
                    )
            db.session.commit()
            flash("Community updated.", "success")
            return redirect(url_for("communities.detail", slug=community.slug))
    members = CommunityMember.query.filter_by(community_id=community.id).all()
    return render_template(
        "communities/form.html",
        errors=errors,
        form=form,
        kind=community.kind,
        categories=COMMUNITY_CATEGORIES,
        community=community,
        members=members,
    )


def slugify_keep(community, name):
    from app.services import slugify

    return slugify(name)


@communities_bp.route("/communities/<slug>/delete", methods=["POST"])
@login_required
def delete(slug):
    community = _community(slug)
    if not can_edit_community(current_user, community):
        abort(403)
    kind = community.kind
    db.session.delete(community)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(url_for("communities.groups" if kind == "group" else "communities.index"))


@communities_bp.route("/communities/<slug>/join", methods=["POST"])
@login_required
def join(slug):
    community = _community(slug)
    if membership_of(current_user, community):
        flash("You are already a member.", "info")
        return redirect(url_for("communities.detail", slug=slug))
    if community.is_private:
        existing = CommunityInvitation.query.filter_by(
            community_id=community.id, inviter_id=current_user.id, kind="request", status="pending"
        ).first()
        if not existing:
            owner = CommunityMember.query.filter_by(community_id=community.id, role="owner").first()
            invite = CommunityInvitation(
                community_id=community.id,
                inviter_id=current_user.id,
                invitee_id=owner.user_id if owner else community.creator_id,
                kind="request",
                message=(request.form.get("message") or "")[:240],
            )
            db.session.add(invite)
            notify(
                owner.user_id if owner else community.creator_id,
                "community_invitation",
                f"{current_user.name} requested to join {community.name}",
                invite.message,
                url_for("communities.detail", slug=community.slug),
                actor_id=current_user.id,
            )
            db.session.commit()
        flash("Request sent to the owner.", "success")
        return redirect(url_for("communities.detail", slug=slug))
    db.session.add(CommunityMember(community_id=community.id, user_id=current_user.id, role="member"))
    log_activity(current_user.id, f"You joined {community.name}.", url_for("communities.detail", slug=slug))
    owner = CommunityMember.query.filter_by(community_id=community.id, role="owner").first()
    if owner:
        notify(
            owner.user_id,
            "community_invitation",
            f"{current_user.name} joined {community.name}",
            "",
            url_for("communities.detail", slug=slug),
            actor_id=current_user.id,
        )
    db.session.commit()
    flash(f"Welcome to {community.name}.", "success")
    return redirect(url_for("communities.detail", slug=slug))


@communities_bp.route("/communities/<slug>/leave", methods=["POST"])
@login_required
def leave(slug):
    community = _community(slug)
    member = membership_of(current_user, community)
    if not member:
        abort(403)
    if member.role == "owner":
        others = CommunityMember.query.filter(
            CommunityMember.community_id == community.id, CommunityMember.user_id != current_user.id
        ).count()
        if others:
            flash("Transfer ownership before leaving.", "error")
            return redirect(url_for("communities.edit", slug=slug))
        db.session.delete(community)
        db.session.commit()
        flash("You left and the empty community was removed.", "success")
        return redirect(url_for("communities.index"))
    db.session.delete(member)
    log_activity(current_user.id, f"You left {community.name}.", url_for("communities.detail", slug=slug))
    db.session.commit()
    flash(f"You left {community.name}.", "success")
    return redirect(url_for("communities.index"))


@communities_bp.route("/communities/<slug>/members")
@login_required
def members(slug):
    community = _community(slug)
    if not can_view_community(current_user, community):
        abort(403)
    rows = (
        CommunityMember.query.filter_by(community_id=community.id)
        .join(User)
        .order_by(CommunityMember.joined_at.asc())
        .all()
    )
    return render_template(
        "communities/members.html",
        community=community,
        rows=rows,
        member=membership_of(current_user, community),
        can_edit=can_edit_community(current_user, community),
        can_moderate=can_moderate(current_user, community),
    )


@communities_bp.route("/communities/<slug>/members/<int:user_id>/role", methods=["POST"])
@login_required
def set_role(slug, user_id):
    community = _community(slug)
    if not can_edit_community(current_user, community):
        abort(403)
    role = request.form.get("role")
    if role not in {"moderator", "member"}:
        abort(400)
    target = CommunityMember.query.filter_by(community_id=community.id, user_id=user_id).first_or_404()
    if target.role == "owner":
        abort(403)
    target.role = role
    notify(
        target.user_id,
        "community_invitation",
        f"Your role in {community.name} is now {role}",
        "",
        url_for("communities.detail", slug=slug),
        actor_id=current_user.id,
    )
    db.session.commit()
    flash("Role updated.", "success")
    return redirect(url_for("communities.members", slug=slug))


@communities_bp.route("/communities/<slug>/members/<int:user_id>/remove", methods=["POST"])
@login_required
def remove_member(slug, user_id):
    community = _community(slug)
    actor = membership_of(current_user, community)
    if not actor or actor.role != "owner":
        if not (current_user.is_admin):
            abort(403)
    target = CommunityMember.query.filter_by(community_id=community.id, user_id=user_id).first_or_404()
    if target.role == "owner":
        abort(403)
    db.session.delete(target)
    notify(
        target.user_id,
        "community_invitation",
        f"You were removed from {community.name}",
        "",
        url_for("communities.index"),
        actor_id=current_user.id,
    )
    db.session.commit()
    flash("Member removed.", "success")
    return redirect(url_for("communities.members", slug=slug))


@communities_bp.route("/communities/<slug>/invite", methods=["POST"])
@login_required
def invite(slug):
    community = _community(slug)
    actor = membership_of(current_user, community)
    if not actor or actor.role not in {"owner", "moderator"}:
        if not current_user.is_admin:
            abort(403)
    username = (request.form.get("username") or "").strip().lower()
    user = User.query.filter_by(username=username, status="active").first()
    if not user:
        flash("No active student with that username.", "error")
        return redirect(url_for("communities.members", slug=slug))
    if membership_of(user, community):
        flash("They are already a member.", "info")
        return redirect(url_for("communities.members", slug=slug))
    existing = CommunityInvitation.query.filter_by(
        community_id=community.id, invitee_id=user.id, kind="invite", status="pending"
    ).first()
    if existing:
        flash("An invitation is already pending.", "info")
        return redirect(url_for("communities.members", slug=slug))
    message = (request.form.get("message") or "")[:240]
    db.session.add(
        CommunityInvitation(
            community_id=community.id,
            inviter_id=current_user.id,
            invitee_id=user.id,
            kind="invite",
            message=message,
        )
    )
    notify(
        user.id,
        "community_invitation",
        f"Invitation to {community.name}",
        message or f"{current_user.name} invited you.",
        url_for("communities.invitations"),
        actor_id=current_user.id,
    )
    db.session.commit()
    flash(f"Invitation sent to {user.name}.", "success")
    return redirect(url_for("communities.members", slug=slug))


@communities_bp.route("/invitations")
@login_required
def invitations():
    incoming = CommunityInvitation.query.filter_by(invitee_id=current_user.id, status="pending", kind="invite").all()
    requests = (
        CommunityInvitation.query.filter_by(status="pending", kind="request")
        .join(Community)
        .join(CommunityMember, CommunityMember.community_id == Community.id)
        .filter(CommunityMember.user_id == current_user.id, CommunityMember.role == "owner")
        .all()
    )
    project_invites = ProjectInvite.query.filter_by(invitee_id=current_user.id, status="pending").all()
    return render_template(
        "communities/invitations.html",
        incoming=incoming,
        requests=requests,
        project_invites=project_invites,
    )


@communities_bp.route("/invitations/<int:invite_id>/respond", methods=["POST"])
@login_required
def respond_invite(invite_id):
    invite = db.session.get(CommunityInvitation, invite_id)
    if not invite or invite.status != "pending":
        abort(404)
    decision = request.form.get("status")
    if decision not in {"accepted", "declined"}:
        abort(400)
    if invite.kind == "invite":
        if invite.invitee_id != current_user.id:
            abort(403)
        invite.status = decision
        if decision == "accepted" and not membership_of(current_user, invite.community):
            db.session.add(
                CommunityMember(community_id=invite.community_id, user_id=current_user.id, role="member")
            )
            log_activity(
                current_user.id,
                f"You joined {invite.community.name}.",
                url_for("communities.detail", slug=invite.community.slug),
            )
            notify(
                invite.inviter_id,
                "community_invitation",
                f"{current_user.name} accepted your invitation",
                invite.community.name,
                url_for("communities.detail", slug=invite.community.slug),
                actor_id=current_user.id,
            )
        db.session.commit()
        flash("Invitation updated.", "success")
        if decision == "accepted":
            return redirect(url_for("communities.detail", slug=invite.community.slug))
        return redirect(url_for("communities.invitations"))
    if not can_edit_community(current_user, invite.community):
        abort(403)
    invite.status = decision
    if decision == "accepted" and not membership_of(invite.inviter, invite.community):
        db.session.add(
            CommunityMember(community_id=invite.community_id, user_id=invite.inviter_id, role="member")
        )
        notify(
            invite.inviter_id,
            "community_invitation",
            f"You were accepted into {invite.community.name}",
            "",
            url_for("communities.detail", slug=invite.community.slug),
            actor_id=current_user.id,
        )
    db.session.commit()
    flash("Request updated.", "success")
    return redirect(url_for("communities.detail", slug=invite.community.slug))


@communities_bp.route("/communities/<slug>/posts", methods=["POST"])
@login_required
def create_post(slug):
    community = _community(slug)
    if not can_participate(current_user, community):
        abort(403)
    title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
    body, body_error = clip(request.form.get("body"), 5000, required=True, label="Post")
    if title_error or body_error:
        flash(title_error or body_error, "error")
        return redirect(url_for("communities.detail", slug=slug))
    post = Post(community_id=community.id, author_id=current_user.id, title=title, body=body)
    db.session.add(post)
    db.session.flush()
    link = url_for("communities.post_detail", slug=slug, post_id=post.id)
    log_activity(current_user.id, f"You posted in {community.name}.", link)
    db.session.commit()
    flash("Post published.", "success")
    return redirect(link)


@communities_bp.route("/communities/<slug>/posts/<int:post_id>")
@login_required
def post_detail(slug, post_id):
    community = _community(slug)
    if not can_view_community(current_user, community):
        abort(403)
    post = Post.query.filter_by(id=post_id, community_id=community.id).first_or_404()
    return render_template(
        "communities/post.html",
        community=community,
        post=post,
        member=membership_of(current_user, community),
        likes=like_count(post),
        liked=user_liked(post, current_user),
        can_moderate=can_moderate(current_user, community),
    )


@communities_bp.route("/posts/<int:post_id>/edit", methods=["POST"])
@login_required
def edit_post(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    if post.author_id != current_user.id:
        abort(403)
    title, title_error = clip(request.form.get("title"), 140, required=True, label="Title")
    body, body_error = clip(request.form.get("body"), 5000, required=True, label="Post")
    if title_error or body_error:
        flash(title_error or body_error, "error")
        return redirect(url_for("communities.post_detail", slug=post.community.slug, post_id=post.id))
    post.title = title
    post.body = body
    db.session.commit()
    flash("Post updated.", "success")
    return redirect(url_for("communities.post_detail", slug=post.community.slug, post_id=post.id))


@communities_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    if post.author_id != current_user.id and not can_moderate(current_user, post.community):
        abort(403)
    slug = post.community.slug
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "success")
    return redirect(url_for("communities.detail", slug=slug))


@communities_bp.route("/posts/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    if not can_participate(current_user, post.community):
        abort(403)
    existing = Reaction.query.filter_by(user_id=current_user.id, post_id=post.id).filter(
        Reaction.comment_id.is_(None)
    ).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Reaction(user_id=current_user.id, post_id=post.id, kind="like"))
    db.session.commit()
    return redirect(request.referrer or url_for("communities.post_detail", slug=post.community.slug, post_id=post.id))


@communities_bp.route("/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def comment(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    if not can_participate(current_user, post.community):
        abort(403)
    body, body_error = clip(request.form.get("body"), 2000, required=True, label="Comment")
    if body_error:
        flash(body_error, "error")
        return redirect(url_for("communities.post_detail", slug=post.community.slug, post_id=post.id))
    item = Comment(post_id=post.id, author_id=current_user.id, body=body)
    db.session.add(item)
    link = url_for("communities.post_detail", slug=post.community.slug, post_id=post.id)
    notify(
        post.author_id,
        "comment",
        f"{current_user.name} commented on your post",
        body[:180],
        link,
        actor_id=current_user.id,
    )
    log_activity(post.author_id, f"{current_user.name} commented on {post.title}.", link)
    log_activity(current_user.id, f"You commented in {post.community.name}.", link)
    db.session.commit()
    flash("Comment added.", "success")
    return redirect(link)


@communities_bp.route("/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    item = db.session.get(Comment, comment_id) or abort(404)
    if item.author_id != current_user.id and not can_moderate(current_user, item.post.community):
        abort(403)
    slug = item.post.community.slug
    post_id = item.post_id
    db.session.delete(item)
    db.session.commit()
    flash("Comment deleted.", "success")
    return redirect(url_for("communities.post_detail", slug=slug, post_id=post_id))
