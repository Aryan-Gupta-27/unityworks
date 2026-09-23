COMMUNITY_CATEGORIES = [
    "Machine Learning",
    "Web Development",
    "Competitive Programming",
    "Photography",
    "College Clubs",
    "Hackathons",
    "Academics",
    "Design",
    "Career",
    "Other",
]

COMMUNITY_KINDS = ["community", "group", "club"]

SUBJECTS = [
    "Programming",
    "Mathematics",
    "Machine Learning",
    "Data Science",
    "Computer Science",
    "Electronics",
    "Algorithms",
    "Web Development",
    "Statistics",
    "Design",
    "Other",
]

RESOURCE_KINDS = [
    "Notes",
    "PDF",
    "Presentation",
    "Reference Material",
    "Study Resource",
    "Link",
]

EVENT_CATEGORIES = ["Hackathon", "Workshop", "Competition", "Event", "Meetup"]

MENTOR_ROLES = ["mentor", "mentee", "both"]

PUBLIC_SECTIONS = [
    "about",
    "skills",
    "education",
    "experience",
    "projects",
    "achievements",
    "certifications",
    "communities",
]

ACHIEVEMENTS = {
    "first_project": ("First Project", "Started a project."),
    "project_contributor": ("Project Contributor", "Joined a project team."),
    "community_contributor": ("Community Contributor", "Joined a community, group, or club."),
    "helpful_answer": ("Helpful Answer", "Had an answer accepted."),
    "resource_contributor": ("Resource Contributor", "Shared a study resource."),
    "tasks_10": ("Completed 10 Tasks", "Finished ten assigned tasks."),
    "portfolio_builder": ("Portfolio Builder", "Published work or filled in a portfolio."),
}

NOTIFY_CATEGORIES = {
    "new_message": "messages",
    "project_invitation": "projects",
    "task_assignment": "tasks",
    "task_deadline": "tasks",
    "community_invitation": "communities",
    "comment": "academic",
    "project_comment": "projects",
    "event_reminder": "events",
}

NOTIFY_PREF_CATEGORIES = ["messages", "projects", "tasks", "communities", "academic", "events"]

ACTIVITY_AREAS = ["project", "community", "academic", "portfolio", "system"]

SEARCH_TYPES = ["all", "users", "communities", "projects", "resources", "questions", "events", "ideas"]

EXPERIENCE_LEVELS = ["Exploring", "Beginner", "Intermediate", "Advanced"]

PROJECT_CATEGORIES = COMMUNITY_CATEGORIES

PROJECT_STATUSES = ["Planning", "Active", "Completed", "Archived"]

PROJECT_VISIBILITY = ["public", "private"]

PROJECT_ROLES = ["owner", "manager", "contributor", "viewer"]

TASK_STATUSES = ["TODO", "IN PROGRESS", "REVIEW", "DONE"]

TASK_PRIORITIES = ["Low", "Medium", "High", "Urgent"]

FILE_FOLDERS = ["Documents", "Images", "Presentations", "Code", "Resources", "Other"]

DISCUSSION_KINDS = ["announcement", "discussion", "question", "update"]

COMMUNITY_ROLES = ["owner", "moderator", "member"]

RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "support",
    "unityworks",
    "root",
    "system",
    "moderator",
    "help",
    "null",
}

RESERVED_SLUGS = {"new", "edit", "members", "invite", "join", "leave", "delete"}

MIN_PASSWORD = 8
MAX_PASSWORD = 128

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_FILE_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".txt", ".md",
    ".py", ".js", ".html", ".css", ".json", ".zip", ".docx", ".pptx",
    ".xlsx", ".csv",
}
