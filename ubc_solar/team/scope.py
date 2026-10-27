"""Who sits where on the team, and what that lets them do.

The chain of responsibility (Captain > Execs per division > Subteam Leads) decides
who can approve purchases and BOMs, who can change positions, and who gets
@mentioned in Slack.
"""

import frappe

ACTIVE_POSITIONS = ("Captain", "Exec", "Subteam Lead", "Senior Design Member", "Member")
TOP_POSITIONS = ("Captain", "Exec")


def _members(filters):
	return frappe.get_all(
		"Team Member",
		filters={"status": "Active", **filters},
		fields=["name", "user", "full_name", "position", "subteam", "division", "slack_user_id"],
	)


def get_member(user=None):
	user = user or frappe.session.user
	rows = _members({"user": user})
	return rows[0] if rows else None


def get_division(subteam):
	return frappe.get_cached_value("Subteam", subteam, "division") if subteam else None


def is_captain(user=None):
	member = get_member(user)
	return bool(member and member.position == "Captain")


def exec_divisions(user=None):
	member = get_member(user)
	return {member.division} if member and member.position == "Exec" and member.division else set()


def lead_subteams(user=None):
	member = get_member(user)
	return {member.subteam} if member and member.position == "Subteam Lead" and member.subteam else set()


def is_admin(user=None):
	return (user or frappe.session.user) == "Administrator"


# ------------------------------------------------------------------ approvals
def can_approve(subteams, user=None):
	"""Captain: anything. Exec: any subteam in their division. Lead: their own subteam.

	`subteams` is a list; approving is allowed if the user covers any of them.
	With no subteam (vehicle BOM, team-wide purchases) only Execs and the Captain approve.
	"""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	member = get_member(user)
	if not member:
		return False
	if member.position == "Captain":
		return True
	subteams = [s for s in (subteams or []) if s]
	if member.position == "Exec":
		if not subteams:
			return True
		return any(get_division(s) == member.division for s in subteams)
	if member.position == "Subteam Lead":
		return member.subteam in subteams
	return False


def get_approvers(subteams, level="lead"):
	"""Users to @mention for an approval.

	level="lead": the subteams' Leads (falls back to Execs if a subteam has no Lead).
	level="exec": the divisions' Execs (falls back to the Captain), used for escalation.
	"""
	subteams = [s for s in (subteams or []) if s]
	users = []
	if level == "lead" and subteams:
		leads = _members({"position": "Subteam Lead", "subteam": ["in", subteams]})
		users = [m.user for m in leads]
		covered = {m.subteam for m in leads}
		if set(subteams) - covered:
			users += get_approvers([s for s in subteams if s not in covered], level="exec")
	else:
		divisions = {get_division(s) for s in subteams} - {None}
		execs = _members({"position": "Exec", "division": ["in", list(divisions)]}) if divisions else []
		if not subteams:
			execs = _members({"position": "Exec"})
		users = [m.user for m in execs]
		if not users:
			users = [m.user for m in _members({"position": "Captain"})]
	return list(dict.fromkeys(u for u in users if u))


# ------------------------------------------------------------------ positions
def can_manage(position, subteam=None, division=None, user=None):
	"""Can `user` assign or change someone in this position?

	Captain and Execs: changed by the Captain or Execs.
	Leads, Senior Design Members, Members: by that subteam's Lead, the division's Exec, or the Captain.
	"""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	member = get_member(user)
	if not member:
		return False
	if position in TOP_POSITIONS:
		return member.position in TOP_POSITIONS
	if member.position == "Captain":
		return True
	division = division or get_division(subteam)
	if member.position == "Exec":
		return bool(division) and member.division == division
	if member.position == "Subteam Lead":
		return bool(subteam) and member.subteam == subteam
	return False


def slack_mentions(users):
	"""'<@U123> <@U456>' for users linked to Slack; plain names for the rest."""
	if not users:
		return ""
	rows = frappe.get_all(
		"Team Member", filters={"user": ["in", list(users)]}, fields=["user", "full_name", "slack_user_id"]
	)
	by_user = {r.user: r for r in rows}
	parts = []
	for user in users:
		row = by_user.get(user)
		if row and row.slack_user_id:
			parts.append(f"<@{row.slack_user_id}>")
		else:
			parts.append(row.full_name if row else frappe.utils.get_fullname(user))
	return " ".join(parts)
