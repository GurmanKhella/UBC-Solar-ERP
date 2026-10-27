# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowdate

from ubc_solar.solar_inventory.stock import check_member

OPEN_STATES = ("Draft", "Pending Approval", "Approved", "Ordered")


class ReorderPoint(Document):
	def validate(self):
		if flt(self.reorder_qty) <= 0:
			frappe.throw(_("Enter how much to order."))
		settings = frappe.get_cached_doc("Solar Settings")
		if not self.budget_line and frappe.db.get_value("Item", self.item_code, "solar_inventory_type") == "Shop Consumable":
			self.budget_line = settings.shop_supplies_line
		if not self.subteam and self.budget_line:
			self.subteam = frappe.db.get_value("Budget Line", self.budget_line, "subteam")
		if not self.subteam:
			self.subteam = settings.shop_supplies_subteam


def open_request(reorder_point):
	return frappe.db.get_value(
		"Material Request",
		{"solar_reorder_point": reorder_point, "docstatus": ["<", 2], "workflow_state": ["in", OPEN_STATES]},
		"name",
	)


@frappe.whitelist()
def request_reorder(reorder_point: str):
	"""Scanning a two-bin or reorder card: one purchase request, sent for approval.

	Scanning again while one is still open doesn't create another.
	"""
	check_member()
	point = frappe.get_doc("Reorder Point", reorder_point)
	if not point.enabled:
		frappe.throw(_("This reorder card is switched off."))
	existing = open_request(point.name)
	if existing:
		return {"name": existing, "created": False}

	mr = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": frappe.db.get_single_value("Solar Settings", "company"),
			"transaction_date": nowdate(),
			"solar_source": "Two-bin" if point.method == "Two-bin" else "Reorder card",
			"solar_reorder_point": point.name,
			"solar_subteam": point.subteam,
			"solar_budget_line": point.budget_line,
			"solar_requested_by": frappe.session.user,
			"items": [
				{
					"item_code": point.item_code,
					"qty": point.reorder_qty,
					"uom": frappe.db.get_value("Item", point.item_code, "stock_uom"),
					"conversion_factor": 1,
					"rate": point.estimated_rate,
					"warehouse": point.location if frappe.db.get_value("Item", point.item_code, "is_stock_item") else None,
				}
			],
		}
	)
	mr.insert(ignore_permissions=True)
	from frappe.model.workflow import apply_workflow

	apply_workflow(mr, "Request Approval")
	point.db_set({"last_requested_on": now_datetime(), "last_request": mr.name})
	return {"name": mr.name, "created": True}
