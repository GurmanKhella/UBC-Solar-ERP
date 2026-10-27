# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BudgetLine(Document):
	def autoname(self):
		self.name = f"{self.line_name.strip()} - {self.budget}"

	def validate(self):
		self.line_name = (self.line_name or "").strip()
		if self.subteam:
			self.division = frappe.get_cached_value("Subteam", self.subteam, "division")
		if flt(self.amount) < 0:
			frappe.throw(_("The planned amount can't be negative."))
		clash = frappe.db.get_value(
			"Budget Line", {"budget": self.budget, "line_name": self.line_name, "name": ["!=", self.name]}
		)
		if clash:
			frappe.throw(_("{0} already has a line called {1}.").format(self.budget, self.line_name))

	def on_update(self):
		update_minimum_target(self.budget)

	def after_delete(self):
		update_minimum_target(self.budget)

	def onload(self):
		if not self.is_new():
			from ubc_solar.money.budget import committed_by_line, spent_by_line

			committed = committed_by_line([self.name]).get(self.name, 0)
			spent = spent_by_line([self.name]).get(self.name, 0)
			self.set_onload(
				"summary",
				{"committed": committed, "spent": spent, "remaining": flt(self.amount) - committed - spent},
			)


def update_minimum_target(budget):
	total = sum(flt(a) for a in frappe.get_all("Budget Line", filters={"budget": budget}, pluck="amount"))
	frappe.db.set_value("Solar Budget", budget, "minimum_target", total)
