"""Helpers for the Mark Received dialog."""

import frappe
from frappe.utils import flt

from ubc_solar.cars.utils import default_location
from ubc_solar.solar_inventory.stock import excluded_locations, stock_by_location


def usual_shelf(item_code, receiving):
	"""The part's own shelf, else the shelf already holding most of it."""
	shelf = default_location(item_code)
	if shelf:
		return shelf
	skip = excluded_locations() | {receiving}
	for warehouse, _qty in stock_by_location(item_code):
		if warehouse not in skip:
			return warehouse
	return None


@frappe.whitelist()
def get_receivable(material_request: str):
	"""What's still to arrive on an ordered purchase, with each part's usual shelf."""
	mr = frappe.get_doc("Material Request", material_request)
	mr.check_permission("read")
	if not mr.solar_purchase_order:
		return []
	po = frappe.get_doc("Purchase Order", mr.solar_purchase_order)
	receiving = frappe.db.get_single_value("Solar Settings", "receiving_warehouse")
	rows = []
	for row in po.items:
		remaining = flt(row.qty) - flt(row.received_qty)
		if remaining <= 0:
			continue
		rows.append(
			{
				"item_code": row.item_code,
				"qty": remaining,
				"warehouse": usual_shelf(row.item_code, receiving) or receiving,
			}
		)
	return rows
