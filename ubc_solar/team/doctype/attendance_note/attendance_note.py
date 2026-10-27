# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AttendanceNote(Document):
	def validate(self):
		if self.until_date and getdate(self.until_date) < getdate(self.date):
			frappe.throw(_("Until can't be before the date."))
		if self.is_new():
			self.recorded_by = frappe.session.user
