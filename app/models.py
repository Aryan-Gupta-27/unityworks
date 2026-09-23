from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    headline = db.Column(db.String(140), default="")
    bio = db.Column(db.Text, default="")
    skills = db.Column(db.String(300), default="")
    education = db.Column(db.String(200), default="")
    interests = db.Column(db.String(300), default="")
    college = db.Column(db.String(140), default="", index=True)
    program = db.Column(db.String(120), default="")
    academic_year = db.Column(db.String(40), default="")
    experience = db.Column(db.String(40), default="", index=True)
    certifications = db.Column(db.String(400), default="")
    honors = db.Column(db.String(400), default="")
    experience_note = db.Column(db.String(400), default="")
    mentor_role = db.Column(db.String(20), default="", index=True)
    profile_public = db.Column(db.Boolean, nullable=False, default=False)
    public_sections = db.Column(db.String(200), default="")
    muted_notifications = db.Column(db.String(120), default="")
    avatar = db.Column(db.String(180), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    memberships = db.relationship("CommunityMember", back_populates="user", cascade="all, delete-orphan")
    participations = db.relationship(
        "ConversationParticipant", back_populates="user", cascade="all, delete-orphan"
    )
    notifications = db.relationship(
        "Notification",
        foreign_keys="Notification.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_active_account(self):
        return self.status == "active"

    @property
    def first_name(self):
        return (self.name or "").split(" ")[0]

    @property
    def initials(self):
        parts = [p for p in (self.name or "").split() if p]
        if not parts:
            return (self.username or "?")[:2].upper()
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    def hue(self):
        return sum(ord(c) for c in self.username or "u") % 360

    @property
    def skill_list(self):
        return [s.strip() for s in (self.skills or "").split(",") if s.strip()]

    @property
    def interest_list(self):
        return [s.strip() for s in (self.interests or "").split(",") if s.strip()]

    @property
    def mentor_label(self):
        return {"mentor": "Mentor", "mentee": "Mentee", "both": "Mentor and mentee"}.get(self.mentor_role, "")

    @property
    def shared_sections(self):
        return {part.strip() for part in (self.public_sections or "").split(",") if part.strip()}

    def shares(self, section):
        return bool(self.profile_public and section in self.shared_sections)

    @property
    def muted_set(self):
        return {part.strip() for part in (self.muted_notifications or "").split(",") if part.strip()}

    @property
    def profile_incomplete(self):
        return not (self.bio and self.skills and self.college)

    def __repr__(self):
        return f"<User {self.username}>"


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    summary = db.Column(db.String(240), nullable=False)
    link = db.Column(db.String(240), default="")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    area = db.Column(db.String(20), nullable=False, default="system", index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    user = db.relationship("User")
    project = db.relationship("Project", back_populates="activities")


class Community(db.Model):
    __tablename__ = "communities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(60), default="Other", index=True)
    kind = db.Column(db.String(20), nullable=False, default="community", index=True)
    visibility = db.Column(db.String(20), nullable=False, default="public")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator = db.relationship("User")
    memberships = db.relationship(
        "CommunityMember", back_populates="community", cascade="all, delete-orphan"
    )
    posts = db.relationship("Post", back_populates="community", cascade="all, delete-orphan")
    invitations = db.relationship(
        "CommunityInvitation", back_populates="community", cascade="all, delete-orphan"
    )

    @property
    def is_private(self):
        return self.visibility == "private"

    @property
    def kind_label(self):
        return {"group": "Group", "club": "Club"}.get(self.kind, "Community")


class CommunityMember(db.Model):
    __tablename__ = "community_members"
    __table_args__ = (db.UniqueConstraint("community_id", "user_id", name="uq_community_member"),)

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="member")
    joined_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    community = db.relationship("Community", back_populates="memberships")
    user = db.relationship("User", back_populates="memberships")


class CommunityInvitation(db.Model):
    __tablename__ = "community_invitations"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    invitee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False, default="invite")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    message = db.Column(db.String(240), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    community = db.relationship("Community", back_populates="invitations")
    inviter = db.relationship("User", foreign_keys=[inviter_id])
    invitee = db.relationship("User", foreign_keys=[invitee_id])


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    community = db.relationship("Community", back_populates="posts")
    author = db.relationship("User")
    comments = db.relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    reactions = db.relationship(
        "Reaction",
        foreign_keys="Reaction.post_id",
        cascade="all, delete-orphan",
        back_populates="post",
    )


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    post = db.relationship("Post", back_populates="comments")
    author = db.relationship("User")
    reactions = db.relationship(
        "Reaction",
        foreign_keys="Reaction.comment_id",
        cascade="all, delete-orphan",
        back_populates="comment",
    )


class Reaction(db.Model):
    __tablename__ = "reactions"
    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_reaction_post"),
        db.UniqueConstraint("user_id", "comment_id", name="uq_reaction_comment"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True, index=True)
    kind = db.Column(db.String(20), nullable=False, default="like")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User")
    post = db.relationship("Post", foreign_keys=[post_id], back_populates="reactions")
    comment = db.relationship("Comment", foreign_keys=[comment_id], back_populates="reactions")


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), default="")
    is_group = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)

    participants = db.relationship(
        "ConversationParticipant", back_populates="conversation", cascade="all, delete-orphan"
    )
    messages = db.relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def title_for(self, user):
        if self.title:
            return self.title
        names = [p.user.name for p in self.participants if p.user_id != user.id and p.user]
        return ", ".join(names) or "Conversation"


