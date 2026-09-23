import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.extensions import csrf, db, login_manager
from app.models import Notification, utcnow
from app.services import avatar_url, format_ago, format_dt, rich, unread_message_count
from config import CONFIGS


@event.listens_for(Engine, "connect")
def _sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app(config_name=None):
    config_name = config_name or os.environ.get("UNITYWORKS_CONFIG", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(CONFIGS[config_name])

    os.makedirs(app.instance_path, exist_ok=True)
    if config_name != "testing" and not os.environ.get("DATABASE_URL"):
        db_path = os.path.join(app.instance_path, "unityworks.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path

    avatar_dir = os.path.join(app.instance_path, "uploads", "avatars")
    file_dir = os.path.join(app.instance_path, "uploads", "files")
    os.makedirs(avatar_dir, exist_ok=True)
    os.makedirs(file_dir, exist_ok=True)
    app.config["AVATAR_FOLDER"] = avatar_dir
    app.config["FILE_FOLDER"] = file_dir

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes import register_blueprints

    register_blueprints(app)
    app.add_template_global(avatar_url, name="avatar_url")
    _register_handlers(app)

    with app.app_context():
        db.create_all()
        if not app.config.get("TESTING"):
            from app.seed import seed_if_empty

            seed_if_empty()

    return app


def _register_handlers(app):
    @app.before_request
    def guard_session():
        if request.endpoint == "static":
            return None
        if not current_user.is_authenticated:
            return None
        if current_user.status != "active":
            logout_user()
            session.clear()
            flash("This account is deactivated. Contact an administrator.", "error")
            return redirect(url_for("auth.login"))
        expires = session.get("expires_at")
        if expires:
            try:
                if utcnow() > datetime.fromisoformat(expires):
                    logout_user()
                    session.clear()
                    flash("Your session expired. Please sign in again.", "warning")
                    target = url_for("auth.login")
                    if request.method == "GET":
                        target = url_for("auth.login", next=request.path)
                    return redirect(target)
            except ValueError:
                session.pop("expires_at", None)
        return None

    @app.context_processor
    def inject_globals():
        counts = {"notifications": 0, "messages": 0}
        try:
            if current_user.is_authenticated:
                counts["notifications"] = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()
                counts["messages"] = unread_message_count(current_user)
        except Exception:
            app.logger.debug("nav counts unavailable", exc_info=True)
        return {
            "nav_counts": counts,
            "avatar_url": avatar_url,
            "app_name": app.config.get("APP_NAME", "UnityWorks"),
        }

    @app.template_filter("dt")
    def _dt(value):
        return format_dt(value)

    @app.template_filter("ago")
    def _ago(value):
        return format_ago(value)

    @app.template_filter("rich")
    def _rich(value):
        return rich(value)

    @app.template_global()
    def page_url(page):
        args = request.args.to_dict(flat=True)
        args["page"] = page
        view_args = request.view_args or {}
        return url_for(request.endpoint, **view_args, **args)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def missing(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def crashed(e):
        app.logger.exception(e)
        return render_template("errors/500.html"), 500

    @app.errorhandler(413)
    def too_large(_e):
        flash("That file is too large. Maximum size is 16 MB.", "error")
        return redirect(request.referrer or url_for("main.landing"))

    @app.errorhandler(CSRFError)
    def csrf_failed(_e):
        flash("Your session token expired. Please try again.", "warning")
        return redirect(request.referrer or url_for("main.landing"))
