# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

from ubc_solar.setup.permissions import ADMIN_ROLES, MANAGED_ROLES, POSITION_ROLES
from ubc_solar.team import scope


class TeamMember(Document):
	def validate(self):
		self.email = (self.email or "").strip().lower()
		self.full_name = (self.full_name or "").strip()
		self.status = "Alumni" if self.position == "Alumni" else "Active"
		self.set_division()
		self.validate_required_placement()
		self.check_permission_to_change()
		self.track_position_change()

	def set_division(self):
		if self.position != "Exec" and self.subteam:
			self.division = scope.get_division(self.subteam)
		elif self.position == "Captain":
			self.division = None

	def validate_required_placement(self):
		if self.position in ("Subteam Lead", "Senior Design Member", "Member") and not self.subteam:
			frappe.throw(_("Pick a subteam for {0}.").format(self.position))
		if self.position == "Exec" and not self.division:
			frappe.throw(_("Pick the division this Exec leads."))

	def check_permission_to_change(self):
		if self.flags.ignore_position_rules:
			return
		before = self.get_doc_before_save()
		if before:
			unchanged = all(
				before.get(f) == self.get(f) for f in ("position", "subteam", "division", "is_erp_admin")
			)
			if unchanged and before.user == frappe.session.user:
				return  # people may fix their own name, Slack ID or notes
			# Offboarding to Alumni follows the rule of the position being left.
			if not scope.can_manage(before.position, before.subteam, before.division):
				frappe.throw(
					_("You can't change {0}: only {1} can.").format(
						self.full_name, describe_managers(before.position, before.subteam, before.division)
					),
					frappe.PermissionError,
				)
		if self.position != "Alumni" and not scope.can_manage(self.position, self.subteam, self.division):
			frappe.throw(
				_("You can't make someone {0} here: only {1} can.").format(
					self.position, describe_managers(self.position, self.subteam, self.division)
				),
				frappe.PermissionError,
			)
		if before and before.is_erp_admin != self.is_erp_admin and not (
			scope.is_admin() or "System Manager" in frappe.get_roles()
		):
			frappe.throw(_("Only an ERP administrator can change who is a maintainer."), frappe.PermissionError)
		if not before and self.is_erp_admin and not (scope.is_admin() or "System Manager" in frappe.get_roles()):
			frappe.throw(_("Only an ERP administrator can add a maintainer."), frappe.PermissionError)

	def track_position_change(self):
		before = self.get_doc_before_save()
		if before and before.position != self.position:
			self.previous_position = before.position
		if self.position == "Alumni":
			self.left_on = self.left_on or nowdate()
			self.is_erp_admin = 0
		else:
			self.left_on = None

	def before_insert(self):
		self.user = ensure_user(self.email, self.full_name, send_welcome=not self.flags.no_welcome_email)

	def on_update(self):
		sync_user_roles(self)
		if not self.slack_user_id and self.status == "Active":
			frappe.enqueue(
				"ubc_solar.solar_automation.slack.link_member_to_slack",
				member=self.name,
				enqueue_after_commit=True,
			)

	def on_trash(self):
		if not scope.is_admin():
			frappe.throw(
				_("Team members aren't deleted: offboard them to Alumni so their history stays."),
				frappe.PermissionError,
			)


def describe_managers(position, subteam=None, division=None):
	if position in scope.TOP_POSITIONS:
		return _("the Captain or an Exec")
	division = division or scope.get_division(subteam)
	return _("the {0} Lead, the {1} Exec or the Captain").format(subteam or "?", division or "?")


def ensure_user(email, full_name, send_welcome=True):
	if frappe.db.exists("User", email):
		return email
	first, _sep, last = (full_name or email).partition(" ")
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first,
			"last_name": last,
			"user_type": "System User",
			"send_welcome_email": 1 if send_welcome else 0,
		}
	)
	user.flags.ignore_permissions = True
	user.insert()
	return user.name


