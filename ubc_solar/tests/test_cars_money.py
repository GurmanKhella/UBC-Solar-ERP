import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from ubc_solar.cars.parts import new_revision
from ubc_solar.money.budget import get_budget_summary
from ubc_solar.money.purchasing import mark_ordered, mark_received
from ubc_solar.tests.utils import (
	add_stock,
	as_user,
	make_item,
	make_location,
	make_member,
	stock_qty,
	unique,
)


def make_budget(lines):
	name = unique("Budget")
	frappe.get_doc({"doctype": "Solar Budget", "budget_name": name, "is_active": 1}).insert(ignore_permissions=True)
	for line_name, subteam, amount in lines:
		frappe.get_doc(
			{"doctype": "Budget Line", "budget": name, "line_name": line_name, "subteam": subteam, "amount": amount}
		).insert(ignore_permissions=True)
	frappe.get_doc("Solar Budget", name).save(ignore_permissions=True)
	frappe.clear_document_cache("Solar Settings", "Solar Settings")
	return name


def make_car(status="In Design"):
	version = unique("VT")
	return frappe.get_doc({"doctype": "Car", "car_version": version, "car_name": "Test", "status": status}).insert(
		ignore_permissions=True
	)


def make_project(car, name=None, subteam="Battery Management", subsystem="Battery", owner=None, **kw):
	doc = frappe.get_doc(
		{
			"doctype": "Solar Project",
			"project_name": name or unique("Project"),
			"car": car,
			"subteam": subteam,
			"subsystem": subsystem,
			"project_owner": owner or "Administrator",
			**kw,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def make_bom(item, rows, project=None, quantity=1):
	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": item,
			"quantity": quantity,
			"company": frappe.db.get_single_value("Solar Settings", "company"),
			"currency": "CAD",
			"solar_project": project,
			"items": [{"item_code": code, "qty": qty, "rate": rate} for code, qty, rate in rows],
		}
	)
	bom.insert(ignore_permissions=True)
	return bom


class TestPartsAndCars(IntegrationTestCase):
	def test_part_numbers(self):
		made = make_item("Make", discipline="Mechanical", item_group="Mechanical Parts")
		self.assertRegex(made.name, r"^M-\d{4}-A$")
		self.assertEqual(made.solar_base_part_number + "-A", made.name)
		elec = make_item("Make", discipline="Electrical")
		self.assertRegex(elec.name, r"^E-\d{4}-A$")
		bought = make_item("Buy", mpn="RC0603FR-0710KL-T1")
		self.assertEqual(bought.name, "RC0603FR-0710KL-T1")
		self.assertEqual(bought.default_material_request_type, "Purchase")
		rev_b = new_revision(made.name)
		self.assertEqual(rev_b, made.solar_base_part_number + "-B")
		self.assertEqual(frappe.db.get_value("Item", rev_b, "solar_revision"), "B")
		no_mpn = make_item("Buy", mpn=None, item_name="Mystery widget")
		self.assertRegex(no_mpn.name, r"^B-\d{4}$")

	def test_inventory_types(self):
		consumable = make_item("Buy", mpn=unique("ZIPTIE"), inventory_type="Shop Consumable")
		self.assertEqual(consumable.is_stock_item, 0)
		prepreg = make_item("Buy", mpn=unique("PREPREG"), inventory_type="Perishable")
		self.assertEqual((prepreg.has_batch_no, prepreg.has_expiry_date), (1, 1))

	def test_car_gets_vehicle_item(self):
		car = make_car()
		car.reload()
		self.assertTrue(car.vehicle_item)
		self.assertEqual(frappe.db.get_value("Item", car.vehicle_item, "item_group"), "Vehicles")
		self.assertEqual(car.car_title, f"{car.car_version} Test")
		car.status = "Retired"
		with self.assertRaises(frappe.ValidationError):
			car.save()

	def test_project_part_and_hidden_project(self):
		car = make_car()
		project = make_project(car.name, name="BMS Slave Board")
		project.reload()
		self.assertRegex(project.part, r"^E-\d{4}-A$")
		self.assertEqual(frappe.db.get_value("Item", project.part, "solar_project"), project.name)
		self.assertEqual(frappe.db.get_value("Project", project.erpnext_project, "project_name"), f"{car.name} BMS Slave Board")
		self.assertEqual(project.division, "Electrical")
		with self.assertRaises(frappe.ValidationError):
			make_project(car.name, name="BMS Slave Board")
		with self.assertRaises(frappe.ValidationError):
			make_project(car.name, subsystem=None)  # Battery Management builds car parts
		embedded = make_project(car.name, subteam="Embedded", subsystem=None)
		self.assertFalse(embedded.subsystem)

	def test_harness_placement(self):
		car = make_car()
		modules = make_project(car.name, subteam="Battery Mech")
		bms = make_project(car.name)
		mc = make_project(car.name, subteam="Power & Signals", subsystem="Power and Signals")
		inside = make_project(car.name, project_type="Harness", subteam="Battery Management", subsystem=None,
			harness_category="LV", from_project=modules.name, to_project=bms.name)
		self.assertEqual(inside.subsystem, "Battery")
		between = make_project(car.name, project_type="Harness", subteam="Power & Signals", subsystem=None,
			harness_category="HV", from_project=bms.name, to_project=mc.name)
		self.assertEqual(between.subsystem, "Vehicle harnesses")
		self.assertEqual(frappe.db.get_value("Item", between.part, "item_group"), "Harnesses")

	def test_retired_car_is_view_only(self):
		car = make_car("Active")
		project = make_project(car.name)
		from ubc_solar.cars.doctype.car.car import retire_car

		with as_user("Administrator"):
			retire_car(car.name)
		self.assertEqual(frappe.db.get_value("Car", car.name, "status"), "Retired")
		lead = make_member("Subteam Lead", subteam="Battery Management")
		with as_user(lead.user):
			project.reload()
			project.description = "change"
			with self.assertRaises(frappe.ValidationError):
				project.save()


