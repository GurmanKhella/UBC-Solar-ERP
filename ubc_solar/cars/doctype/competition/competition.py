# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from ubc_solar.cars.utils import assert_car_editable


class Competition(Document):
	def validate(self):
		assert_car_editable(self.car, self)
		if self.vehicle_bom:
			vehicle_item = frappe.db.get_value("Car", self.car, "vehicle_item")
			bom = frappe.db.get_value("BOM", self.vehicle_bom, ["item", "docstatus"], as_dict=True)
			if bom.item != vehicle_item:
				frappe.throw(_("{0} isn't a vehicle BOM version of {1}.").format(self.vehicle_bom, self.car))
			if bom.docstatus != 1:
				frappe.throw(_("Pick an approved vehicle BOM version."))
		if self.start_date and self.end_date and getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("The end date is before the start date."))
		for row in self.support_items:
			if not (row.item_code or row.equipment or row.description):
				frappe.throw(_("Support BOM row {0}: pick a part or equipment, or describe it.").format(row.idx))


@frappe.whitelist()
def copy_support_items(competition: str, from_competition: str):
	"""Reuse a past competition's support BOM (packing ticks are cleared)."""
	doc = frappe.get_doc("Competition", competition)
	doc.check_permission("write")
	source = frappe.get_doc("Competition", from_competition)
	source.check_permission("read")
	existing = {(r.item_code, r.equipment, r.description) for r in doc.support_items}
	added = 0
	for row in source.support_items:
		key = (row.item_code, row.equipment, row.description)
		if key in existing:
			continue
		doc.append(
			"support_items",
			{
				"category": row.category,
				"item_code": row.item_code,
				"equipment": row.equipment,
				"description": row.description,
				"qty": row.qty,
				"packed": 0,
			},
		)
		added += 1
	doc.save()
	return added


@frappe.whitelist()
def check_out_packed_equipment(competition: str):
	"""Check out every packed piece of equipment to this competition."""
	doc = frappe.get_doc("Competition", competition)
	doc.check_permission("write")
	from ubc_solar.solar_inventory.doctype.equipment.equipment import check_out

	done = []
	for row in doc.support_items:
		if row.equipment and row.packed:
			if not frappe.db.get_value("Equipment", row.equipment, "checked_out_to"):
				check_out(row.equipment, purpose=_("Competition: {0}").format(doc.name), competition=doc.name)
				done.append(row.equipment)
	return done
