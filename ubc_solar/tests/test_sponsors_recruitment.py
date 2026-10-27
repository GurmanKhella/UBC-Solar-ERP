import frappe
from frappe.tests import IntegrationTestCase

from ubc_solar.money.budget import get_budget_summary
from ubc_solar.recruitment.doctype.applicant.applicant import accept
from ubc_solar.recruitment.doctype.recruitment_opening.recruitment_opening import copy_from
from ubc_solar.sponsors.doctype.sponsor_donation.sponsor_donation import receive_parts
from ubc_solar.tests.test_cars_money import make_budget
from ubc_solar.tests.utils import as_user, make_item, make_member, stock_qty, unique


class TestSponsors(IntegrationTestCase):
	def test_donations_flow_into_budget_and_stock(self):
		budget = make_budget([("Battery", "Battery Mech", 2000)])
		sponsor = frappe.get_doc({"doctype": "Sponsor", "sponsor_name": unique("Sponsor"), "status": "Committed"}).insert(
			ignore_permissions=True
		)
		frappe.get_doc(
			{"doctype": "Sponsor Donation", "sponsor": sponsor.name, "donation_type": "Money", "status": "Received", "amount": 1500, "budget": budget}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{"doctype": "Sponsor Donation", "sponsor": sponsor.name, "donation_type": "Money", "status": "Pledged", "amount": 500, "budget": budget}
		).insert(ignore_permissions=True)
		cell = make_item("Buy", mpn=unique("CELL"))
		parts = frappe.get_doc(
			{
				"doctype": "Sponsor Donation",
				"sponsor": sponsor.name,
				"donation_type": "Parts",
				"status": "Pledged",
				"amount": 1,
				"budget": budget,
				"items": [{"item_code": cell.name, "qty": 20, "value_per_unit": 8}],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(parts.amount, 160)
		receive_parts(parts.name)
		parts.reload()
		self.assertEqual(parts.status, "Received")
		self.assertEqual(stock_qty(cell.name), 20)
		se = frappe.get_doc("Stock Entry", parts.stock_entry)
		self.assertEqual((se.solar_source, se.solar_reference_name), ("Donation", parts.name))
		with self.assertRaises(frappe.ValidationError):
			receive_parts(parts.name)
		s = get_budget_summary(budget)
		self.assertEqual((s["raised"], s["pledged"], s["in_kind"]), (1500, 500, 160))

	def test_sponsor_contacts_link(self):
		sponsor = frappe.get_doc({"doctype": "Sponsor", "sponsor_name": unique("Sponsor")}).insert(ignore_permissions=True)
		contact = frappe.get_doc(
			{"doctype": "Contact", "first_name": "Pat", "links": [{"link_doctype": "Sponsor", "link_name": sponsor.name}]}
		).insert(ignore_permissions=True)
		sponsor.run_method("onload")
		contacts = sponsor.get_onload().get("contact_list")
		self.assertEqual([c.name for c in contacts], [contact.name])


class TestRecruitment(IntegrationTestCase):
	def setUp(self):
		self.cycle = frappe.get_doc({"doctype": "Recruitment Cycle", "cycle_name": unique("Fall")}).insert(ignore_permissions=True)
		self.opening = frappe.get_doc(
			{
				"doctype": "Recruitment Opening",
				"opening_title": unique("Electrical member"),
				"cycle": self.cycle.name,
				"subteam": "Power & Signals",
				"status": "Published",
				"challenge_instructions": "<p>Design a buck converter</p>",
			}
		).insert(ignore_permissions=True)

	def apply(self, email=None, opening=None):
		return frappe.get_doc(
			{
				"doctype": "Applicant",
				"full_name": "Sam Applicant",
				"email": email or f"{unique('a')}@example.com",
				"opening": opening or self.opening.name,
				"consent": 1,
			}
		).insert(ignore_permissions=True)

	def test_accept_creates_member(self):
		applicant = self.apply()
		self.assertEqual(applicant.cycle, self.cycle.name)
		exec_ = make_member("Exec", division="Mechanical")  # any Exec can accept, whatever the division
		with as_user(exec_.user):
			member = accept(applicant.name)
		m = frappe.get_doc("Team Member", member)
		self.assertEqual((m.position, m.subteam, m.status), ("Member", "Power & Signals", "Active"))
		self.assertIn("Solar Member", frappe.get_roles(m.user))
		self.assertEqual(frappe.db.get_value("Applicant", applicant.name, "status"), "Accepted")

	def test_only_execs_and_captain_see_recruitment(self):
		applicant = self.apply()
		lead = make_member("Subteam Lead", subteam="Power & Signals")
		with as_user(lead.user), self.assertRaises(frappe.PermissionError):
			accept(applicant.name)

	def test_closed_openings_and_duplicates_rejected(self):
		applicant = self.apply()
		with self.assertRaises(frappe.ValidationError):
			self.apply(email=applicant.email)
		frappe.db.set_value("Recruitment Opening", self.opening.name, "status", "Closed")
		with self.assertRaises(frappe.ValidationError):
			self.apply()

	def test_copy_challenge_from_previous_opening(self):
		new = frappe.get_doc(
			{"doctype": "Recruitment Opening", "opening_title": unique("Electrical member next"), "cycle": self.cycle.name}
		).insert(ignore_permissions=True)
		copy_from(new.name, self.opening.name)
		new.reload()
		self.assertIn("buck converter", new.challenge_instructions)
		self.assertEqual(new.copied_from, self.opening.name)
