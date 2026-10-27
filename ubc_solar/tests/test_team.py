import frappe
from frappe.tests import IntegrationTestCase

from ubc_solar.setup.access import PROFILES
from ubc_solar.team import scope
from ubc_solar.tests.utils import as_user, make_member, unique


def roles_of(user):
	return set(frappe.get_roles(user)) - {"All", "Guest", "Desk User"}


class TestTeam(IntegrationTestCase):
	def test_new_member_gets_user_and_roles(self):
		m = make_member("Member", subteam="Embedded")
		self.assertEqual(m.user, m.email)
		self.assertEqual(m.division, "Electrical")
		self.assertEqual(m.status, "Active")
		self.assertTrue(set(PROFILES["Member Access"]) <= roles_of(m.user))
		self.assertNotIn("Solar Approver", roles_of(m.user))
		self.assertEqual(frappe.db.get_value("User", m.user, "user_type"), "System User")

	def test_lead_can_promote_in_own_subteam_only(self):
		lead = make_member("Subteam Lead", subteam="Embedded")
		member = make_member("Member", subteam="Embedded")
		other = make_member("Member", subteam="Aeroshell")
		with as_user(lead.user):
			member.reload()
			member.position = "Senior Design Member"
			member.save()
			self.assertIn("Solar Manufacturing Editor", roles_of(member.user))
			other.reload()
			other.position = "Senior Design Member"
			with self.assertRaises(frappe.PermissionError):
				other.save()

	def test_exec_scope_is_their_division(self):
		elec = make_member("Exec", division="Electrical")
		member = make_member("Member", subteam="Power & Signals")
		mech_member = make_member("Member", subteam="Structures")
		with as_user(elec.user):
			member.reload()
			member.position = "Subteam Lead"
			member.save()
			mech_member.reload()
			mech_member.position = "Subteam Lead"
			with self.assertRaises(frappe.PermissionError):
				mech_member.save()

	def test_only_captain_or_exec_assign_top_positions(self):
		lead = make_member("Subteam Lead", subteam="Dynamics")
		captain = make_member("Captain")
		member = make_member("Member", subteam="Dynamics")
		with as_user(lead.user):
			member.reload()
			member.position = "Exec"
			member.division = "Mechanical"
			with self.assertRaises(frappe.PermissionError):
				member.save()
		with as_user(captain.user):
			member.reload()
			member.position = "Exec"
			member.division = "Mechanical"
			member.save()
		self.assertIn("Solar Recruitment", roles_of(member.user))
		self.assertEqual(member.division, "Mechanical")

	def test_lead_cannot_promote_themselves(self):
		lead = make_member("Subteam Lead", subteam="Strategy")
		with as_user(lead.user):
			lead.reload()
			lead.position = "Exec"
			lead.division = "Electrical"
			with self.assertRaises(frappe.PermissionError):
				lead.save()

	def test_alumni_are_read_only(self):
		lead = make_member("Subteam Lead", subteam="Business")
		member = make_member("Member", subteam="Business")
		with as_user(lead.user):
			member.reload()
			member.position = "Alumni"
			member.save()
		self.assertEqual(member.status, "Alumni")
		self.assertTrue(member.left_on)
		self.assertEqual(roles_of(member.user), {"Solar Alumni"})
		self.assertTrue(frappe.has_permission("Item", "read", user=member.user))
		self.assertFalse(frappe.has_permission("Item", "write", user=member.user))
		self.assertFalse(frappe.has_permission("Applicant", "read", user=member.user))
		self.assertFalse(frappe.has_permission("Attendance Note", "read", user=member.user))

	def test_maintainer_flag(self):
		admin = make_member("Member", subteam="Embedded", is_erp_admin=1)
		self.assertIn("System Manager", roles_of(admin.user))
		lead = make_member("Subteam Lead", subteam="Embedded")
		member = make_member("Member", subteam="Embedded")
		with as_user(lead.user):
			member.reload()
			member.is_erp_admin = 1
			with self.assertRaises(frappe.PermissionError):
				member.save()

	def test_protected_areas(self):
		member = make_member("Member", subteam="Aeroshell")
		lead = make_member("Subteam Lead", subteam="Aeroshell")
		exec_ = make_member("Exec", division="Mechanical")
		senior = make_member("Senior Design Member", subteam="Aeroshell")
		self.assertFalse(frappe.has_permission("Attendance Note", "read", user=member.user))
		self.assertTrue(frappe.has_permission("Attendance Note", "create", user=lead.user))
		self.assertFalse(frappe.has_permission("Applicant", "read", user=lead.user))
		self.assertTrue(frappe.has_permission("Applicant", "read", user=exec_.user))
		self.assertFalse(frappe.has_permission("Manufacturing Package", "write", user=member.user))
		self.assertTrue(frappe.has_permission("Manufacturing Package", "read", user=member.user))
		self.assertTrue(frappe.has_permission("Manufacturing Package", "write", user=senior.user))
		self.assertTrue(frappe.has_permission("BOM", "write", user=member.user))

	def test_approval_scope(self):
		lead = make_member("Subteam Lead", subteam="Battery Management")
		elec = make_member("Exec", division="Electrical")
		captain = make_member("Captain")
		member = make_member("Member", subteam="Battery Management")
		self.assertTrue(scope.can_approve(["Battery Management"], user=lead.user))
		self.assertFalse(scope.can_approve(["Battery Mech"], user=lead.user))
		self.assertTrue(scope.can_approve(["Battery Management"], user=elec.user))
		self.assertFalse(scope.can_approve(["Battery Mech"], user=elec.user))
		self.assertTrue(scope.can_approve(["Battery Mech", "Battery Management"], user=elec.user))
		self.assertTrue(scope.can_approve(["Aeroshell"], user=captain.user))
		self.assertFalse(scope.can_approve(["Battery Management"], user=member.user))
		self.assertFalse(scope.can_approve([], user=lead.user))
		self.assertTrue(scope.can_approve([], user=elec.user))

	def test_approvers_fall_back_to_exec(self):
		lead = make_member("Subteam Lead", subteam="Power & Signals")
		elec = make_member("Exec", division="Electrical")
		self.assertIn(lead.user, scope.get_approvers(["Power & Signals"]))
		self.assertNotIn(elec.user, scope.get_approvers(["Power & Signals"]))
		# Strategy has no Lead in this test, so the Electrical Exec is asked.
		frappe.db.set_value("Team Member", {"position": "Subteam Lead", "subteam": "Strategy"}, "status", "Alumni")
		self.assertIn(elec.user, scope.get_approvers(["Strategy"]))
		self.assertIn(elec.user, scope.get_approvers(["Power & Signals"], level="exec"))

	def test_top_positions_can_restrict_access(self):
		captain = make_member("Captain")
		member = make_member("Member", subteam="Embedded")
		self.assertTrue(frappe.has_permission("User Permission", "create", user=captain.user))
		self.assertFalse(frappe.has_permission("User Permission", "create", user=member.user))

	def test_members_are_not_deleted(self):
		member = make_member("Member", subteam="Embedded")
		lead = make_member("Subteam Lead", subteam="Embedded")
		with as_user(lead.user), self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Team Member", member.name)


