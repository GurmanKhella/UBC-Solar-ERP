# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""Who can see and do what: each member's position, access profiles, approval scope
and the roles those give them."""

import frappe
from frappe import _

from ubc_solar.team import scope


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {}
	if filters.position:
		conditions["position"] = filters.position
	if filters.subteam:
		conditions["subteam"] = filters.subteam
	if not filters.include_alumni:
		conditions["status"] = "Active"
	members = frappe.get_all(
		"Team Member",
		filters=conditions,
		fields=["name", "full_name", "user", "position", "subteam", "division", "is_erp_admin"],
		order_by="full_name asc",
	)
	rows = []
	for m in members:
		pos = scope.position(m.position)
		profiles = frappe.get_all("User Role Profile", filters={"parent": m.user, "parenttype": "User"}, pluck="role_profile")
		roles = sorted(
			r for r in frappe.get_all("Has Role", filters={"parent": m.user, "parenttype": "User"}, pluck="role")
			if r.startswith("Solar") or r == "System Manager"
		)
		extra = frappe.get_all("Team Member Approval Subteam", filters={"parent": m.name, "parenttype": "Team Member"}, pluck="subteam")
		approves = pos.approval_scope if pos else ""
		if approves == "Own subteam":
			approves = m.subteam or ""
		elif approves == "Own division":
			approves = f"{m.division} division" if m.division else ""
		elif approves == "None":
			approves = ""
		approves = ", ".join(x for x in [approves, *extra] if x)
		rows.append(
			{
				"member": m.name,
				"full_name": m.full_name,
				"position": m.position,
				"subteam": m.subteam,
				"access": ", ".join(profiles),
				"approves_for": approves,
				"roles": ", ".join(r.replace("Solar ", "") for r in roles),
			}
		)
	columns = [
		{"fieldname": "member", "label": _("Member"), "fieldtype": "Link", "options": "Team Member", "width": 180},
		{"fieldname": "full_name", "label": _("Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "position", "label": _("Position"), "fieldtype": "Link", "options": "Team Position", "width": 140},
		{"fieldname": "subteam", "label": _("Subteam"), "fieldtype": "Link", "options": "Subteam", "width": 140},
		{"fieldname": "access", "label": _("Access Profiles"), "fieldtype": "Data", "width": 220},
		{"fieldname": "approves_for", "label": _("Approves For"), "fieldtype": "Data", "width": 180},
		{"fieldname": "roles", "label": _("Roles"), "fieldtype": "Data", "width": 360},
	]
	return columns, rows
