# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""Every harness on a car, wherever it sits, counted once. Filter by a project to
find every harness touching it (e.g. when a connector changes on a board)."""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {"project_type": "Harness"}
	if filters.car:
		conditions["car"] = filters.car
	if filters.harness_category:
		conditions["harness_category"] = filters.harness_category
	or_filters = None
	if filters.project:
		or_filters = {"from_project": filters.project, "to_project": filters.project}
	rows = frappe.get_list(
		"Solar Project",
		filters=conditions,
		or_filters=or_filters,
		fields=["name", "project_name", "car", "harness_category", "from_project", "from_subsystem", "to_project", "to_subsystem", "subsystem", "part", "status"],
		order_by="car desc, harness_category asc, project_name asc",
	)
	names = {r.from_project for r in rows} | {r.to_project for r in rows}
	titles = dict(frappe.get_all("Solar Project", filters={"name": ["in", list(names)]}, fields=["name", "project_name"], as_list=True)) if names else {}
	for r in rows:
		r.from_title = titles.get(r.from_project, r.from_project)
		r.to_title = titles.get(r.to_project, r.to_project)
		r.bom = frappe.db.get_value("Item", r.part, "default_bom") if r.part else None
	columns = [
		{"fieldname": "name", "label": _("Harness"), "fieldtype": "Link", "options": "Solar Project", "width": 110},
		{"fieldname": "project_name", "label": _("Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "car", "label": _("Car"), "fieldtype": "Link", "options": "Car", "width": 70},
		{"fieldname": "harness_category", "label": _("Category"), "fieldtype": "Link", "options": "Harness Category", "width": 90},
		{"fieldname": "from_title", "label": _("From"), "fieldtype": "Data", "width": 170},
		{"fieldname": "from_subsystem", "label": _("From Subsystem"), "fieldtype": "Link", "options": "Subsystem", "width": 130},
		{"fieldname": "to_title", "label": _("To"), "fieldtype": "Data", "width": 170},
		{"fieldname": "to_subsystem", "label": _("To Subsystem"), "fieldtype": "Link", "options": "Subsystem", "width": 130},
		{"fieldname": "subsystem", "label": _("Lives In"), "fieldtype": "Link", "options": "Subsystem", "width": 130},
		{"fieldname": "part", "label": _("Part Number"), "fieldtype": "Link", "options": "Item", "width": 110},
		{"fieldname": "bom", "label": _("Active BOM"), "fieldtype": "Link", "options": "BOM", "width": 140},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
	]
	return columns, rows
