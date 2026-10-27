# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""Perishables (prepreg, solder paste) expiring soon or already expired."""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, nowdate

from ubc_solar.solar_inventory.tasks import expiring_batches


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = []
	for b in expiring_batches(days=cint(filters.days) if filters.days else None):
		days_left = date_diff(b.expiry_date, nowdate())
		rows.append(
			{
				"batch": b.name,
				"item": b.item,
				"item_name": b.item_name,
				"qty": b.qty,
				"expiry_date": b.expiry_date,
				"days_left": days_left,
				"state": _("Expired") if days_left < 0 else _("Expiring"),
			}
		)
	columns = [
		{"fieldname": "item", "label": _("Part"), "fieldtype": "Link", "options": "Item", "width": 150},
		{"fieldname": "item_name", "label": _("Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "batch", "label": _("Batch"), "fieldtype": "Link", "options": "Batch", "width": 140},
		{"fieldname": "qty", "label": _("Left"), "fieldtype": "Float", "width": 80},
		{"fieldname": "expiry_date", "label": _("Expires"), "fieldtype": "Date", "width": 110},
		{"fieldname": "days_left", "label": _("Days Left"), "fieldtype": "Int", "width": 90},
		{"fieldname": "state", "label": _("State"), "fieldtype": "Data", "width": 90},
	]
	return columns, rows
