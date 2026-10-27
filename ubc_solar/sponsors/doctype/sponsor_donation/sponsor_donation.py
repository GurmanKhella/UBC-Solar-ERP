# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from ubc_solar.solar_inventory.stock import make_stock_entry


class SponsorDonation(Document):
	def validate(self):
		if not self.budget:
			from ubc_solar.money.budget import active_budget

			self.budget = active_budget()
		if self.donation_type == "Parts" and self.items:
			values = [flt(r.qty) * flt(r.value_per_unit) for r in self.items]
			if any(values):
				self.amount = sum(values)
		else:
			if self.donation_type != "Parts":
				self.items = []
		if flt(self.amount) <= 0:
			frappe.throw(_("Enter the amount (or, for parts, their value)."))
		if self.status == "Received":
			self.date_received = self.date_received or nowdate()


@frappe.whitelist()
def receive_parts(donation: str):
	"""Donated parts arrive: put them into stock, linked to this donation and its sponsor."""
	doc = frappe.get_doc("Sponsor Donation", donation)
	doc.check_permission("write")
	if doc.donation_type != "Parts":
		frappe.throw(_("Only parts donations go into stock."))
	if doc.stock_entry:
		frappe.throw(_("These parts are already in stock ({0}).").format(doc.stock_entry))
	if not doc.items:
		frappe.throw(_("List the donated parts first."))
	receiving = frappe.db.get_single_value("Solar Settings", "receiving_warehouse")
	se = make_stock_entry(
		"Material Receipt",
		[
			{
				"item_code": r.item_code,
				"qty": flt(r.qty),
				"t_warehouse": r.warehouse or receiving,
				"basic_rate": flt(r.value_per_unit),
			}
			for r in doc.items
		],
		source="Donation",
		reference=doc,
	)
	doc.db_set({"stock_entry": se.name, "status": "Received", "date_received": doc.date_received or nowdate()})
	return se.name
