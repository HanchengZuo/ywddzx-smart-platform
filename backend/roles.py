"""Stable role identifiers shared by authentication and inspection workflows.

The existing supervisor identifier now denotes members so historical references
and account-specific permissions remain intact.
"""
SUPERVISOR_ROLES = ("supervisor_manager", "supervisor")
PRIVILEGED_ROLES = frozenset(("root", *SUPERVISOR_ROLES))


def is_supervisor_role(role):
    return role in SUPERVISOR_ROLES
