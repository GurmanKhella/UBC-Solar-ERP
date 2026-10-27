# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SolarBudget(Document):
	def validate(self):
		if not self.is_new():
			self.minimum_target = sum(
				flt(a) for a in frappe.get_all("Budget Line", filters={"budget": self.name}, pluck="amount")
			)

	def on_update(self):
		if not self.is_active:
			return
		for other in frappe.get_all("Solar Budget", filters={"is_active": 1, "name": ["!=", self.name]}, pluck="name"):
			frappe.db.set_value("Solar Budget", other, "is_active", 0)
		frappe.db.set_single_value("Solar Settings", "active_budget", self.name)
		shop = frappe.db.get_value("Budget Line", {"budget": self.name, "is_shop_supplies": 1}, "name")
		if shop:
			frappe.db.set_single_value("Solar Settings", "shop_supplies_line", shop)
		frappe.clear_document_cache("Solar Settings", "Solar Settings")

	def onload(self):
		if not self.is_new():
			from ubc_solar.money.budget import get_budget_summary

			self.set_onload("summary", get_budget_summary(self.name))
