# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""Equipment marked needs repair or missing, and (optionally) anything not checked
in the last walk-through."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	days = cint(frappe.db.get_single_value("Solar Settings", "equipment_check_days")) or 120
	since = add_days(nowdate(), -days)
	equipment = frappe.get_all(
		"Equipment",
		fields=["name", "equipment_name", "category", "condition", "location", "group_location", "checked_out_to", "last_checked_on"],
		order_by="condition desc, equipment_name asc",
	)
	rows = []
	for eq in equipment:
		reasons = []
		if eq.condition != "Working":
			reasons.append(eq.condition)
		if filters.include_unchecked and (not eq.last_checked_on or str(eq.last_checked_on) < str(since)):
			reasons.append(_("Not checked since {0}").format(since))
		if reasons:
			rows.append({**eq, "reason": ", ".join(reasons), "where": eq.group_location or eq.location})
	columns = [
		{"fieldname": "name", "label": _("Equipment"), "fieldtype": "Link", "options": "Equipment", "width": 100},
		{"fieldname": "equipment_name", "label": _("Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "category", "label": _("Category"), "fieldtype": "Data", "width": 140},
		{"fieldname": "reason", "label": _("Why"), "fieldtype": "Data", "width": 220},
		{"fieldname": "where", "label": _("Home"), "fieldtype": "Data", "width": 170},
		{"fieldname": "checked_out_to", "label": _("Checked Out To"), "fieldtype": "Link", "options": "User", "width": 160},
		{"fieldname": "last_checked_on", "label": _("Last Checked"), "fieldtype": "Date", "width": 110},
	]
	return columns, rows
