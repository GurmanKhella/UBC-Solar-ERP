# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""Spending rolled up from budget line to division to the whole team, so each
Exec sees their division's total."""

import frappe
from frappe import _
from frappe.utils import flt

from ubc_solar.money.budget import active_budget, get_budget_summary

KEYS = ("amount", "spent", "committed", "remaining")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	budget = filters.budget or active_budget()
	columns = [
		{"fieldname": "label", "label": _("Division / Line"), "fieldtype": "Data", "width": 260},
		{"fieldname": "budget_line", "label": _("Budget Line"), "fieldtype": "Link", "options": "Budget Line", "width": 200},
		{"fieldname": "priority", "label": _("Priority"), "fieldtype": "Data", "width": 110},
		{"fieldname": "amount", "label": _("Planned"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "spent", "label": _("Spent"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "committed", "label": _("Committed"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "remaining", "label": _("Left"), "fieldtype": "Currency", "width": 120},
	]
	if not budget:
		return columns, []
	s = get_budget_summary(budget)
	groups = {}
	for line in s["lines"]:
		groups.setdefault(line.get("division") or _("Team-wide"), []).append(line)
	rows = []
	for division in sorted(groups):
		lines = groups[division]
		rows.append({"label": division, **{k: sum(flt(line[k]) for line in lines) for k in KEYS}})
		for line in sorted(lines, key=lambda line: line["line_name"]):
			rows.append(
				{
					"label": line["line_name"],
					"budget_line": line["name"],
					"priority": line["priority"],
					**{k: flt(line[k]) for k in KEYS},
				}
			)
	rows.append({"label": _("Whole team"), **{k: sum(flt(line[k]) for line in s["lines"]) for k in KEYS}})
	message = _("Raised {0} of {1} minimum target · pledged {2} · available {3}").format(
		frappe.format(s["raised"], "Currency"),
		frappe.format(s["minimum_target"], "Currency"),
		frappe.format(s["pledged"], "Currency"),
		frappe.format(s["available"], "Currency"),
	)
	return columns, rows, message