def sync_user_roles(member):
	"""Make the user's roles match their position (only roles this app manages)."""
	if not member.user or member.user in ("Administrator", "Guest"):
		return
	desired = set(POSITION_ROLES[member.position])
	if member.is_erp_admin and member.position != "Alumni":
		desired |= set(ADMIN_ROLES)
	user = frappe.get_doc("User", member.user)
	current = {r.role for r in user.roles}
	managed_current = current & set(MANAGED_ROLES)
	if managed_current == desired:
		return
	user.roles = [r for r in user.roles if r.role not in MANAGED_ROLES or r.role in desired]
	for role in sorted(desired - current):
		user.append("roles", {"role": role})
	user.flags.ignore_permissions = True
	user.save()


@frappe.whitelist()
def offboard(member: str, new_owner: str | None = None, new_approver: str | None = None):
	"""Offboard someone to Alumni: reassign their work, check equipment is back, change the role.

	Returns a summary of what was moved.
	"""
	doc = frappe.get_doc("Team Member", member)
	if doc.position == "Alumni":
		frappe.throw(_("{0} is already an alumnus.").format(doc.full_name))
	if not scope.can_manage(doc.position, doc.subteam, doc.division):
		frappe.throw(
			_("Only {0} can offboard {1}.").format(
				describe_managers(doc.position, doc.subteam, doc.division), doc.full_name
			),
			frappe.PermissionError,
		)
	user = doc.user

	equipment = frappe.get_all("Equipment", filters={"checked_out_to": user}, pluck="equipment_name")
	if equipment:
		frappe.throw(
			_("{0} still has equipment checked out: {1}. Return it first.").format(
				doc.full_name, ", ".join(equipment)
			)
		)

	projects = frappe.get_all("Solar Project", filters={"project_owner": user}, pluck="name")
	draft_boms = frappe.get_all("BOM", filters={"solar_bom_owner": user, "docstatus": 0}, pluck="name")
	open_purchases = frappe.get_all(
		"Material Request",
		filters={"solar_approver": user, "docstatus": 1, "workflow_state": ["in", ["Approved", "Ordered"]]},
		pluck="name",
	)
	sponsors = frappe.get_all("Sponsor", filters={"relationship_owner": user}, pluck="name")

	if (projects or draft_boms or sponsors) and not new_owner:
		frappe.throw(_("{0} owns projects, BOMs or sponsors. Pick a new owner.").format(doc.full_name))
	if open_purchases and not new_approver:
		frappe.throw(
			_("{0} owns open purchases ({1}). Pick who takes them over.").format(
				doc.full_name, ", ".join(open_purchases)
			)
		)
	if new_approver:
		mr_subteams = {frappe.db.get_value("Material Request", mr, "solar_subteam") for mr in open_purchases}
		if not all(scope.can_approve([s], user=new_approver) for s in mr_subteams):
			frappe.throw(_("{0} can't approve those purchases. Pick their Lead, Exec or the Captain.").format(new_approver))

	for name in projects:
		project = frappe.get_doc("Solar Project", name)
		project.project_owner = new_owner
		project.co_owners = [row for row in project.co_owners if row.user != user]
		project.flags.ignore_car_lock = True
		project.save(ignore_permissions=True)
	co_owned = frappe.get_all("Solar Project Co-owner", filters={"user": user, "parenttype": "Solar Project"}, pluck="parent")
	for name in set(co_owned):
		project = frappe.get_doc("Solar Project", name)
		project.co_owners = [row for row in project.co_owners if row.user != user]
		project.flags.ignore_car_lock = True
		project.save(ignore_permissions=True)
	for name in draft_boms:
		frappe.db.set_value("BOM", name, "solar_bom_owner", new_owner)
	for name in open_purchases:
		frappe.db.set_value("Material Request", name, "solar_approver", new_approver)
	for name in sponsors:
		frappe.db.set_value("Sponsor", name, "relationship_owner", new_owner)

	was_maintainer = doc.is_erp_admin
	doc.position = "Alumni"
	doc.save()

	summary = {
		"projects": projects,
		"boms": draft_boms,
		"purchases": open_purchases,
		"sponsors": sponsors,
		"was_maintainer": bool(was_maintainer),
	}
	return summary
