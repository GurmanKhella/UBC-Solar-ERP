# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Applicant(Document):
	def validate(self):
		self.email = (self.email or "").strip().lower()
		self.full_name = (self.full_name or "").strip()
		if not self.consent:
			frappe.throw(_("Please confirm you've read how application data is kept."))
		if self.is_new() and frappe.db.get_value("Recruitment Opening", self.opening, "status") != "Published":
			frappe.throw(_("This opening isn't taking applications."))
		if self.is_new() and frappe.db.exists("Applicant", {"email": self.email, "opening": self.opening}):
			frappe.throw(_("You've already applied for this opening."))
		before = self.get_doc_before_save()
		if before and before.status == "Accepted" and self.status != "Accepted" and self.team_member:
			frappe.throw(_("This applicant already has an account. Offboard them from the Team instead."))
		if self.status == "Accepted" and not self.team_member and not self.flags.accepting:
			frappe.throw(_("Use Accept and Create Account so their ERP account is set up."))


@frappe.whitelist()
def accept(applicant: str):
	"""Accept an applicant: create their account with their subteam and role, so onboarding starts."""
	doc = frappe.get_doc("Applicant", applicant)
	doc.check_permission("write")
	if doc.team_member:
		return doc.team_member
	opening = frappe.db.get_value("Recruitment Opening", doc.opening, ["subteam", "position"], as_dict=True)
	if not opening.subteam:
		frappe.throw(_("Set the subteam on {0} first.").format(doc.opening))
	existing = frappe.db.get_value("Team Member", {"email": doc.email})
	if existing:
		member = frappe.get_doc("Team Member", existing)
		if member.position == "Alumni":
			member.position = opening.position or "Member"
			member.subteam = opening.subteam
			member.flags.ignore_position_rules = True  # recruitment decides; only Execs and the Captain get here
			member.save()
	else:
		member = frappe.get_doc(
			{
				"doctype": "Team Member",
				"full_name": doc.full_name,
				"email": doc.email,
				"position": opening.position or "Member",
				"subteam": opening.subteam,
				"joined_on": frappe.utils.nowdate(),
			}
		)
		member.flags.ignore_position_rules = True
		member.insert()
	doc.status = "Accepted"
	doc.team_member = member.name
	doc.flags.accepting = True
	doc.save()
	return member.name
