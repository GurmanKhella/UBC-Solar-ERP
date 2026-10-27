# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class FundingEntry(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Enter the amount."))
		if self.status == "Received" and not self.received_on:
			self.received_on = nowdate()
		elif self.status == "Pledged":
			self.received_on = None
