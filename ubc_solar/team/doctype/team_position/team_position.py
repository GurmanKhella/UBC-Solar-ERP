# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TeamPosition(Document):
	def validate(self):
		self.position_name = (self.position_name or "").strip()
		if self.is_alumni:
			other = frappe.db.get_value("Team Position", {"is_alumni": 1, "name": ["!=", self.name]})
			if other:
				frappe.throw(_("{0} is already the alumni position.").format(other))
			self.approval_scope = "None"
			self.manage_scope = "None"
		if self.needs_division and self.needs_subteam:
			frappe.throw(_("A position belongs either to a subteam or leads a division, not both."))
		before = self.get_doc_before_save()
		if not before or before.role_profile != self.role_profile:
			from ubc_solar.team import scope

			scope.check_can_grant([self.role_profile])

	def on_update(self):
		frappe.clear_document_cache("Team Position", self.name)
		before = self.get_doc_before_save()
		if before and (before.role_profile, before.approval_scope) != (self.role_profile, self.approval_scope):
			from ubc_solar.team.doctype.team_member.team_member import resync_position

			resync_position(self.name)
