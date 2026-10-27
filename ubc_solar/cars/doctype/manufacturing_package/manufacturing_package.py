# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from ubc_solar.cars.utils import assert_car_editable, item_group, make_team_item


class ManufacturingPackage(Document):
	def validate(self):
		assert_car_editable(self.car, self)
		if self.is_new() and frappe.db.exists("Manufacturing Package", {"car": self.car, "subsystem": self.subsystem}):
			frappe.throw(_("{0} already has a manufacturing package for {1}.").format(self.car, self.subsystem))

	def after_insert(self):
		# The finished subsystem is a stock item used up when the car is built.
		# Vehicle harnesses aren't one finished thing: the vehicle BOM uses each harness directly.
		if not self.output_item and not frappe.db.get_value("Subsystem", self.subsystem, "is_vehicle_harnesses"):
			self.db_set("output_item", make_team_item(f"{self.car} {self.subsystem}", "Assembly", item_group("subsystems")))

	def onload(self):
		self.set_onload(
			"stages",
			frappe.get_all(
				"Manufacturing Stage",
				filters={"manufacturing_package": self.name},
				fields=["name", "stage_name", "sequence", "output_item", "manufacturing_bom", "is_final_stage", "total_minutes", "procedure_doc_url"],
				order_by="sequence asc",
			),
		)
