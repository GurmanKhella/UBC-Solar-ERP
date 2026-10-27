"""Number cards for the Sponsors section."""

import frappe
from frappe.utils import nowdate


@frappe.whitelist()
def follow_ups_due(filters=None):
	count = frappe.db.count(
		"Sponsor",
		{"next_follow_up": ["<=", nowdate()], "status": ["not in", ["Declined", "Past"]]},
	)
	return {"value": count, "fieldtype": "Int"}