class TestConfigurableAccess(IntegrationTestCase):
	"""Access is changed in the ERP, not in code."""

	def restore_lead_profile(self):
		pos = frappe.get_doc("Team Position", "Subteam Lead")
		pos.role_profile = "Lead Access"
		pos.save()

	def test_give_every_lead_recruitment_through_their_profile(self):
		# A copy of Lead Access, so the test doesn't edit the real profile
		profile = frappe.copy_doc(frappe.get_doc("Role Profile", "Lead Access"))
		profile.role_profile = unique("Lead Access")
		profile.insert()
		pos = frappe.get_doc("Team Position", "Subteam Lead")
		pos.role_profile = profile.name
		pos.save()
		self.addCleanup(self.restore_lead_profile)
		lead = make_member("Subteam Lead", subteam="Embedded")
		self.assertFalse(frappe.has_permission("Applicant", "read", user=lead.user))
		profile.append("roles", {"role": "Solar Recruitment"})
		profile.save()  # the app re-applies the profile to its users straight away
		frappe.clear_cache(user=lead.user)
		self.assertTrue(frappe.has_permission("Applicant", "read", user=lead.user))

	def test_give_one_person_recruitment(self):
		lead = make_member("Subteam Lead", subteam="Embedded")
		other = make_member("Subteam Lead", subteam="Strategy")
		captain = make_member("Captain")
		with as_user(captain.user):
			lead.reload()
			lead.append("extra_access", {"role_profile": "Recruitment Access"})
			lead.save()
		frappe.clear_cache(user=lead.user)
		self.assertTrue(frappe.has_permission("Applicant", "read", user=lead.user))
		self.assertFalse(frappe.has_permission("Applicant", "read", user=other.user))
		# Changing someone's position keeps their extra access
		with as_user(captain.user):
			lead.reload()
			lead.position = "Member"
			lead.save()
		self.assertIn("Solar Recruitment", roles_of(lead.user))
		self.assertNotIn("Solar Approver", roles_of(lead.user))

	def test_nobody_hands_out_more_access_than_they_have(self):
		lead = make_member("Subteam Lead", subteam="Aeroshell")
		member = make_member("Member", subteam="Aeroshell")
		for profile in ("Captain Access", "ERP Maintainer Access", "Recruitment Access"):
			with as_user(lead.user), self.assertRaises(frappe.PermissionError):
				member.reload()
				member.append("extra_access", {"role_profile": profile})
				member.save()
		with as_user(lead.user):
			member.reload()
			member.append("extra_access", {"role_profile": "Attendance Access"})  # a Lead has attendance
			member.save()
			with self.assertRaises(frappe.PermissionError):
				lead.reload()
				lead.append("extra_access", {"role_profile": "Attendance Access"})
				lead.save()  # not on themselves
			with self.assertRaises(frappe.PermissionError):
				member.reload()
				member.append("also_approves_for", {"subteam": "Power & Signals"})  # outside the Lead's own approvals
				member.save()
		self.assertIn("Solar Attendance", roles_of(member.user))

		exec_ = make_member("Exec", division="Mechanical")
		with as_user(exec_.user):
			position = frappe.get_doc("Team Position", "Member")
			position.role_profile = "ERP Maintainer Access"
			with self.assertRaises(frappe.PermissionError):
				position.save()
		with as_user("Administrator"):
			member.reload()
			member.append("extra_access", {"role_profile": "Recruitment Access"})
			member.save()
		self.assertIn("Solar Recruitment", roles_of(member.user))

	def test_captain_edits_access_profiles_within_their_own_roles(self):
		captain = make_member("Captain")
		lead = make_member("Subteam Lead", subteam="Embedded")
		profile = frappe.copy_doc(frappe.get_doc("Role Profile", "Lead Access"))
		profile.role_profile = unique("Lead Access")
		profile.insert()
		admin_profile = frappe.get_doc(
			{"doctype": "Role Profile", "role_profile": unique("Maintainers"), "roles": [{"role": "System Manager"}]}
		).insert()
		lead.reload()
		lead.append("extra_access", {"role_profile": profile.name})
		lead.save()
		with as_user(captain.user):
			editable = frappe.get_doc("Role Profile", profile.name)
			editable.append("roles", {"role": "Solar Recruitment"})
			editable.save()
		frappe.clear_cache(user=lead.user)
		self.assertIn("Solar Recruitment", roles_of(lead.user))
		with as_user(captain.user):
			editable.reload()
			editable.append("roles", {"role": "System Manager"})
			with self.assertRaises(frappe.PermissionError):
				editable.save()
			maintainer = frappe.get_doc("Role Profile", admin_profile.name)
			maintainer.set("roles", [])
			with self.assertRaises(frappe.PermissionError):
				maintainer.save()
		member = make_member("Member", subteam="Embedded")
		with as_user(member.user), self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Role Profile", profile.name).save()

	def test_only_people_who_manage_them_can_change_access(self):
		member = make_member("Member", subteam="Aeroshell")
		other_lead = make_member("Subteam Lead", subteam="Dynamics")
		with as_user(other_lead.user):
			member.reload()
			member.append("extra_access", {"role_profile": "Recruitment Access"})
			with self.assertRaises(frappe.PermissionError):
				member.save()

	def test_extra_approval_subteam(self):
		member = make_member("Senior Design Member", subteam="Business")
		self.assertFalse(scope.can_approve(["Business"], user=member.user))
		member.append("also_approves_for", {"subteam": "Business"})
		member.flags.ignore_position_rules = True
		member.save()
		self.assertTrue(scope.can_approve(["Business"], user=member.user))
		self.assertFalse(scope.can_approve(["Aeroshell"], user=member.user))
		self.assertIn("Solar Approver", roles_of(member.user))
		self.assertIn(member.user, scope.get_approvers(["Business"]))

	def test_new_position(self):
		frappe.get_doc(
			{
				"doctype": "Team Position",
				"position_name": "Co-Captain",
				"role_profile": "Captain Access",
				"approval_scope": "Everything",
				"manage_scope": "Everything",
				"team_wide": 1,
				"assigned_by": [{"position": "Captain"}],
			}
		).insert()
		co = make_member("Co-Captain")
		self.assertTrue(scope.can_approve(["Aeroshell"], user=co.user))
		self.assertIn("Solar Car Manager", roles_of(co.user))
		member = make_member("Member", subteam="Aeroshell")
		with as_user(co.user):
			member.reload()
			member.position = "Subteam Lead"
			with self.assertRaises(frappe.PermissionError):
				member.save()  # Subteam Lead doesn't list Co-Captain as an assigner yet
		for name in ("Subteam Lead", "Member"):  # rights over both the old and the new position
			pos = frappe.get_doc("Team Position", name)
			pos.append("assigned_by", {"position": "Co-Captain"})
			pos.save()
		with as_user(co.user):
			member.reload()
			member.position = "Subteam Lead"
			member.save()
		self.assertIn("Solar Approver", roles_of(member.user))

	def test_approval_scope_alone_decides_who_approves(self):
		profile = frappe.get_doc({"doctype": "Role Profile", "role_profile": unique("Plain"), "roles": [{"role": "Solar Member"}]}).insert()
		frappe.get_doc(
			{
				"doctype": "Team Position",
				"position_name": "Purchasing Lead",
				"role_profile": profile.name,
				"approval_scope": "Own subteam",
				"needs_subteam": 1,
				"assigned_by": [{"position": "Captain"}],
			}
		).insert()
		person = make_member("Purchasing Lead", subteam="Aeroshell")
		self.assertIn("Solar Approver", roles_of(person.user))
		position = frappe.get_doc("Team Position", "Purchasing Lead")
		position.approval_scope = "None"
		position.save()
		self.assertNotIn("Solar Approver", roles_of(person.user))
		self.assertFalse(scope.can_approve(["Aeroshell"], user=person.user))

	def test_who_can_assign_a_position_is_configurable(self):
		member = make_member("Member", subteam="Aeroshell")
		senior = make_member("Senior Design Member", subteam="Aeroshell")
		senior.append("extra_access", {"role_profile": "Team Manager Access"})
		senior.save()
		with as_user(senior.user):
			member.reload()
			member.position = "Senior Design Member"
			with self.assertRaises(frappe.PermissionError):
				member.save()
		pos = frappe.get_doc("Team Position", "Senior Design Member")
		pos.manage_scope = "Own subteam"
		pos.save()
		for name in ("Senior Design Member", "Member"):  # rights over both the old and the new position
			target = frappe.get_doc("Team Position", name)
			target.append("assigned_by", {"position": "Senior Design Member"})
			target.save()
		with as_user(senior.user):
			member.reload()
			member.position = "Senior Design Member"
			member.save()
		self.assertEqual(frappe.db.get_value("Team Member", member.name, "position"), "Senior Design Member")

	def test_migrate_keeps_changes_made_in_the_erp(self):
		from ubc_solar.setup import install

		wf = frappe.get_doc("Workflow", "Purchase Approval")
		for t in wf.transitions:
			t.allow_self_approval = 0
		wf.save()
		frappe.get_doc("Custom Field", {"dt": "Item", "fieldname": "solar_vendor"}).db_set("label", "Supplier / Shop")
		pos = frappe.get_doc("Team Position", "Subteam Lead")
		pos.approval_scope = "Own division"
		pos.save()
		self.addCleanup(lambda: frappe.get_doc("Team Position", "Subteam Lead").update({"approval_scope": "Own subteam"}).save())
		install.sync()
		self.assertFalse(any(t.allow_self_approval for t in frappe.get_doc("Workflow", "Purchase Approval").transitions))
		self.assertEqual(frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": "solar_vendor"}, "label"), "Supplier / Shop")
		self.assertEqual(frappe.db.get_value("Team Position", "Subteam Lead", "approval_scope"), "Own division")
