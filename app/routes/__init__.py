def register_blueprints(app):
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.communities import communities_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.discover import discover_bp
    from app.routes.main import main_bp
    from app.routes.messages import messages_bp
    from app.routes.notifications import notifications_bp
    from app.routes.profile import profile_bp
    from app.routes.search import search_bp
    from app.routes.workspace import workspace_bp

    for bp in (
        main_bp,
        auth_bp,
        dashboard_bp,
        profile_bp,
        admin_bp,
        communities_bp,
        messages_bp,
        notifications_bp,
        search_bp,
        discover_bp,
        workspace_bp,
    ):
        app.register_blueprint(bp)