class TestBomToBuild(IntegrationTestCase):
	def setUp(self):
		self.lead = make_member("Subteam Lead", subteam="Battery Management")
		self.other_lead = make_member("Subteam Lead", subteam="Aeroshell")
		self.member = make_member("Member", subteam="Battery Management")
		self.budget = make_budget([("BMS", "Battery Management", 5000)])
		self.car = make_car()
		self.project = make_project(self.car.name, owner=self.member.user)
		self.project.reload()
		self.shelf = make_location(unique("E-A"))
		self.ic = make_item("Buy", mpn=unique("LTC6811"), valuation_rate=18.5)
		self.res = make_item("Buy", mpn=unique("RC0603"), inventory_type="Small Part", valuation_rate=0.1)
		add_stock(self.res.name, 30, self.shelf, rate=0.1)

	def approve_bom(self):
		bom = make_bom(self.project.part, [(self.ic.name, 2, 18.5), (self.res.name, 40, 0.1)], project=self.project.name)
		self.assertEqual(bom.solar_bom_kind, "Project")
		self.assertEqual(bom.solar_subteam, "Battery Management")
		self.assertEqual(bom.solar_bom_owner, self.member.user)
		with as_user(self.member.user):
			apply_workflow(bom, "Mark Ready for Review")
		bom.reload()
		self.assertEqual(bom.workflow_state, "Ready for Review")
		with as_user(self.other_lead.user), self.assertRaises(frappe.PermissionError):
			apply_workflow(bom, "Approve")
		with as_user(self.lead.user):
			apply_workflow(bom, "Approve")
		bom.reload()
		self.assertEqual((bom.docstatus, bom.workflow_state, bom.solar_approved_by), (1, "Approved", self.lead.user))
		return bom

	def test_bom_approval_creates_approved_purchase(self):
		bom = self.approve_bom()
		mr = frappe.get_doc("Material Request", bom.solar_purchase_request)
		self.assertEqual((mr.docstatus, mr.workflow_state, mr.solar_approver), (1, "Approved", self.lead.user))
		self.assertEqual(mr.solar_source, "BOM")
		self.assertEqual(mr.solar_requested_by, self.member.user)
		qty = {r.item_code: r.qty for r in mr.items}
		self.assertEqual(qty[self.ic.name], 2)
		self.assertEqual(qty[self.res.name], 10)  # 40 needed, 30 in stock
		self.assertEqual(mr.solar_budget_line, f"BMS - {self.budget}")
		summary = get_budget_summary(self.budget)
		self.assertAlmostEqual(summary["committed"], 2 * 18.5 + 10 * 0.1, places=2)

	def test_order_receive_build(self):
		bom = self.approve_bom()
		mr = frappe.get_doc("Material Request", bom.solar_purchase_request)
		receipt = frappe.get_doc(
			{"doctype": "File", "file_name": "receipt.txt", "content": b"receipt", "is_private": 1}
		).insert(ignore_permissions=True)
		with as_user(self.member.user), self.assertRaises(frappe.PermissionError):
			mark_ordered(mr.name, "Digi-Key", receipt.file_url)
		with as_user(self.lead.user):
			po = mark_ordered(mr.name, "Digi-Key", receipt.file_url, "DK-123", {self.ic.name: 19.0})
		mr.reload()
		self.assertEqual(mr.workflow_state, "Ordered")
		self.assertEqual(mr.solar_purchase_order, po)
		summary = get_budget_summary(self.budget)
		self.assertAlmostEqual(summary["committed"], 0, places=2)
		self.assertAlmostEqual(summary["spent"], 2 * 19.0 + 10 * 0.1, places=2)

		with as_user(self.lead.user):
			mark_received(
				mr.name,
				[
					{"item_code": self.ic.name, "qty": 2, "warehouse": self.shelf},
					{"item_code": self.res.name, "qty": 10, "warehouse": self.shelf},
				],
			)
		mr.reload()
		self.assertEqual(mr.workflow_state, "Received")
		self.assertEqual(stock_qty(self.ic.name, self.shelf), 2)
		self.assertEqual(stock_qty(self.res.name, self.shelf), 40)

		build = frappe.get_doc({"doctype": "Build Record", "bom": bom.name, "qty": 1, "built_by": self.member.user})
		with as_user(self.member.user):
			build.insert()
			build.submit()
		self.assertEqual(stock_qty(self.ic.name, self.shelf), 0)
		self.assertEqual(stock_qty(self.res.name, self.shelf), 0)
		self.assertEqual(stock_qty(self.project.part), 1)
		self.assertEqual(frappe.db.get_value("Solar Project", self.project.name, "status"), "Built")

	def test_build_blocks_when_parts_missing(self):
		bom = self.approve_bom()
		build = frappe.get_doc({"doctype": "Build Record", "bom": bom.name, "qty": 1})
		build.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			build.submit()

	def test_manual_purchase_needs_scoped_approval(self):
		with as_user(self.member.user):
			mr = frappe.get_doc(
				{
					"doctype": "Material Request",
					"material_request_type": "Purchase",
					"company": frappe.db.get_single_value("Solar Settings", "company"),
					"transaction_date": frappe.utils.nowdate(),
					"solar_subteam": "Battery Management",
					"items": [{"item_code": self.ic.name, "qty": 1, "rate": 20, "uom": "Nos", "conversion_factor": 1}],
				}
			).insert()
			self.assertEqual(mr.workflow_state, "Draft")
			self.assertEqual(mr.solar_budget_line, f"BMS - {self.budget}")
			apply_workflow(mr, "Request Approval")
		mr.reload()
		self.assertEqual(mr.workflow_state, "Pending Approval")
		with as_user(self.other_lead.user), self.assertRaises(frappe.PermissionError):
			apply_workflow(mr, "Approve")
		with as_user(self.lead.user):
			apply_workflow(mr, "Approve")
		mr.reload()
		self.assertEqual((mr.docstatus, mr.solar_approver), (1, self.lead.user))

	def test_raised_and_available(self):
		frappe.get_doc(
			{"doctype": "Funding Entry", "budget": self.budget, "source_type": "Grant", "source_name": "UBC", "amount": 1000, "status": "Received"}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{"doctype": "Funding Entry", "budget": self.budget, "source_type": "Grant", "source_name": "X", "amount": 400, "status": "Pledged"}
		).insert(ignore_permissions=True)
		self.approve_bom()
		s = get_budget_summary(self.budget)
		self.assertEqual(s["minimum_target"], 5000)
		self.assertEqual(s["raised"], 1000)
		self.assertEqual(s["pledged"], 400)
		self.assertAlmostEqual(s["available"], 1000 - s["committed"] - s["spent"], places=2)
		self.assertAlmostEqual(flt(s["lines"][0]["remaining"]), 5000 - s["committed"], places=2)
