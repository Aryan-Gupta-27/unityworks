"""Add columns the live SQLite file is missing. create_all() will not do this."""

from sqlalchemy import inspect, text

from app.extensions import db


def upgrade_schema():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    def columns(table):
        if table not in tables:
            return set()
        return {col["name"] for col in inspector.get_columns(table)}

    def add(table, name, ddl):
        if table in tables and name not in columns(table):
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

    add("projects", "category", "TEXT DEFAULT 'Other'")
    add("projects", "visibility", "TEXT DEFAULT 'public'")
    add("projects", "published", "INTEGER DEFAULT 0")
    add("projects", "published_at", "DATETIME")
    add("tasks", "description", "TEXT DEFAULT ''")
    add("tasks", "priority", "TEXT DEFAULT 'Medium'")
    add("tasks", "deadline", "DATETIME")
    add("tasks", "updated_at", "DATETIME")
    add("notes", "project_id", "INTEGER")
    add("files", "project_id", "INTEGER")
    add("files", "folder", "TEXT DEFAULT 'Other'")
    add("files", "group_key", "TEXT DEFAULT ''")
    add("files", "version", "INTEGER DEFAULT 1")
    add("activities", "project_id", "INTEGER")
    add("project_invites", "role", "TEXT DEFAULT 'contributor'")
    add("ideas", "project_id", "INTEGER")
    add("users", "certifications", "TEXT DEFAULT ''")
    add("users", "honors", "TEXT DEFAULT ''")
    add("users", "experience_note", "TEXT DEFAULT ''")
    add("users", "mentor_role", "TEXT DEFAULT ''")
    add("users", "profile_public", "INTEGER DEFAULT 0")
    add("users", "public_sections", "TEXT DEFAULT ''")
    add("projects", "technologies", "TEXT DEFAULT ''")
    add("projects", "repo_url", "TEXT DEFAULT ''")
    add("projects", "demo_url", "TEXT DEFAULT ''")
    add("academic_resources", "kind", "TEXT DEFAULT 'Study Resource'")
    add("academic_resources", "tags", "TEXT DEFAULT ''")
    add("academic_resources", "stored_name", "TEXT DEFAULT ''")
    add("academic_resources", "original_name", "TEXT DEFAULT ''")
    add("academic_resources", "size", "INTEGER DEFAULT 0")
    add("questions", "subject", "TEXT DEFAULT ''")
    add("answers", "accepted", "INTEGER DEFAULT 0")
    add("answers", "updated_at", "DATETIME")
    add("events", "category", "TEXT DEFAULT 'Event'")
    add("events", "registration_link", "TEXT DEFAULT ''")
    add("users", "muted_notifications", "TEXT DEFAULT ''")
    add("activities", "area", "TEXT DEFAULT 'system'")
    db.session.commit()

    if "tasks" in tables:
        db.session.execute(text("UPDATE tasks SET status = 'TODO' WHERE status IN ('To do', 'todo', 'TODO')"))
        db.session.execute(
            text("UPDATE tasks SET status = 'IN PROGRESS' WHERE status IN ('In progress', 'Doing', 'IN PROGRESS')")
        )
        db.session.execute(text("UPDATE tasks SET status = 'REVIEW' WHERE status IN ('Review', 'REVIEW')"))
        db.session.execute(text("UPDATE tasks SET status = 'DONE' WHERE status IN ('Done', 'DONE')"))
        db.session.execute(text("UPDATE tasks SET priority = 'Medium' WHERE priority IS NULL OR priority = ''"))
        db.session.execute(text("UPDATE tasks SET description = '' WHERE description IS NULL"))
        db.session.execute(text("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL"))
    if "projects" in tables:
        db.session.execute(text("UPDATE projects SET status = 'Planning' WHERE status = 'On hold'"))
        db.session.execute(text("UPDATE projects SET category = 'Other' WHERE category IS NULL OR category = ''"))
        db.session.execute(text("UPDATE projects SET visibility = 'public' WHERE visibility IS NULL OR visibility = ''"))
        db.session.execute(text("UPDATE projects SET published = 0 WHERE published IS NULL"))
    if "project_members" in tables:
        db.session.execute(text("UPDATE project_members SET role = 'contributor' WHERE role = 'member'"))
    if "project_invites" in tables:
        db.session.execute(
            text("UPDATE project_invites SET role = 'contributor' WHERE role IS NULL OR role = ''")
        )
    if "files" in tables:
        db.session.execute(text("UPDATE files SET folder = 'Other' WHERE folder IS NULL OR folder = ''"))
        db.session.execute(text("UPDATE files SET version = 1 WHERE version IS NULL OR version = 0"))
        db.session.execute(
            text("UPDATE files SET group_key = stored_name WHERE group_key IS NULL OR group_key = ''")
        )
    if "users" in tables:
        db.session.execute(text("UPDATE users SET certifications = '' WHERE certifications IS NULL"))
        db.session.execute(text("UPDATE users SET honors = '' WHERE honors IS NULL"))
        db.session.execute(text("UPDATE users SET experience_note = '' WHERE experience_note IS NULL"))
        db.session.execute(text("UPDATE users SET mentor_role = '' WHERE mentor_role IS NULL"))
        db.session.execute(text("UPDATE users SET profile_public = 0 WHERE profile_public IS NULL"))
        db.session.execute(text("UPDATE users SET public_sections = '' WHERE public_sections IS NULL"))
        db.session.execute(text("UPDATE users SET muted_notifications = '' WHERE muted_notifications IS NULL"))
    if "academic_resources" in tables:
        db.session.execute(
            text("UPDATE academic_resources SET kind = 'Study Resource' WHERE kind IS NULL OR kind = ''")
        )
        db.session.execute(text("UPDATE academic_resources SET tags = '' WHERE tags IS NULL"))
        db.session.execute(text("UPDATE academic_resources SET stored_name = '' WHERE stored_name IS NULL"))
        db.session.execute(text("UPDATE academic_resources SET original_name = '' WHERE original_name IS NULL"))
    if "answers" in tables:
        db.session.execute(text("UPDATE answers SET accepted = 0 WHERE accepted IS NULL"))
    if "events" in tables:
        db.session.execute(text("UPDATE events SET category = 'Event' WHERE category IS NULL OR category = ''"))
        db.session.execute(text("UPDATE events SET registration_link = '' WHERE registration_link IS NULL"))
    if "projects" in tables:
        db.session.execute(text("UPDATE projects SET technologies = '' WHERE technologies IS NULL"))
        db.session.execute(text("UPDATE projects SET repo_url = '' WHERE repo_url IS NULL"))
        db.session.execute(text("UPDATE projects SET demo_url = '' WHERE demo_url IS NULL"))
    if "activities" in tables:
        db.session.execute(text("UPDATE activities SET area = 'system' WHERE area IS NULL OR area = ''"))
        db.session.execute(
            text("UPDATE activities SET area = 'project' WHERE project_id IS NOT NULL OR link LIKE '/projects%'")
        )
        db.session.execute(
            text(
                "UPDATE activities SET area = 'community' "
                "WHERE link LIKE '/communities%' OR link LIKE '/groups%' OR link LIKE '/clubs%'"
            )
        )
        db.session.execute(
            text(
                "UPDATE activities SET area = 'academic' "
                "WHERE link LIKE '/academics%' OR link LIKE '/questions%'"
            )
        )
        db.session.execute(
            text(
                "UPDATE activities SET area = 'portfolio' "
                "WHERE link LIKE '/profile%' OR link LIKE '/showcase%' OR link LIKE '/u/%'"
            )
        )
    db.session.commit()
    if "tasks" in tables:
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_assignee ON tasks (assignee_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_deadline ON tasks (deadline)"))
    if "activities" in tables:
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_activities_area ON activities (area)"))
    db.session.commit()
