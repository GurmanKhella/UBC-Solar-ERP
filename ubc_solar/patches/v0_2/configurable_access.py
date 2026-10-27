"""Move from fixed position roles to configurable Team Positions and Role Profiles."""

import frappe

OLD_ROLES = ["Solar Captain", "Solar Exec", "Solar Lead", "Solar Senior Designer"]


def execute():
	from ubc_solar.setup import access, permissions, workflows
	from ubc_solar.team.doctype.team_member.team_member import sync_user_roles

	access.create_all()
	frappe.db.delete("Custom DocPerm", {"role": ["in", OLD_ROLES]})
	permissions.apply()
	workflows.apply()
	for spec in (workflows.BOM_REVIEW, workflows.PURCHASE_APPROVAL):
		workflows.make_workflow(spec)  # rebuild once with the new roles

	for name in frappe.get_all("Team Member", pluck="name"):
		sync_user_roles(frappe.get_doc("Team Member", name))

	for role in OLD_ROLES:
		if frappe.db.exists("Role", role):
			frappe.delete_doc("Role", role, force=True, ignore_permissions=True)
	frappe.clear_cache()
