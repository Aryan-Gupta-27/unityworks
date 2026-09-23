from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from app.extensions import db
from app.models import User, utcnow
from app.services import log_activity, safe_next
from app.validators import clean_email, clean_name, clean_password, clean_username

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name, name_error = clean_name(form.get("name"))
        username, username_error = clean_username(form.get("username"))
        email, email_error = clean_email(form.get("email"))
        password, password_error = clean_password(form.get("password"), form.get("confirm"))
        if name_error:
            errors["name"] = name_error
        if username_error:
            errors["username"] = username_error
        if email_error:
            errors["email"] = email_error
        if password_error:
            errors["password"] = password_error
        if username and User.query.filter(User.username == username).first():
            errors["username"] = "That username is already taken."
        if email and User.query.filter(User.email == email).first():
            errors["email"] = "An account with that email already exists."
        if not errors:
            user = User(name=name, username=username, email=email, role="student", status="active")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            log_activity(user.id, "You joined UnityWorks.", url_for("dashboard.index"))
            db.session.commit()
            _start_session(user, remember=False)
            flash("Welcome to UnityWorks. Your study life starts here.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/register.html", errors=errors, form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(safe_next(request.args.get("next")) or url_for("dashboard.index"))
    errors = {}
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        identifier = (form.get("identifier") or "").strip()
        password = form.get("password") or ""
        if not identifier or not password:
            errors["form"] = "Enter your email or username and your password."
        else:
            user = User.query.filter(
                or_(User.email == identifier.lower(), User.username == identifier.lower())
            ).first()
            if not user or not user.check_password(password):
                errors["form"] = "Those credentials don't match our records."
            elif user.status != "active":
                errors["form"] = "This account is deactivated. Contact an administrator."
            else:
                _start_session(user, remember=form.get("remember") == "on")
                flash(f"Welcome back, {user.first_name}.", "success")
                return redirect(safe_next(form.get("next") or request.args.get("next")) or url_for("dashboard.index"))
    return render_template("auth/login.html", errors=errors, form=form, next=request.args.get("next", ""))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("main.landing"))


def _start_session(user, remember):
    session.clear()
    login_user(user, remember=remember)
    session.permanent = True
    from flask import current_app

    lifetime = current_app.config["PERMANENT_SESSION_LIFETIME"]
    if remember:
        lifetime = timedelta(days=current_app.config.get("REMEMBER_DAYS", 14))
    session["login_at"] = utcnow().isoformat()
    session["expires_at"] = (utcnow() + lifetime).isoformat()
