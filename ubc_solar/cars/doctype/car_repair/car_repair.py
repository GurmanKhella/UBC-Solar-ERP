# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from ubc_solar.cars.utils import assert_car_editable
from ubc_solar.solar_inventory.stock import make_stock_entry, pick_sources


class CarRepair(Document):
	def validate(self):
		assert_car_editable(self.car, self)
		if self.solar_project:
			project = frappe.db.get_value("Solar Project", self.solar_project, ["car", "subsystem"], as_dict=True)
			if project.car != self.car:
				frappe.throw(_("{0} belongs to {1}, not {2}.").format(self.solar_project, project.car, self.car))
			self.solar_subsystem = self.solar_subsystem or project.subsystem
		for row in self.parts:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: enter a quantity.").format(row.idx))
			if not row.source_warehouse:
				picks = pick_sources(row.item_code, row.qty)
				row.source_warehouse = picks[0][0] if picks else None
		if self.changes_design and self.new_bom:
			bom_project = frappe.db.get_value("BOM", self.new_bom, "solar_project")
			if self.solar_project and bom_project != self.solar_project:
				frappe.throw(_("The new BOM version should be for {0}.").format(self.solar_project))
		if self.status == "Fixed":
			self.fixed_on = self.fixed_on or nowdate()
			self.fixed_by = self.fixed_by or frappe.session.user

	def on_update(self):
		if self.status == "Fixed":
			self.issue_parts()

	def issue_parts(self):
		"""Deduct the parts used (from stock or competition spares), once."""
		rows = [r for r in self.parts if not r.stock_entry]
		if not rows:
			return
		missing = [r.item_code for r in rows if not r.source_warehouse]
		if missing:
			frappe.throw(_("Pick where these parts came from: {0}").format(", ".join(missing)))
		se = make_stock_entry(
			"Material Issue",
			[{"item_code": r.item_code, "qty": flt(r.qty), "s_warehouse": r.source_warehouse} for r in rows],
			source="Repair",
			car=self.car,
			reference=self,
		)
		for r in rows:
			r.db_set("stock_entry", se.name)
		self.add_comment("Info", _("Parts deducted from stock: {0}").format(se.name))
