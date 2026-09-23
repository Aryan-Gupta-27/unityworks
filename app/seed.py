"""Demo workspace used the first time the database is created."""

from datetime import timedelta

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
    Message,
    Note,
    Notification,
    Post,
    Project,
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
        status="Active",
        creator_id=aarav.id,
        created_at=now - timedelta(days=15),
    )
    notes_project = Project(
        name="StudyBuddy Notes",
        slug=unique_slug(Project, "StudyBuddy Notes"),
        description="Shared revision sheets with owners, not a graveyard of Google Docs.",
        status="Planning",
        creator_id=mira.id,
        created_at=now - timedelta(days=8),
    )
    db.session.add_all([nav, notes_project])
    db.session.flush()
    db.session.add(ProjectMember(project_id=nav.id, user_id=aarav.id, role="owner"))
    db.session.add(ProjectMember(project_id=nav.id, user_id=kabir.id, role="member"))
    db.session.add(ProjectMember(project_id=notes_project.id, user_id=mira.id, role="owner"))
    db.session.add(ProjectMember(project_id=notes_project.id, user_id=aarav.id, role="member"))
    db.session.add(Task(project_id=nav.id, title="Sketch the lab hours table", assignee_id=kabir.id, created_by=aarav.id, status="In progress"))
    db.session.add(Task(project_id=notes_project.id, title="Decide how shared notes are owned", assignee_id=aarav.id, created_by=mira.id, status="To do"))

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
            created_at=now - timedelta(hours=30),
        )
    )
    db.session.commit()

    import os
    from flask import current_app

    path = os.path.join(current_app.config["FILE_FOLDER"], folder_note)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("Attention paper — sections 3 and 4.\nOne question for Friday.\n")
