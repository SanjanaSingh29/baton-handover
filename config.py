from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "baton.db"

# How sensitive a source is. A claim takes the strictest level of its sources.
SENSITIVITIES = ["Open", "Team", "Restricted"]
SENSITIVITY_RANK = {"Open": 0, "Team": 1, "Restricted": 2}

# Which sensitivity levels each role is allowed to see.
ROLES = {
    "Project Lead": ["Open", "Team", "Restricted"],
    "Incoming Developer": ["Open", "Team"],
    "Incoming Volunteer": ["Open"],
}

CLAIM_TYPES = [
    "decision",
    "owner",
    "open_task",
    "risk",
    "dependency",
    "contact",
    "recurring_problem",
]

# Evidence statuses shown as badges.
STATUSES = ["Verified", "Inferred", "Conflicting", "Missing", "Unverified"]

# Review decisions made by the project lead.
REVIEW_STATES = ["pending", "accepted", "rejected"]