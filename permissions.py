"""Who may see what. The filter runs in code, before anything is shown."""
from config import ROLES, SENSITIVITY_RANK


def allowed_levels(role):
    # An unknown role sees nothing.
    return ROLES.get(role, [])


def can_see(role, sensitivity):
    return sensitivity in allowed_levels(role)


def split_by_role(claims, role):
    """Return (visible_claims, hidden_count) for a role."""
    visible = [c for c in claims if can_see(role, c["sensitivity"])]
    return visible, len(claims) - len(visible)


def strictest(levels):
    """The strictest of several sensitivity levels. No levels at all means Restricted."""
    if not levels:
        return "Restricted"
    return max(levels, key=lambda lvl: SENSITIVITY_RANK.get(lvl, 2))
