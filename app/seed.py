"""Demo workspace used the first time the database is created."""

import os
import uuid
from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import (
    AcademicResource,
    Activity,
    Answer,
    Comment,
    Community,
    CommunityInvitation,
    CommunityMember,
    Conversation,
    ConversationParticipant,
    Event,
    FileItem,
    Idea,
    IdeaInterest,
    Message,
    Note,
    Notification,
    Post,
    Project,
    ProjectDiscussion,
    ProjectMember,
    Question,
    Reaction,
    Task,
    User,
    utcnow,
)
from app.services import unique_slug


def seed_if_empty():
    if User.query.first():
        return
    now = utcnow()

    def user(**kwargs):
        password = kwargs.pop("password")
        row = User(**kwargs)
        row.set_password(password)
        db.session.add(row)
        return row

    admin = user(
        name="Unity Admin",
        username="admin",
        email="admin@unityworks.app",
        password="UnityAdmin#2026",
        role="admin",
        headline="Keeps the campus workspace healthy.",
        bio="Platform administrator for UnityWorks.",
        college="UnityWorks",
        experience="Advanced",
        created_at=now - timedelta(days=40),
    )
    aarav = user(
        name="Aarav Shah",
        username="aarav",
        email="aarav@unityworks.app",
        password="Student#2026",
        avatar="seed:aarav.jpg",
        headline="Learning systems, building with people.",
        bio="Third-year CSE student in Prayagraj. I like study groups that actually ship — papers on Fridays, prototypes on Sundays.",
        skills="Python, Machine Learning, Flask, SQL",
        education="B.Tech Computer Science, Sangam Institute of Technology",
        interests="Research, Hackathons, Open Source",
        college="Sangam Institute of Technology, Prayagraj",
        program="B.Tech CSE",
        academic_year="Year 3",
        experience="Intermediate",
        created_at=now - timedelta(days=30),
    )
    mira = user(
        name="Mira Chen",
        username="mira",
        email="mira@unityworks.app",
        password="Student#2026",
        avatar="seed:mira.jpg",
        headline="Interfaces, study notes, and calm CSS.",
        bio="I design and build student tools. Looking for collaborators who care about the details.",
        skills="JavaScript, CSS, UI Design, Accessibility",
        education="B.Des Interaction, Northwind University",
        interests="Design systems, Photography, Writing",
        college="Northwind University",
        program="Interaction Design",
        academic_year="Year 2",
        experience="Advanced",
        created_at=now - timedelta(days=28),
    )
    leo = user(
        name="Leo Mensah",
        username="leo",
        email="leo@unityworks.app",
        password="Student#2026",
        avatar="seed:leo.jpg",
        headline="Night-shift competitive programmer.",
        bio="I run problem-solving sessions and like explaining proofs without the fog.",
        skills="C++, Algorithms, Competitive Programming",
        education="B.Sc. Computing, Linden School of Computing",
        interests="Contests, Teaching, Chess",
        college="Linden School of Computing",
        program="Computer Science",
        academic_year="Year 4",
        experience="Advanced",
        created_at=now - timedelta(days=26),
    )
    sofia = user(
        name="Sofia Alvarez",
        username="sofia",
        email="sofia@unityworks.app",
        password="Student#2026",
        avatar="seed:sofia.jpg",
        headline="Photographs the campus, then designs the poster.",
        bio="Club lead and visual storyteller. Always up for a walk with a camera and a brief.",
        skills="Photography, Figma, Branding, Writing",
        education="B.A. Visual Communication, Harbour College of Design",
        interests="Film, Clubs, Campus stories",
        college="Harbour College of Design",
        program="Visual Communication",
        academic_year="Year 3",
        experience="Intermediate",
        created_at=now - timedelta(days=22),
    )
    kabir = user(
        name="Kabir Nair",
        username="kabir",
        email="kabir@unityworks.app",
        password="Student#2026",
        avatar="seed:kabir.jpg",
        headline="Turning messy datasets into something a classmate can use.",
        bio="First serious year with data. Happy to pair on statistics homework or a small dashboard.",
        skills="Python, Statistics, Data Analysis",
        education="B.Sc. Statistics, Sangam Institute of Technology",
        interests="Data visualization, Cricket, Study playlists",
        college="Sangam Institute of Technology, Prayagraj",
        program="Statistics",
        academic_year="Year 2",
        experience="Beginner",
        created_at=now - timedelta(days=18),
    )
    db.session.flush()

    def community(owner, name, description, category, kind="community", visibility="public", days=20):
        row = Community(
            name=name,
            slug=unique_slug(Community, name),
            description=description,
            category=category,
            kind=kind,
            visibility=visibility,
            creator_id=owner.id,
            created_at=now - timedelta(days=days),
        )
        db.session.add(row)
        db.session.flush()
        db.session.add(CommunityMember(community_id=row.id, user_id=owner.id, role="owner", joined_at=row.created_at))
        return row

    ml = community(
        aarav,
        "Machine Learning",
        "Paper club, project critiques, and a calm place to ask the question you almost didn't.",
        "Machine Learning",
        days=24,
    )
    web = community(
        mira,
        "Web Development",
        "HTML, CSS, Flask, and the small interface decisions that make study tools feel finished.",
        "Web Development",
        days=23,
    )
    cp = community(
        leo,
        "Competitive Programming",
        "Weekly sets, editorials, and contest post-mortems. Bring the problem that beat you.",
        "Competitive Programming",
        days=21,
    )
    photo = community(
        sofia,
        "Photography",
        "Campus walks, lighting notes, and critique that stays kind.",
        "Photography",
        days=16,
    )
    clubs = community(
        kabir,
        "College Clubs",
        "A notice board for student clubs — meetings, drives, and people looking for a role.",
        "College Clubs",
        days=14,
    )
    hacks = community(
        aarav,
        "Hackathons",
        "Team formation, idea notes, and what we wish we had packed last time.",
        "Hackathons",
        days=12,
    )
    squad = community(
        mira,
        "Final Year Project Squad",
        "A small group for people shipping a year-long build. Weekly check-ins, no status theater.",
        "Academics",
        kind="group",
        visibility="private",
        days=9,
    )
    dsa = community(
        leo,
        "DSA Night Grind",
        "Late sessions for arrays, graphs, and the one DP problem we keep postponing.",
        "Competitive Programming",
        kind="group",
        days=8,
    )
    walk = community(
        sofia,
        "Campus Photography Walk",
        "Saturday morning walk. Meet at the gate, shoot for an hour, share three frames.",
        "Photography",
        kind="group",
        days=6,
    )

    def join(community_row, person, role="member", days=5):
        db.session.add(
            CommunityMember(
                community_id=community_row.id,
                user_id=person.id,
                role=role,
                joined_at=now - timedelta(days=days),
            )
        )

    join(ml, mira, days=10)
    join(ml, kabir, days=4)
    join(web, aarav, days=11)
    join(web, sofia, "moderator", days=7)
    join(cp, kabir, days=3)
    join(hacks, mira, days=6)
    join(hacks, leo, days=5)
    join(squad, aarav, days=4)
    join(dsa, kabir, days=2)
    join(photo, mira, days=3)
    join(clubs, sofia, "moderator", days=2)

    db.session.add(
        CommunityInvitation(
            community_id=dsa.id,
            inviter_id=leo.id,
            invitee_id=aarav.id,
            kind="invite",
            message="We are missing a Python person on Thursday. Come if you want a quiet room and hard problems.",
            created_at=now - timedelta(hours=8),
        )
    )

    def post(community_row, author, title, body, days=2, hours=0):
        row = Post(
            community_id=community_row.id,
            author_id=author.id,
            title=title,
            body=body,
            created_at=now - timedelta(days=days, hours=hours),
        )
        db.session.add(row)
        db.session.flush()
        return row

    p1 = post(
        ml,
        aarav,
        "Friday paper: attention, without the fog",
        "Bringing a short walkthrough of the transformer paper. Read sections 3 and 4 if you can — we will sketch the diagram together and skip the prestige.\n\nBring one question. That is the entry ticket.",
        days=2,
    )
    p2 = post(
        web,
        mira,
        "Portfolio roast thread",
        "Drop a link and one sentence about what feels unfinished. I will reply with one structural note, not a pile of opinions.",
        days=1,
        hours=3,
    )
    p3 = post(
        cp,
        leo,
        "Graph set for Thursday",
        "Five problems. The last one is the one I failed in contest. Editorials stay hidden until Friday noon.",
        days=1,
    )
    post(
        hacks,
        aarav,
        "Who is still looking for a team?",
        "Sangam students and friends of friends. We need one person who likes talking to users more than opening a new repo.",
        days=3,
    )
    db.session.add(Comment(post_id=p1.id, author_id=mira.id, body="I can bring the diagram. Saving a seat.", created_at=now - timedelta(days=1, hours=4)))
    db.session.add(Comment(post_id=p2.id, author_id=aarav.id, body="Mine is still a folder of screenshots. I will bring the real link tonight.", created_at=now - timedelta(hours=6)))
    db.session.add(Reaction(user_id=mira.id, post_id=p1.id, kind="like", created_at=now - timedelta(days=1)))
    db.session.add(Reaction(user_id=kabir.id, post_id=p1.id, kind="like", created_at=now - timedelta(hours=20)))
    db.session.add(Reaction(user_id=sofia.id, post_id=p2.id, kind="like", created_at=now - timedelta(hours=5)))

    conv = Conversation(is_group=False, created_at=now - timedelta(days=3), updated_at=now - timedelta(hours=2))
    db.session.add(conv)
    db.session.flush()
    db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=aarav.id, last_read_at=now - timedelta(hours=2)))
    db.session.add(ConversationParticipant(conversation_id=conv.id, user_id=mira.id, last_read_at=now - timedelta(hours=5)))
    db.session.add(Message(conversation_id=conv.id, sender_id=mira.id, body="Did the paper club time move, or are we still on Friday at 6?", created_at=now - timedelta(days=1, hours=2)))
    db.session.add(Message(conversation_id=conv.id, sender_id=aarav.id, body="Still Friday. I booked the small lab — the one with the good board.", created_at=now - timedelta(days=1)))
    db.session.add(Message(conversation_id=conv.id, sender_id=mira.id, body="Perfect. I'll bring printed diagrams so we are not squinting at a slide.", created_at=now - timedelta(hours=2)))

    group = Conversation(title="Study Sprint", is_group=True, created_at=now - timedelta(days=2), updated_at=now - timedelta(hours=1))
    db.session.add(group)
    db.session.flush()
    for person, read in ((leo, now), (kabir, now - timedelta(hours=3)), (aarav, now - timedelta(days=1))):
        db.session.add(ConversationParticipant(conversation_id=group.id, user_id=person.id, last_read_at=read))
    db.session.add(Message(conversation_id=group.id, sender_id=leo.id, body="Thursday set is up in Competitive Programming. No spoilers in here.", created_at=now - timedelta(hours=3)))
    db.session.add(Message(conversation_id=group.id, sender_id=kabir.id, body="I will start with the graph ones. Saving the DP for when I am braver.", created_at=now - timedelta(hours=1)))

    nav = Project(
        name="Campus Navigator",
        slug=unique_slug(Project, "Campus Navigator"),
        description="A small map of Sangam that knows which labs are actually open after 7.",
        category="Web Development",
        status="Active",
        visibility="public",
        creator_id=aarav.id,
        created_at=now - timedelta(days=15),
    )
    notes_project = Project(
        name="StudyBuddy Notes",
        slug=unique_slug(Project, "StudyBuddy Notes"),
        description="Shared revision sheets with owners, not a graveyard of Google Docs.",
        category="Academics",
        status="Planning",
        visibility="public",
        creator_id=mira.id,
        created_at=now - timedelta(days=8),
    )
    db.session.add_all([nav, notes_project])
    db.session.flush()
    db.session.add(ProjectMember(project_id=nav.id, user_id=aarav.id, role="owner"))
    db.session.add(ProjectMember(project_id=nav.id, user_id=kabir.id, role="contributor"))
    db.session.add(ProjectMember(project_id=notes_project.id, user_id=mira.id, role="owner"))
    db.session.add(ProjectMember(project_id=notes_project.id, user_id=aarav.id, role="contributor"))
    db.session.add(Task(project_id=nav.id, title="Sketch the lab hours table", assignee_id=kabir.id, created_by=aarav.id, status="IN PROGRESS", priority="High"))
    db.session.add(Task(project_id=notes_project.id, title="Decide how shared notes are owned", assignee_id=aarav.id, created_by=mira.id, status="TODO", priority="Medium"))

    db.session.add(Note(user_id=aarav.id, title="Transformer diagram notes", body="Query, key, value. Draw the residual path before memorizing the formula.\n\n`softmax(QK^T / sqrt(d)) V`", created_at=now - timedelta(days=2)))
    db.session.add(Note(user_id=aarav.id, title="Lab booking", body="Small lab, Friday 6pm. Bring markers.", created_at=now - timedelta(days=1)))

    question = Question(
        author_id=kabir.id,
        title="How do you explain a confusion matrix to a non-stats friend?",
        body="I have a club demo on Saturday. I want a picture, not a definition. What has actually worked for you?",
        tags="statistics, teaching",
        created_at=now - timedelta(days=1, hours=5),
    )
    db.session.add(question)
    db.session.flush()
    db.session.add(Answer(question_id=question.id, author_id=aarav.id, body="Four boxes, two questions: did we say yes, and were we right? Start there. The words can come later.", created_at=now - timedelta(hours=9)))

    db.session.add(
        AcademicResource(
            author_id=leo.id,
            title="Graph editorial notebook",
            subject="Algorithms",
            description="A short set of patterns: BFS layers, Dijkstra with a reason, and when not to use either.",
            link="https://cp-algorithms.com/graph/breadth-first-search.html",
            created_at=now - timedelta(days=4),
        )
    )
    db.session.add(
        AcademicResource(
            author_id=mira.id,
            title="Glass interface notes",
            subject="Web Development",
            description="Blur, a hairline border, and one light edge. If it needs a drop shadow the size of a building, it is not glass.",
            created_at=now - timedelta(days=3),
        )
    )
    db.session.add(
        Event(
            creator_id=aarav.id,
            title="ML paper club",
            description="Transformer walkthrough. One question each.",
            location="Small lab, Sangam Institute",
            starts_at=now + timedelta(days=2, hours=4),
        )
    )
    db.session.add(
        Event(
            creator_id=sofia.id,
            title="Campus photography walk",
            description="Three frames, then tea.",
            location="Main gate",
            starts_at=now + timedelta(days=4),
        )
    )
    db.session.add(
        Idea(
            author_id=mira.id,
            title="A quieter attendance tool for clubs",
            description="Not another spreadsheet. A check-in that a secretary can run from their phone without a training session.",
            skills_needed="Flask, UI, Writing",
            created_at=now - timedelta(days=2),
        )
    )
    db.session.add(
        Idea(
            author_id=leo.id,
            title="Contest post-mortem archive",
            description="After every contest, one page: what we missed, what we would drill next week.",
            skills_needed="Competitive Programming, Writing",
            created_at=now - timedelta(hours=20),
        )
    )

    db.session.add(
        Notification(
            user_id=aarav.id,
            actor_id=mira.id,
            kind="comment",
            title="Mira Chen commented on your post",
            body="I can bring the diagram. Saving a seat.",
            link=f"/communities/{ml.slug}/posts/{p1.id}",
            is_read=False,
            created_at=now - timedelta(days=1, hours=4),
        )
    )
    db.session.add(
        Notification(
            user_id=aarav.id,
            actor_id=leo.id,
            kind="community_invitation",
            title="Invitation to DSA Night Grind",
            body="We are missing a Python person on Thursday.",
            link="/invitations",
            is_read=False,
            created_at=now - timedelta(hours=8),
        )
    )
    db.session.add(
        Notification(
            user_id=kabir.id,
            actor_id=aarav.id,
            kind="task_assignment",
            title="Task assigned in Campus Navigator",
            body="Sketch the lab hours table",
            link=f"/projects/{nav.slug}",
            is_read=False,
            created_at=now - timedelta(days=1),
        )
    )
    db.session.add(
        Notification(
            user_id=mira.id,
            actor_id=aarav.id,
            kind="new_message",
            title="New message from Aarav Shah",
            body="Still Friday. I booked the small lab.",
            link=f"/messages/{conv.id}",
            is_read=True,
            created_at=now - timedelta(days=1),
        )
    )

    for person, summary, link, hours in (
        (aarav, "You posted in Machine Learning.", "/communities/machine-learning", 48),
        (aarav, "File uploaded: revision-outline.txt", "/files", 30),
        (mira, "You commented on a paper-club post.", "/communities/machine-learning", 28),
        (leo, "You published the Thursday graph set.", "/communities/competitive-programming", 24),
        (aarav, "You joined Final Year Project Squad.", "/communities/final-year-project-squad", 96),
    ):
        db.session.add(Activity(user_id=person.id, summary=summary, link=link, created_at=now - timedelta(hours=hours)))

    folder_note = "revision-outline.txt"
    # File row is recorded; the bytes are created by the app if missing.
    db.session.add(
        FileItem(
            owner_id=aarav.id,
            stored_name=folder_note,
            original_name="revision-outline.txt",
            size=120,
            mime="text/plain",
            folder="Documents",
            group_key="revision-outline",
            version=1,
            created_at=now - timedelta(hours=30),
        )
    )
    db.session.commit()

    path = os.path.join(current_app.config["FILE_FOLDER"], folder_note)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("Attention paper - sections 3 and 4.\nOne question for Friday.\n")


