# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from ubc_solar.cars.utils import (
	assert_car_editable,
	car_subteams,
	make_team_item,
	vehicle_harness_subsystem,
)
from ubc_solar.team import scope


class SolarProject(Document):
	def validate(self):
		self.project_name = (self.project_name or "").strip()
		assert_car_editable(self.car, self)
		self.validate_unique_name()
		if self.project_type == "Harness":
			self.place_harness()
		else:
			self.harness_category = self.from_project = self.to_project = None
			self.validate_subsystem()
		self.division = scope.get_division(self.subteam)
		seen = {self.project_owner}
		rows = []
		for row in self.co_owners:
			if row.user and row.user not in seen:
				seen.add(row.user)
				rows.append(row)
		self.co_owners = rows

	def validate_unique_name(self):
		clash = frappe.db.get_value(
			"Solar Project",
			{"car": self.car, "project_name": self.project_name, "name": ["!=", self.name]},
		)
		if clash:
			frappe.throw(_("{0} already has a project called {1} ({2}).").format(self.car, self.project_name, clash))

	def validate_subsystem(self):
		if self.subsystem:
			if frappe.db.get_value("Subsystem", self.subsystem, "is_vehicle_harnesses"):
				frappe.throw(_("Only harnesses go in {0}.").format(self.subsystem))
		elif self.subteam in car_subteams():
			frappe.throw(_("Pick the subsystem this project belongs to."))

	def place_harness(self):
		"""Same subsystem at both ends: lives in that subsystem. Different: Vehicle harnesses."""
		if not (self.from_project and self.to_project):
			frappe.throw(_("A harness needs a From project and a To project."))
		if self.from_project == self.to_project:
			frappe.throw(_("A harness connects two different projects."))
		ends = {}
		for field in ("from_project", "to_project"):
			ends[field] = frappe.db.get_value(
				"Solar Project", self.get(field), ["car", "subsystem", "project_type"], as_dict=True
			)
			if ends[field].car != self.car:
				frappe.throw(_("{0} is on a different car.").format(self.get(field)))
			if ends[field].project_type == "Harness":
				frappe.throw(_("Harnesses connect projects, not other harnesses."))
		self.from_subsystem = ends["from_project"].subsystem
		self.to_subsystem = ends["to_project"].subsystem
		if self.from_subsystem and self.from_subsystem == self.to_subsystem:
			self.subsystem = self.from_subsystem
		else:
			self.subsystem = vehicle_harness_subsystem()

	@property
	def external_name(self):
		"""The name used in Drive and Monday."""
		return f"{self.car} {self.project_name}"

	def after_insert(self):
		self.create_part()
		self.create_erpnext_project()
		frappe.enqueue(
			"ubc_solar.solar_automation.drive.create_project_doc",
			project=self.name,
			enqueue_after_commit=True,
		)
		frappe.enqueue(
			"ubc_solar.solar_automation.monday.create_project_item",
			project=self.name,
			enqueue_after_commit=True,
		)

	def create_part(self):
		if self.part:
			return
		if self.project_type == "Harness":
			discipline, group = "Electrical", "Harnesses"
		else:
			discipline = {"Electrical": "Electrical", "Mechanical": "Mechanical"}.get(self.division, "Assembly")
			group = "Assemblies"
		item = make_team_item(self.external_name, discipline, group, project=self.name)
		self.db_set("part", item)

	def create_erpnext_project(self):
		"""ERPNext's Projects module is set up with the same names but hidden while Monday stays."""
		if self.erpnext_project:
			return
		project = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": self.external_name,
				"company": frappe.db.get_single_value("Solar Settings", "company"),
				"status": "Open",
			}
		)
		project.insert(ignore_permissions=True)
		self.db_set("erpnext_project", project.name)

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.project_name != self.project_name:
			if self.part:
				frappe.db.set_value("Item", self.part, "item_name", self.external_name[:140])
			if self.erpnext_project:
				frappe.db.set_value("Project", self.erpnext_project, "project_name", self.external_name)
			frappe.enqueue(
				"ubc_solar.solar_automation.drive.rename_project_doc",
				project=self.name,
				enqueue_after_commit=True,
			)
			frappe.enqueue(
				"ubc_solar.solar_automation.monday.rename_project_item",
				project=self.name,
				enqueue_after_commit=True,
			)

	def owners(self):
		return [self.project_owner, *[r.user for r in self.co_owners]]
