"""Who sits where on the team, and what that lets them do.

Nothing here names a position. Each Team Position record says what scope it
approves for and which members its holders can manage, so the team changes
these rules in the ERP (Team > Positions) rather than in code.
"""

import frappe
from frappe import _

EVERYTHING, DIVISION, SUBTEAM, NONE = "Everything", "Own division", "Own subteam", "None"


def position(name):
	"""Team Position settings (cached)."""
	if not name:
		return None
	return frappe.get_cached_doc("Team Position", name)


def alumni_positions():
	return frappe.get_all("Team Position", filters={"is_alumni": 1}, pluck="name")


def _members(filters):
	rows = frappe.get_all(
		"Team Member",
		filters={"status": "Active", **filters},
		fields=["name", "user", "full_name", "position", "subteam", "division", "slack_user_id"],
	)
	return rows


def get_member(user=None):
	user = user or frappe.session.user
	rows = _members({"user": user})
	if not rows:
		return None
	member = rows[0]
	member.also_approves_for = set(
		frappe.get_all(
			"Team Member Approval Subteam",
			filters={"parent": member.name, "parenttype": "Team Member"},
			pluck="subteam",
		)
	)
	return member


def get_division(subteam):
	return frappe.get_cached_value("Subteam", subteam, "division") if subteam else None


def is_admin(user=None):
	return (user or frappe.session.user) == "Administrator"


def is_maintainer(user=None):
	user = user or frappe.session.user
	return is_admin(user) or "System Manager" in frappe.get_roles(user)


def check_can_grant(role_profiles, user=None):
	"""People can only hand out access they have themselves (maintainers can hand out anything)."""
	user = user or frappe.session.user
	if is_maintainer(user):
		return
	mine = set(frappe.get_roles(user))
	for profile in role_profiles:
		missing = set(frappe.get_all("Has Role", filters={"parent": profile, "parenttype": "Role Profile"}, pluck="role")) - mine
		if missing:
			frappe.throw(
				_("You can't give {0}: it includes {1}, which you don't have. Ask an ERP maintainer.").format(
					profile, ", ".join(sorted(missing))
				),
				frappe.PermissionError,
			)


def approval_scope(member):
	pos = position(member.position) if member else None
	return pos.approval_scope if pos else NONE


# ------------------------------------------------------------------ approvals
def can_approve(subteams, user=None):
	"""Can `user` approve something belonging to these subteams?

	Uses the position's approval scope (own subteam / own division / everything)
	plus the member's own "Also Approves For" subteams. Approving is allowed if the
	user covers any of the subteams. Something with no subteam (the whole car, a
	team-wide purchase) needs division-wide or team-wide scope.
	"""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	member = get_member(user)
	if not member:
		return False
	subteams = [s for s in (subteams or []) if s]
	scope = approval_scope(member)
	if scope == EVERYTHING:
		return True
	if not subteams:
		return scope == DIVISION
	if member.also_approves_for & set(subteams):
		return True
	if scope == DIVISION:
		return any(get_division(s) == member.division for s in subteams)
	if scope == SUBTEAM:
		return member.subteam in subteams
	return False


def has_wider_scope(subteam, user=None):
	"""Division-wide or team-wide approver for this subteam (a stand-in for the owner)."""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	member = get_member(user)
	scope = approval_scope(member)
	if scope == EVERYTHING:
		return True
	return scope == DIVISION and bool(subteam) and get_division(subteam) == member.division


def _positions_with(scope):
	return frappe.get_all("Team Position", filters={"approval_scope": scope}, pluck="name")


def get_approvers(subteams, level="lead"):
	"""Users to @mention for an approval.

	level="lead": subteam-scope approvers of these subteams (and anyone who also
	approves for them); a subteam nobody covers falls back to division-scope.
	level="exec": division-scope approvers of their divisions, else team-wide ones.
	"""
	subteams = [s for s in (subteams or []) if s]
	users = []
	if level == "lead" and subteams:
		covered = set()
		positions = _positions_with(SUBTEAM)
		if positions:
			for m in _members({"position": ["in", positions], "subteam": ["in", subteams]}):
				users.append(m.user)
				covered.add(m.subteam)
		extra = frappe.get_all(
			"Team Member Approval Subteam",
			filters={"subteam": ["in", subteams], "parenttype": "Team Member"},
			fields=["parent", "subteam"],
		)
		for row in extra:
			m = frappe.db.get_value("Team Member", row.parent, ["user", "status"], as_dict=True)
			if m and m.status == "Active":
				users.append(m.user)
				covered.add(row.subteam)
		missing = [s for s in subteams if s not in covered]
		if missing:
			users += get_approvers(missing, level="exec")
	else:
		division_positions = _positions_with(DIVISION)
		divisions = {get_division(s) for s in subteams} - {None}
		if division_positions:
			filters = {"position": ["in", division_positions]}
			if subteams:
				filters["division"] = ["in", list(divisions) or [""]]
			users = [m.user for m in _members(filters)]
		if not users:
			top = _positions_with(EVERYTHING)
			users = [m.user for m in _members({"position": ["in", top]})] if top else []
	return list(dict.fromkeys(u for u in users if u))


# ------------------------------------------------------------------ positions
def can_manage(target_position, subteam=None, division=None, user=None):
	"""Can `user` put someone into (or take someone out of) `target_position`?

	The user's position must be listed in the target's "Who Can Give Someone This
	Position", and the member must fall within the user's management scope (not
	checked for team-wide positions such as Captain and Exec).
	"""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	member = get_member(user)
	target = position(target_position)
	if not member or not target:
		return False
	if member.position not in {row.position for row in target.assigned_by}:
		return False
	if target.team_wide:
		return True
	scope = position(member.position).manage_scope
	division = division or get_division(subteam)
	if scope == EVERYTHING:
		return True
	if scope == DIVISION:
		return bool(division) and member.division == division
	if scope == SUBTEAM:
		return bool(subteam) and member.subteam == subteam
	return False


def describe_managers(target_position, subteam=None, division=None):
	target = position(target_position)
	names = ", ".join(row.position for row in target.assigned_by) if target else ""
	if not names:
		return "an ERP administrator"
	if target.team_wide:
		return names
	where = subteam or division or "this subteam"
	return f"{names} (with {where} in their scope)"


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
