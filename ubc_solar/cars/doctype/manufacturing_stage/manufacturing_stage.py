# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from ubc_solar.cars.utils import assert_car_editable


class ManufacturingStage(Document):
	def validate(self):
		package = frappe.db.get_value(
			"Manufacturing Package", self.manufacturing_package, ["car", "subsystem", "output_item"], as_dict=True
		)
		self.car, self.subsystem = package.car, package.subsystem
		assert_car_editable(self.car, self)
		self.stage_name = (self.stage_name or "").strip()

		if self.is_final_stage:
			if not package.output_item:
				frappe.throw(_("{0} has no finished subsystem part, so it has no final stage.").format(self.subsystem))
			self.output_item = package.output_item
			other = frappe.db.get_value(
				"Manufacturing Stage",
				{"manufacturing_package": self.manufacturing_package, "is_final_stage": 1, "name": ["!=", self.name]},
			)
			if other:
				frappe.throw(_("{0} is already the final stage.").format(other))

		if self.manufacturing_bom:
			bom_item = frappe.db.get_value("BOM", self.manufacturing_bom, "item")
			if self.output_item and bom_item != self.output_item:
				frappe.throw(_("The manufacturing BOM must be for {0}, the part this stage produces.").format(self.output_item))

		self.total_minutes = sum(cint(s.minutes) for s in self.steps)
		self.people_needed = max([cint(s.people) for s in self.steps] or [0])

	def after_insert(self):
		frappe.enqueue(
			"ubc_solar.solar_automation.drive.create_procedure_doc",
			stage=self.name,
			enqueue_after_commit=True,
		)

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.stage_name != self.stage_name and self.drive_doc_id:
			frappe.enqueue(
				"ubc_solar.solar_automation.drive.rename_procedure_doc",
				stage=self.name,
				enqueue_after_commit=True,
			)