class ConversationParticipant(db.Model):
    __tablename__ = "conversation_participants"
    __table_args__ = (
        db.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),
    )

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    last_read_at = db.Column(db.DateTime, nullable=True)
    joined_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    conversation = db.relationship("Conversation", back_populates="participants")
    user = db.relationship("User", back_populates="participations")


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)

    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    kind = db.Column(db.String(40), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.String(300), default="")
    link = db.Column(db.String(240), default="")
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="notifications")
    actor = db.relationship("User", foreign_keys=[actor_id])

    @property
    def category(self):
        from app.constants import NOTIFY_CATEGORIES

        return NOTIFY_CATEGORIES.get(self.kind, "system")


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = db.relationship("User")
    project = db.relationship("Project", back_populates="notes")


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(60), default="Other", index=True)
    status = db.Column(db.String(30), default="Planning", index=True)
    visibility = db.Column(db.String(20), nullable=False, default="public")
    published = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(db.DateTime, nullable=True)
    technologies = db.Column(db.String(200), default="")
    repo_url = db.Column(db.String(300), default="")
    demo_url = db.Column(db.String(300), default="")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator = db.relationship("User")
    memberships = db.relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    tasks = db.relationship("Task", back_populates="project", cascade="all, delete-orphan")
    invites = db.relationship("ProjectInvite", back_populates="project", cascade="all, delete-orphan")
    notes = db.relationship("Note", back_populates="project")
    files = db.relationship("FileItem", back_populates="project")
    discussions = db.relationship(
        "ProjectDiscussion", back_populates="project", cascade="all, delete-orphan"
    )
    activities = db.relationship("Activity", back_populates="project")

    @property
    def visibility_label(self):
        return "Private" if self.visibility == "private" else "Public"

    @property
    def completion(self):
        total = len(self.tasks)
        if not total:
            return 0
        done = sum(1 for task in self.tasks if task.status == "DONE")
        return round(100 * done / total)

    @property
    def tech_list(self):
        return [item.strip() for item in (self.technologies or "").split(",") if item.strip()]


class ProjectMember(db.Model):
    __tablename__ = "project_members"
    __table_args__ = (db.UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="contributor")
    joined_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    project = db.relationship("Project", back_populates="memberships")
    user = db.relationship("User")

    @property
    def role_label(self):
        labels = {
            "owner": "Owner",
            "manager": "Manager",
            "contributor": "Contributor",
            "viewer": "Viewer",
            "member": "Contributor",
        }
        return labels.get(self.role, (self.role or "").replace("_", " ").title())


class ProjectInvite(db.Model):
    __tablename__ = "project_invites"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    invitee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="contributor")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    project = db.relationship("Project", back_populates="invites")
    inviter = db.relationship("User", foreign_keys=[inviter_id])
    invitee = db.relationship("User", foreign_keys=[invitee_id])


