import frappe
from frappe.tests import IntegrationTestCase

from ubc_solar.cars.test_bom_parsers import ALTIUM_CSV, SOLIDWORKS_CSV
from ubc_solar.tests.test_cars_money import make_car, make_project
from ubc_solar.tests.utils import unique


def upload(name, content):
	return frappe.get_doc(
		{"doctype": "File", "file_name": name, "content": content.encode(), "is_private": 1}
	).insert(ignore_permissions=True)


def run(project, source, file_doc):
	imp = frappe.get_doc(
		{"doctype": "BOM Import", "solar_project": project, "source": source, "bom_file": file_doc.file_url, "design_revision": "rev B"}
	).insert(ignore_permissions=True)
	result = imp.run_import()
	imp.reload()
	return imp, result


class TestBomImport(IntegrationTestCase):
	def test_altium_import(self):
		car = make_car()
		project = make_project(car.name)
		tag = unique("A").upper()
		csv = ALTIUM_CSV.replace("RC0603FR-0710KL", f"RC0603FR-{tag}").replace("CL10B104KB8NNNC", f"CL10-{tag}").replace(
			"LTC6811HG-1#3ZZPBF", f"LTC6811-{tag}"
		)
		imp, result = run(project.name, "Altium", upload("bms.csv", csv))
		self.assertEqual(imp.status, "Imported")
		bom = frappe.get_doc("BOM", imp.bom)
		self.assertEqual(bom.docstatus, 0)
		self.assertEqual(bom.item, frappe.db.get_value("Solar Project", project.name, "part"))
		self.assertEqual(bom.solar_design_revision, "rev B")
		self.assertEqual(bom.solar_project, project.name)
		qty = {r.item_code: r.qty for r in bom.items}
		self.assertEqual(qty[f"RC0603FR-{tag}"], 4)
		self.assertEqual(frappe.db.get_value("Item", f"RC0603FR-{tag}", "solar_inventory_type"), "Small Part")
		self.assertEqual(frappe.db.get_value("Item", f"LTC6811-{tag}", "solar_inventory_type"), "Component / Material")
		self.assertEqual(frappe.db.get_value("Item", f"LTC6811-{tag}", "solar_manufacturer"), "Analog Devices")
		self.assertTrue(frappe.db.exists("Item Supplier", {"parent": f"RC0603FR-{tag}", "supplier": "Digi-Key"}))
		self.assertEqual(len(bom.items), 4)  # includes the test points with no MPN
		self.assertTrue(any("no manufacturer part number" in w for w in result["warnings"]))

		# Importing again reuses the parts and makes a new draft version.
		imp2, _ = run(project.name, "Altium", upload("bms2.csv", csv))
		self.assertNotEqual(imp2.bom, imp.bom)
		self.assertEqual(frappe.db.count("Item", {"solar_mpn": f"RC0603FR-{tag}"}), 1)

	def test_solidworks_import_with_subassembly(self):
		car = make_car()
		project = make_project(car.name, subteam="Dynamics", subsystem="Vehicle dynamics")
		tag = unique("S").upper()
		csv = SOLIDWORKS_CSV.replace("M-0042-A", f"M-{tag}1-A").replace("M-0050-A", f"M-{tag}2-A").replace(
			"M-0051-A", f"M-{tag}3-A"
		).replace("6383K221", f"6383K-{tag}")
		imp, result = run(project.name, "SolidWorks", upload("upright.csv", csv))
		bom = frappe.get_doc("BOM", imp.bom)
		codes = [r.item_code for r in bom.items]
		self.assertIn(f"M-{tag}1-A", codes)
		self.assertIn(f"M-{tag}2-A", codes)
		self.assertEqual(frappe.db.get_value("Item", f"M-{tag}1-A", "solar_material"), "6061-T6 aluminum")
		self.assertEqual(frappe.db.get_value("Item", f"6383K-{tag}", "solar_make_or_buy"), "Buy")
		sub = frappe.get_all("BOM", filters={"item": f"M-{tag}2-A", "docstatus": 0}, pluck="name")
		self.assertEqual(len(sub), 1)
		self.assertIn(sub[0], result["summary"])
		spacer = [c for c in codes if c.startswith("M-") and c not in (f"M-{tag}1-A", f"M-{tag}2-A")]
		self.assertEqual(len(spacer), 1)  # unnumbered made part got a generated team number

	def test_bad_file(self):
		car = make_car()
		project = make_project(car.name)
		with self.assertRaises(frappe.ValidationError):
			run(project.name, "Altium", upload("bad.csv", "nothing,useful\n1,2\n"))
