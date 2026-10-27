"""Role Profiles are now applied straight away (team/role_profile.py). Release the locks
Frappe's queued version left behind, so the profiles can be edited at once."""

import frappe


def execute():
	for name in frappe.get_all("Role Profile", pluck="name"):
		frappe.get_doc("Role Profile", name).unlock()
