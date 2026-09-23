import re

from email_validator import EmailNotValidError, validate_email

from app.constants import MAX_PASSWORD, MIN_PASSWORD, RESERVED_USERNAMES


def clean_username(value):
    username = (value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{3,20}", username):
        return None, "Use 3–20 letters, numbers, or underscores."
    if username in RESERVED_USERNAMES:
        return None, "That username is reserved."
    return username, None


def clean_email(value):
    raw = (value or "").strip()
    try:
        valid = validate_email(raw, check_deliverability=False)
    except EmailNotValidError:
        return None, "Enter a valid email address."
    return valid.email.lower(), None


def clean_password(value, confirm=None):
    password = value or ""
    if len(password) < MIN_PASSWORD:
        return None, f"Use at least {MIN_PASSWORD} characters."
    if len(password) > MAX_PASSWORD:
        return None, "That password is too long."
    if confirm is not None and password != confirm:
        return None, "Passwords do not match."
    return password, None


def clean_name(value):
    name = " ".join((value or "").split())
    if len(name) < 2 or len(name) > 80:
        return None, "Enter your name (2–80 characters)."
    return name, None


def clip(value, limit, required=False, label="This field"):
    text = (value or "").strip()
    if required and not text:
        return None, f"{label} is required."
    if len(text) > limit:
        return None, f"{label} must be {limit} characters or fewer."
    return text, None