def enrich_workspace():
    """Fill the existing demo projects once, without touching a database that already has discussions."""
    if ProjectDiscussion.query.first():
        return
    aarav = User.query.filter_by(username="aarav").first()
    kabir = User.query.filter_by(username="kabir").first()
    sofia = User.query.filter_by(username="sofia").first()
    if not aarav:
        return
    now = utcnow()
    nav = Project.query.filter_by(slug="campus-navigator").first()
    if nav:
        if not nav.category or nav.category == "Other":
            nav.category = "Web Development"
        if not nav.visibility:
            nav.visibility = "public"
        _ensure_task(nav, "Mark the gates that lock at 8", aarav, None, "TODO", "Medium", now + timedelta(days=4))
        _ensure_task(nav, "Review the Friday hours", aarav, aarav, "REVIEW", "Medium", now + timedelta(days=1))
        _ensure_task(nav, "Publish the first map pin", aarav, kabir, "DONE", "Low", now - timedelta(days=1))
        if not Note.query.filter_by(project_id=nav.id).first():
            db.session.add(
                Note(
                    user_id=aarav.id,
                    project_id=nav.id,
                    title="Lab hours that are actually true",
                    body="Ask the night guard before trusting the printed sheet. The small lab stays open on Fridays.",
                    created_at=now - timedelta(days=1),
                )
            )
        if not ProjectDiscussion.query.filter_by(project_id=nav.id).first():
            db.session.add(
                ProjectDiscussion(
                    project_id=nav.id,
                    author_id=aarav.id,
                    kind="announcement",
                    title="We are mapping real hours",
                    body="Skip the brochure. If a lab was closed last week, say so in the thread.",
                    created_at=now - timedelta(days=2),
                )
            )
            if kabir:
                db.session.add(
                    ProjectDiscussion(
                        project_id=nav.id,
                        author_id=kabir.id,
                        kind="question",
                        title="Which lab stays open during exams?",
                        body="I can check the notice board tomorrow if nobody has the list.",
                        created_at=now - timedelta(hours=6),
                    )
                )
        if not FileItem.query.filter_by(project_id=nav.id).first():
            group_key = uuid.uuid4().hex
            _demo_file(aarav, nav, "hours.txt", "Lab hours, first pass.\n", 1, group_key, now - timedelta(days=2))
            _demo_file(kabir or aarav, nav, "hours.txt", "Lab hours, checked with the guard.\n", 2, group_key, now - timedelta(hours=8))
        if not Activity.query.filter_by(project_id=nav.id).first():
            db.session.add(
                Activity(
                    user_id=aarav.id,
                    project_id=nav.id,
                    summary=f"{aarav.name} created a task",
                    link=f"/projects/{nav.slug}",
                    created_at=now - timedelta(days=3),
                )
            )
            if kabir:
                db.session.add(
                    Activity(
                        user_id=kabir.id,
                        project_id=nav.id,
                        summary=f"{kabir.name} joined the project",
                        link=f"/projects/{nav.slug}",
                        created_at=now - timedelta(days=4),
                    )
                )
    notes_project = Project.query.filter_by(slug="studybuddy-notes").first()
    if notes_project and (not notes_project.category or notes_project.category == "Other"):
        notes_project.category = "Academics"
    if sofia and not Project.query.filter_by(published=True).first():
        poster = Project(
            name="Night Market Poster",
            slug=unique_slug(Project, "Night Market Poster"),
            description="A finished poster set for the campus night market. Published so the next team can see what shipped.",
            category="Design",
            status="Completed",
            visibility="public",
            published=True,
            published_at=now - timedelta(days=3),
            creator_id=sofia.id,
            created_at=now - timedelta(days=12),
        )
        db.session.add(poster)
        db.session.flush()
        db.session.add(ProjectMember(project_id=poster.id, user_id=sofia.id, role="owner"))
        db.session.add(
            Task(
                project_id=poster.id,
                title="Export the final poster",
                created_by=sofia.id,
                assignee_id=sofia.id,
                status="DONE",
                priority="Medium",
            )
        )
        db.session.add(
            ProjectDiscussion(
                project_id=poster.id,
                author_id=sofia.id,
                kind="update",
                title="Poster is up",
                body="Printed and pinned. This one can live in the showcase.",
            )
        )
    db.session.commit()


