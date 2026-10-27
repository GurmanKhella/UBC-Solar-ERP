# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

from ubc_solar.setup.access import APPROVER_PROFILE, MAINTAINER_PROFILE
from ubc_solar.team import scope

PLACEMENT_FIELDS = ("position", "subteam", "division", "is_erp_admin")
ACCESS_FIELDS = ("extra_access", "also_approves_for")


class TeamMember(Document):
	def validate(self):
		self.email = (self.email or "").strip().lower()
		self.full_name = (self.full_name or "").strip()
		pos = scope.position(self.position)
		if not pos:
			frappe.throw(_("Pick a position."))
		self.status = "Alumni" if pos.is_alumni else "Active"
		self.set_division(pos)
		self.validate_required_placement(pos)
		self.check_permission_to_change()
		self.track_position_change(pos)

	def set_division(self, pos):
		if self.subteam and not pos.needs_division:
			self.division = scope.get_division(self.subteam)
		elif pos.team_wide and not pos.needs_division:
			self.division = None

	def validate_required_placement(self, pos):
		if pos.needs_subteam and not self.subteam:
			frappe.throw(_("Pick a subteam for {0}.").format(self.position))
		if pos.needs_division and not self.division:
			frappe.throw(_("Pick the division this {0} leads.").format(self.position))

	def access_changed(self, before):
		def rows(doc, field, key):
			return sorted(r.get(key) for r in doc.get(field) or [])

		return rows(before, "extra_access", "role_profile") != rows(self, "extra_access", "role_profile") or rows(
			before, "also_approves_for", "subteam"
		) != rows(self, "also_approves_for", "subteam")

	def check_permission_to_change(self):
		if self.flags.ignore_position_rules:
			return
		before = self.get_doc_before_save()
		if before:
			placement_same = all(before.get(f) == self.get(f) for f in PLACEMENT_FIELDS)
			if placement_same and not self.access_changed(before):
				return  # name, Slack ID, notes: anyone allowed to edit the record
			# Offboarding to Alumni follows the rule of the position being left.
			if not scope.can_manage(before.position, before.subteam, before.division):
				frappe.throw(
					_("You can't change {0}: only {1} can.").format(
						self.full_name, scope.describe_managers(before.position, before.subteam, before.division)
					),
					frappe.PermissionError,
				)
		if not scope.position(self.position).is_alumni and not scope.can_manage(self.position, self.subteam, self.division):
			frappe.throw(
				_("You can't make someone {0} here: only {1} can.").format(
					self.position, scope.describe_managers(self.position, self.subteam, self.division)
				),
				frappe.PermissionError,
			)
		admin_changed = (before.is_erp_admin != self.is_erp_admin) if before else bool(self.is_erp_admin)
		if admin_changed and not (scope.is_admin() or "System Manager" in frappe.get_roles()):
			frappe.throw(_("Only an ERP administrator can change who is a maintainer."), frappe.PermissionError)

	def track_position_change(self, pos):
		before = self.get_doc_before_save()
		if before and before.position != self.position:
			self.previous_position = before.position
		if pos.is_alumni:
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


def role_profiles_for(member):
	"""The position's Role Profile, plus extra access, plus the automatic ones."""
	pos = scope.position(member.position)
	profiles = [pos.role_profile] if pos and pos.role_profile else []
	if pos and not pos.is_alumni:
		profiles += [row.role_profile for row in member.get("extra_access") or []]
		if member.get("also_approves_for") and pos.approval_scope == scope.NONE:
			profiles.append(APPROVER_PROFILE)
		if member.is_erp_admin:
			profiles.append(MAINTAINER_PROFILE)
	return [p for p in dict.fromkeys(profiles) if p and frappe.db.exists("Role Profile", p)]


def sync_user_roles(member):
	"""Give the user exactly the roles of their Role Profiles (Frappe applies them)."""
	if not member.user or member.user in ("Administrator", "Guest"):
		return
	wanted = role_profiles_for(member)
	user = frappe.get_doc("User", member.user)
	current = [row.role_profile for row in user.role_profiles]
	if sorted(current) == sorted(wanted) and user.roles:
		return
	user.set("role_profiles", [{"role_profile": p} for p in wanted])
	if not wanted:
		user.set("roles", [])
	user.flags.ignore_permissions = True
	user.save()


def role_profile_updated(doc, method=None):
	"""Apply an edited Role Profile to its users now (Frappe also queues this in the background)."""
	users = frappe.get_all("User Role Profile", filters={"role_profile": doc.name, "parenttype": "User"}, pluck="parent")
	for user in set(users):
		if user in ("Administrator", "Guest"):
			continue
		user_doc = frappe.get_doc("User", user)
		user_doc.flags.ignore_permissions = True
		user_doc.save()


def resync_position(position):
	"""After a position's Role Profile changes, update everyone in it."""
	for name in frappe.get_all("Team Member", filters={"position": position}, pluck="name"):
		sync_user_roles(frappe.get_doc("Team Member", name))


@frappe.whitelist()
def offboard(member: str, new_owner: str | None = None, new_approver: str | None = None):
	"""Offboard someone to Alumni: reassign their work, check equipment is back, change the role.

	Returns a summary of what was moved.
	"""
	doc = frappe.get_doc("Team Member", member)
	alumni = scope.alumni_positions()
	if not alumni:
		frappe.throw(_("No position is marked as the alumni position (Team > Positions)."))
	if doc.position in alumni:
		frappe.throw(_("{0} is already an alumnus.").format(doc.full_name))
	if not scope.can_manage(doc.position, doc.subteam, doc.division):
		frappe.throw(
			_("Only {0} can offboard {1}.").format(
				scope.describe_managers(doc.position, doc.subteam, doc.division), doc.full_name
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
		if not all(scope.can_approve([s] if s else [], user=new_approver) for s in mr_subteams):
			frappe.throw(_("{0} can't approve those purchases. Pick someone who approves for them.").format(new_approver))

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
	doc.position = alumni[0]
	doc.save()

	return {
		"projects": projects,
		"boms": draft_boms,
		"purchases": open_purchases,
		"sponsors": sponsors,
		"was_maintainer": bool(was_maintainer),
	}
