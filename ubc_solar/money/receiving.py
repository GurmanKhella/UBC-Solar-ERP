"""Helpers for the Mark Received dialog."""

import frappe
from frappe.utils import flt

from ubc_solar.cars.utils import default_location


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
				"warehouse": default_location(row.item_code) or row.warehouse or receiving,
			}
		)
	return rows