def _ensure_task(project, title, creator, assignee, status, priority, deadline):
    if Task.query.filter_by(project_id=project.id, title=title).first():
        return
    db.session.add(
        Task(
            project_id=project.id,
            title=title,
            created_by=creator.id,
            assignee_id=assignee.id if assignee else None,
            status=status,
            priority=priority,
            deadline=deadline,
        )
    )


def _demo_file(owner, project, name, body, version, group_key, created_at):
    stored = f"{uuid.uuid4().hex}.txt"
    directory = current_app.config["FILE_FOLDER"]
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, stored), "w", encoding="utf-8") as handle:
        handle.write(body)
    db.session.add(
        FileItem(
            owner_id=owner.id,
            project_id=project.id,
            stored_name=stored,
            original_name=name,
            size=len(body.encode("utf-8")),
            mime="text/plain",
            folder="Documents",
            group_key=group_key,
            version=version,
            created_at=created_at,
        )
    )

def enrich_ecosystem():
    """Add clubs, opportunities, and public portfolio details without rewriting earlier seeds."""
    aarav = User.query.filter_by(username="aarav").first()
    if not aarav:
        return
    now = utcnow()
    for event in Event.query.filter((Event.category.is_(None)) | (Event.category == "")).all():
        title = (event.title or "").lower()
        if "paper" in title or "workshop" in title:
            event.category = "Workshop"
        elif "photo" in title or "walk" in title:
            event.category = "Meetup"
        else:
            event.category = "Event"
    poster = Project.query.filter_by(slug="night-market-poster").first()
    if poster and not poster.technologies:
        poster.technologies = "Figma, Print, Photography"
    question = Question.query.filter(Question.title.contains("confusion matrix")).first()
    if question and not question.subject:
        question.subject = "Statistics"
    for resource in AcademicResource.query.filter((AcademicResource.tags.is_(None)) | (AcademicResource.tags == "")).all():
        if "graph" in (resource.title or "").lower():
            resource.tags = "algorithms, graphs"
            resource.kind = "Reference Material"
            if resource.subject not in {
                "Programming", "Mathematics", "Machine Learning", "Data Science", "Computer Science",
                "Electronics", "Algorithms", "Web Development", "Statistics", "Design", "Other",
            }:
                resource.subject = "Algorithms"
        elif "glass" in (resource.title or "").lower():
            resource.tags = "css, interface"
            resource.kind = "Notes"
            resource.subject = resource.subject or "Web Development"
    if not Event.query.filter_by(category="Hackathon").first():
        db.session.add(
            Event(
                creator_id=aarav.id,
                title="Sangam weekend hack",
                description="Thirty-six hours. Bring a teammate or find one on the idea board.",
                location="Main lab, Sangam Institute",
                category="Hackathon",
                registration_link="https://example.com/sangam-weekend-hack",
                starts_at=now + timedelta(days=12),
            )
        )
    if Community.query.filter_by(kind="club").first():
        db.session.commit()
        return
    sofia = User.query.filter_by(username="sofia").first()
    mira = User.query.filter_by(username="mira").first()
    kabir = User.query.filter_by(username="kabir").first()
    leo = User.query.filter_by(username="leo").first()

    def club(owner, name, description, category):
        if not owner or Community.query.filter_by(name=name).first():
            return None
        row = Community(
            name=name,
            slug=unique_slug(Community, name),
            description=description,
            category=category,
            kind="club",
            visibility="public",
            creator_id=owner.id,
            created_at=now - timedelta(days=5),
        )
        db.session.add(row)
        db.session.flush()
        db.session.add(CommunityMember(community_id=row.id, user_id=owner.id, role="owner"))
        return row

    club(aarav, "Coding Club", "Weekly builds, office hours, and a place to ask the question that does not fit a lecture.", "College Clubs")
    club(sofia or aarav, "Photography Club", "Campus walks, lighting notes, and critique that stays kind.", "Photography")
    club(leo or aarav, "Robotics Club", "A bench, a battery, and the patience to try the mechanism again.", "Other")
    if not Community.query.filter_by(name="Study Hall").first():
        hall = Community(
            name="Study Hall",
            slug=unique_slug(Community, "Study Hall"),
            description="A public room for subject questions that are bigger than one project.",
            category="Academics",
            kind="community",
            visibility="public",
            creator_id=aarav.id,
        )
        db.session.add(hall)
        db.session.flush()
        db.session.add(CommunityMember(community_id=hall.id, user_id=aarav.id, role="owner"))
        db.session.add(
            Post(
                community_id=hall.id,
                author_id=aarav.id,
                title="Bring the problem set, not the panic",
                body="Post the subject and the line you are stuck on. Someone in the room has seen it before.",
            )
        )
    if not aarav.mentor_role:
        aarav.mentor_role = "mentor"
    if kabir and not kabir.mentor_role:
        kabir.mentor_role = "mentee"
    if mira and not mira.mentor_role:
        mira.mentor_role = "both"
    if not aarav.profile_public:
        aarav.profile_public = True
        aarav.public_sections = "about,skills,education,projects,achievements,communities"
    if sofia and not sofia.profile_public:
        sofia.profile_public = True
        sofia.certifications = sofia.certifications or "Campus design studio, year 2"
        sofia.honors = sofia.honors or "Night market poster, printed and pinned"
        sofia.public_sections = "about,skills,projects,achievements,certifications"
    idea = Idea.query.filter_by(title="A quieter attendance tool for clubs").first()
    if idea and kabir and not IdeaInterest.query.filter_by(idea_id=idea.id, user_id=kabir.id).first():
        db.session.add(IdeaInterest(idea_id=idea.id, user_id=kabir.id))
    db.session.commit()
