import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from ubc_solar.solar_inventory import stock
from ubc_solar.solar_inventory.doctype.equipment.equipment import check_out, confirm_check, return_equipment
from ubc_solar.solar_inventory.doctype.reorder_point.reorder_point import request_reorder
from ubc_solar.solar_inventory.tasks import expiring_batches
from ubc_solar.tests.test_cars_money import make_budget, make_car, make_project
from ubc_solar.tests.utils import add_stock, as_user, make_item, make_location, make_member, stock_qty, unique


class TestStockMoves(IntegrationTestCase):
	def setUp(self):
		self.member = make_member("Member", subteam="Power & Signals")
		self.bin = make_location(unique("E-B"))
		self.bin2 = make_location(unique("E-C"))
		self.part = make_item("Buy", mpn=unique("XT60"))
		add_stock(self.part.name, 10, self.bin)

	def test_take_move_recount(self):
		with as_user(self.member.user):
			stock.take(self.part.name, 3, self.bin)
			stock.move(self.part.name, 2, self.bin, self.bin2)
			result = stock.recount(self.part.name, self.bin, 4)
		self.assertEqual(stock_qty(self.part.name, self.bin), 4)
		self.assertEqual(stock_qty(self.part.name, self.bin2), 2)
		self.assertEqual(result["difference"], -1)

	def test_alumni_cannot_change_stock(self):
		alum = make_member("Member", subteam="Power & Signals")
		alum.position = "Alumni"
		alum.save()
		with as_user(alum.user), self.assertRaises(frappe.PermissionError):
			stock.take(self.part.name, 1, self.bin)

	def test_pick_sources_splits_and_flags_shortage(self):
		add_stock(self.part.name, 5, self.bin2)
		picks = stock.pick_sources(self.part.name, 18)
		self.assertEqual([p[0] for p in picks], [self.bin, self.bin2, None])
		self.assertEqual([p[1] for p in picks], [10, 5, 3])


class TestEquipment(IntegrationTestCase):
	def test_checkout_cycle(self):
		member = make_member("Member", subteam="Aeroshell")
		scope_bin = make_location(unique("M-T"), parent="Mechanical Storage")
		eq = frappe.get_doc(
			{"doctype": "Equipment", "equipment_name": "Vacuum pump", "category": "Shop and facility", "location": scope_bin}
		).insert(ignore_permissions=True)
		with as_user(member.user):
			check_out(eq.name, purpose="Layup")
			with self.assertRaises(frappe.ValidationError):
				check_out(eq.name)
		eq.reload()
		self.assertEqual(eq.checked_out_to, member.user)
		with as_user(member.user):
			return_equipment(eq.name)
			confirm_check(eq.name, "Needs Repair")
		eq.reload()
		self.assertFalse(eq.checked_out_to)
		self.assertEqual(eq.condition, "Needs Repair")
		self.assertEqual(eq.last_checked_by, member.user)
		log = frappe.get_all("Equipment Checkout", filters={"equipment": eq.name}, fields=["returned_on"])
		self.assertEqual(len(log), 1)
		self.assertTrue(log[0].returned_on)

	def test_offboarding_needs_equipment_back(self):
		from ubc_solar.team.doctype.team_member.team_member import offboard

		member = make_member("Member", subteam="Aeroshell")
		eq = frappe.get_doc({"doctype": "Equipment", "equipment_name": "Oscilloscope", "category": "Test and measurement"}).insert(
			ignore_permissions=True
		)
		with as_user(member.user):
			check_out(eq.name)
		with as_user("Administrator"):
			with self.assertRaises(frappe.ValidationError):
				offboard(member.name)
			with as_user(member.user):
				return_equipment(eq.name)
			car = make_car()
			project = make_project(car.name, subteam="Aeroshell", subsystem="Aeroshell", owner=member.user)
			with self.assertRaises(frappe.ValidationError):
				offboard(member.name)  # owns a project: needs a new owner
			summary = offboard(member.name, new_owner="Administrator")
		self.assertEqual(summary["projects"], [project.name])
		self.assertEqual(frappe.db.get_value("Solar Project", project.name, "project_owner"), "Administrator")
		self.assertEqual(frappe.db.get_value("Team Member", member.name, "position"), "Alumni")


class TestReorderAndExpiry(IntegrationTestCase):
	def test_two_bin_scan_creates_one_request(self):
		budget = make_budget([("Shop Supplies", None, 500)])
		frappe.db.set_value("Budget Line", f"Shop Supplies - {budget}", "is_shop_supplies", 1)
		member = make_member("Member", subteam="Structures")
		gloves = make_item("Buy", mpn=unique("GLOVES"), inventory_type="Shop Consumable")
		point = frappe.get_doc(
			{
				"doctype": "Reorder Point",
				"item_code": gloves.name,
				"method": "Two-bin",
				"reorder_qty": 2,
				"budget_line": f"Shop Supplies - {budget}",
				"subteam": "Structures",
				"estimated_rate": 12,
			}
		).insert(ignore_permissions=True)
		with as_user(member.user):
			first = request_reorder(point.name)
			second = request_reorder(point.name)
		self.assertTrue(first["created"])
		self.assertFalse(second["created"])
		self.assertEqual(first["name"], second["name"])
		mr = frappe.get_doc("Material Request", first["name"])
		self.assertEqual((mr.workflow_state, mr.solar_source, mr.solar_requested_by), ("Pending Approval", "Two-bin", member.user))

	def test_expiring_batch_is_found(self):
		from ubc_solar.money.purchasing import make_batch

		prepreg = make_item("Buy", mpn=unique("PREPREG"), inventory_type="Perishable")
		fridge = make_location(unique("Fridge"), parent="Workshop")
		batch = make_batch(prepreg.name, add_days(nowdate(), 5))
		se = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": frappe.db.get_single_value("Solar Settings", "company"),
				"items": [{"item_code": prepreg.name, "qty": 3, "t_warehouse": fridge, "basic_rate": 50, "use_serial_batch_fields": 1, "batch_no": batch}],
			}
		).insert(ignore_permissions=True)
		se.submit()
		found = {r.name: r.qty for r in expiring_batches(days=30)}
		self.assertEqual(found.get(batch), 3)


class TestRepair(IntegrationTestCase):
	def test_fixed_repair_deducts_parts(self):
		car = make_car("Active")
		project = make_project(car.name)
		shelf = make_location(unique("E-R"))
		fuse = make_item("Buy", mpn=unique("FUSE"))
		add_stock(fuse.name, 5, shelf)
		repair = frappe.get_doc(
			{
				"doctype": "Car Repair",
				"title": "Blown fuse on BMS",
				"car": car.name,
				"solar_project": project.name,
				"parts": [{"item_code": fuse.name, "qty": 2}],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(repair.solar_subsystem, "Battery")
		self.assertEqual(repair.parts[0].source_warehouse, shelf)
		self.assertEqual(stock_qty(fuse.name), 5)
		repair.status = "Fixed"
		repair.save(ignore_permissions=True)
		self.assertEqual(stock_qty(fuse.name), 3)
		repair.save(ignore_permissions=True)  # saving again doesn't deduct twice
		self.assertEqual(stock_qty(fuse.name), 3)
