"""Number cards for the Inventory section."""

import frappe

from ubc_solar.solar_inventory.tasks import expiring_batches


@frappe.whitelist()
def expiring_soon(filters=None):
	return {"value": len(expiring_batches()), "fieldtype": "Int"}
