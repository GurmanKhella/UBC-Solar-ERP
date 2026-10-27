import frappe
from frappe.tests import IntegrationTestCase

from ubc_solar.setup.permissions import POSITION_ROLES
from ubc_solar.team import scope
from ubc_solar.tests.utils import as_user, make_member


def roles_of(user):
	return set(frappe.get_roles(user)) - {"All", "Guest", "Desk User"}


class TestTeam(IntegrationTestCase):
	def test_new_member_gets_user_and_roles(self):
		m = make_member("Member", subteam="Embedded")
		self.assertEqual(m.user, m.email)
		self.assertEqual(m.division, "Electrical")
		self.assertEqual(m.status, "Active")
		self.assertTrue(set(POSITION_ROLES["Member"]) <= roles_of(m.user))
		self.assertNotIn("Solar Lead", roles_of(m.user))
		self.assertEqual(frappe.db.get_value("User", m.user, "user_type"), "System User")

	def test_lead_can_promote_in_own_subteam_only(self):
		lead = make_member("Subteam Lead", subteam="Embedded")
		member = make_member("Member", subteam="Embedded")
		other = make_member("Member", subteam="Aeroshell")
		with as_user(lead.user):
			member.reload()
			member.position = "Senior Design Member"
			member.save()
			self.assertIn("Solar Senior Designer", roles_of(member.user))
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
		self.assertIn("Solar Exec", roles_of(member.user))
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
