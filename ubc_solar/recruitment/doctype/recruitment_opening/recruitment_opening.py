# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RecruitmentOpening(Document):
	def validate(self):
		self.opening_title = (self.opening_title or "").strip()


@frappe.whitelist()
def copy_from(opening: str, from_opening: str):
	"""Reuse (and then edit) a previous cycle's description and technical challenge."""
	doc = frappe.get_doc("Recruitment Opening", opening)
	doc.check_permission("write")
	source = frappe.get_doc("Recruitment Opening", from_opening)
	source.check_permission("read")
	doc.description = source.description
	doc.challenge_instructions = source.challenge_instructions
	doc.subteam = doc.subteam or source.subteam
	doc.position = source.position
	doc.copied_from = source.name
	doc.save()
	for file in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Recruitment Opening", "attached_to_name": source.name},
		fields=["file_url", "file_name", "is_private"],
	):
		frappe.get_doc(
			{
				"doctype": "File",
				"file_url": file.file_url,
				"file_name": file.file_name,
				"is_private": file.is_private,
				"attached_to_doctype": "Recruitment Opening",
				"attached_to_name": doc.name,
			}
		).insert(ignore_permissions=True)
	return doc.name
