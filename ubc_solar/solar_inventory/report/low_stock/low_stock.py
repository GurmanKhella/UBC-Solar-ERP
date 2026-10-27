# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""Parts below their reorder level (set on the Item's Auto re-order table).

This only flags them; consumables are reordered by scanning two-bin and reorder
cards, and nothing is ordered on a schedule."""

import frappe
from frappe import _
from frappe.utils import flt


def qty_in(item_code, warehouse):
	lft, rgt, is_group = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt", "is_group"])
	if not is_group:
		return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))
	return flt(
		frappe.db.sql(
			"""select sum(b.actual_qty) from tabBin b join tabWarehouse w on w.name = b.warehouse
			where b.item_code = %s and w.lft >= %s and w.rgt <= %s""",
			(item_code, lft, rgt),
		)[0][0]
	)


def execute(filters=None):
	rows = []
	levels = frappe.get_all(
		"Item Reorder",
		filters={"parenttype": "Item"},
		fields=["parent as item_code", "warehouse", "warehouse_group", "warehouse_reorder_level", "warehouse_reorder_qty"],
	)
	for level in levels:
		where = level.warehouse_group or level.warehouse
		if not where:
			continue
		qty = qty_in(level.item_code, where)
		if qty <= flt(level.warehouse_reorder_level):
			item = frappe.db.get_value("Item", level.item_code, ["item_name", "stock_uom", "solar_inventory_type", "disabled"], as_dict=True)
			if item.disabled:
				continue
			rows.append(
				{
					"item_code": level.item_code,
					"item_name": item.item_name,
					"inventory_type": item.solar_inventory_type,
					"location": where,
					"qty": qty,
					"reorder_level": level.warehouse_reorder_level,
					"reorder_qty": level.warehouse_reorder_qty,
					"uom": item.stock_uom,
				}
			)
	columns = [
		{"fieldname": "item_code", "label": _("Part"), "fieldtype": "Link", "options": "Item", "width": 150},
		{"fieldname": "item_name", "label": _("Name"), "fieldtype": "Data", "width": 220},
		{"fieldname": "inventory_type", "label": _("Type"), "fieldtype": "Data", "width": 140},
		{"fieldname": "location", "label": _("Location"), "fieldtype": "Link", "options": "Warehouse", "width": 180},
		{"fieldname": "qty", "label": _("In Stock"), "fieldtype": "Float", "width": 90},
		{"fieldname": "reorder_level", "label": _("Reorder Level"), "fieldtype": "Float", "width": 110},
		{"fieldname": "reorder_qty", "label": _("Usual Order"), "fieldtype": "Float", "width": 100},
		{"fieldname": "uom", "label": _("Unit"), "fieldtype": "Data", "width": 70},
	]
	return columns, sorted(rows, key=lambda r: r["item_name"] or "")