class ProjectDiscussion(db.Model):
    __tablename__ = "project_discussions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False, default="discussion")
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    project = db.relationship("Project", back_populates="discussions")
    author = db.relationship("User")

    @property
    def kind_label(self):
        return {
            "announcement": "Announcement",
            "discussion": "Discussion",
            "question": "Question",
            "update": "Update",
        }.get(self.kind, (self.kind or "").title())


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, default="")
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    deadline = db.Column(db.DateTime, nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="TODO")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    project = db.relationship("Project", back_populates="tasks")
    assignee = db.relationship("User", foreign_keys=[assignee_id])
    author = db.relationship("User", foreign_keys=[created_by])

    @property
    def is_overdue(self):
        return bool(self.deadline and self.deadline < utcnow() and self.status != "DONE")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    subject = db.Column(db.String(80), default="", index=True)
    tags = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    author = db.relationship("User")
    answers = db.relationship("Answer", back_populates="question", cascade="all, delete-orphan")

    @property
    def tag_list(self):
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]


class Answer(db.Model):
    __tablename__ = "answers"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    accepted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=True)

    question = db.relationship("Question", back_populates="answers")
    author = db.relationship("User")
    votes = db.relationship("AnswerVote", back_populates="answer", cascade="all, delete-orphan")

    @property
    def score(self):
        return sum(vote.value for vote in self.votes)

    def vote_by(self, user):
        if not user or not getattr(user, "is_authenticated", False):
            return 0
        for vote in self.votes:
            if vote.user_id == user.id:
                return vote.value
        return 0


class AcademicResource(db.Model):
    __tablename__ = "academic_resources"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    subject = db.Column(db.String(80), default="", index=True)
    kind = db.Column(db.String(40), nullable=False, default="Study Resource")
    description = db.Column(db.Text, default="")
    tags = db.Column(db.String(200), default="")
    link = db.Column(db.String(300), default="")
    stored_name = db.Column(db.String(180), default="")
    original_name = db.Column(db.String(180), default="")
    size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    author = db.relationship("User")

    @property
    def tag_list(self):
        return [tag.strip() for tag in (self.tags or "").split(",") if tag.strip()]


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, default="")
    location = db.Column(db.String(140), default="")
    category = db.Column(db.String(40), nullable=False, default="Event", index=True)
    registration_link = db.Column(db.String(300), default="")
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    creator = db.relationship("User")


class Idea(db.Model):
    __tablename__ = "ideas"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, default="")
    skills_needed = db.Column(db.String(200), default="")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    author = db.relationship("User")
    project = db.relationship("Project")
    interests = db.relationship("IdeaInterest", back_populates="idea", cascade="all, delete-orphan")


class FileItem(db.Model):
    __tablename__ = "files"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    stored_name = db.Column(db.String(180), nullable=False)
    original_name = db.Column(db.String(180), nullable=False)
    size = db.Column(db.Integer, default=0)
    mime = db.Column(db.String(80), default="")
    folder = db.Column(db.String(40), nullable=False, default="Other")
    group_key = db.Column(db.String(64), nullable=False, default="", index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User")
    project = db.relationship("Project", back_populates="files")


class AnswerVote(db.Model):
    __tablename__ = "answer_votes"
    __table_args__ = (db.UniqueConstraint("user_id", "answer_id", name="uq_answer_vote"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    answer_id = db.Column(db.Integer, db.ForeignKey("answers.id"), nullable=False, index=True)
    value = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User")
    answer = db.relationship("Answer", back_populates="votes")


class IdeaInterest(db.Model):
    __tablename__ = "idea_interests"
    __table_args__ = (db.UniqueConstraint("idea_id", "user_id", name="uq_idea_interest"),)

    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    idea = db.relationship("Idea", back_populates="interests")
    user = db.relationship("User")


class Achievement(db.Model):
    __tablename__ = "achievements"
    __table_args__ = (db.UniqueConstraint("user_id", "code", name="uq_achievement"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False, index=True)
    earned_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User")

    @property
    def label(self):
        from app.constants import ACHIEVEMENTS

        return ACHIEVEMENTS.get(self.code, (self.code.replace("_", " ").title(), ""))[0]

    @property
    def blurb(self):
        from app.constants import ACHIEVEMENTS

        return ACHIEVEMENTS.get(self.code, ("", ""))[1]
