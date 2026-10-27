"""Install and migrate hooks: company setup, roles, permissions, workflows and the
team's starting data. Everything here is safe to run more than once."""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from ubc_solar.setup import custom_fields, permissions, workflows

COMPANY = "UBC Solar"
ABBR = "UBCS"

ROLES = [
	"Solar Captain",
	"Solar Exec",
	"Solar Lead",
	"Solar Senior Designer",
	"Solar Member",
	"Solar Alumni",
	"Solar Admin",
]

DIVISIONS = {
	"Electrical": ["Power & Signals", "Battery Management", "Embedded", "Strategy"],
	"Mechanical": ["Aeroshell", "Structures", "Dynamics", "Battery Mech"],
	"Business": ["Business"],
}

# (subsystem, subteams, is_vehicle_harnesses, lead note)
SUBSYSTEMS = [
	("Aeroshell", ["Aeroshell"], 0, ""),
	("Chassis", ["Structures"], 0, ""),
	("Vehicle dynamics", ["Dynamics"], 0, ""),
	(
		"Battery",
		["Battery Mech", "Battery Management"],
		0,
		"Electrical and Mechanical Execs together, with the Battery Mech Lead and Battery Management Lead",
	),
	("Power and Signals", ["Power & Signals"], 0, ""),
	("Vehicle harnesses", ["Power & Signals"], 1, "Power & Signals (to confirm)"),
]

HARNESS_CATEGORIES = ["HV", "LV", "CAN"]

HARNESS_CHECKS = ["Continuity", "Pinout", "Crimp pull test", "Labeling"]

ITEM_GROUPS = [
	"Electrical Components",
	"Mechanical Parts",
	"Fasteners",
	"Raw Materials",
	"Composites",
	"PCBs",
	"Harnesses",
	"Assemblies",
	"Subsystems",
	"Vehicles",
	"Shop Consumables",
	"Services",
]

SUPPLIERS = ["Digi-Key", "Mouser", "McMaster-Carr", "LCSC", "JLCPCB", "Amazon", "Other"]


def after_install():
	run_setup_wizard()
	configure_company()
	sync()
	create_starting_data()
	frappe.db.commit()


def after_migrate():
	sync()


def sync():
	"""Things that must match the code after every migrate."""
	create_roles()
	custom_fields.apply()
	permissions.apply()
	workflows.apply()
	configure_settings()


# ------------------------------------------------------------------ setup wizard
def run_setup_wizard():
	if frappe.is_setup_complete():
		return
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	year = getdate(nowdate()).year
	result = setup_complete(
		{
			"language": "English",
			"country": "Canada",
			"timezone": "America/Vancouver",
			"currency": "CAD",
			"company_name": COMPANY,
			"company_abbr": ABBR,
			"chart_of_accounts": "Standard",
			"fy_start_date": f"{year}-01-01",
			"fy_end_date": f"{year}-12-31",
			"domain": "Manufacturing",
		}
	)
	if not result or result.get("status") != "ok":
		frappe.throw(_("ERPNext setup wizard failed: {0}").format(result))


def get_company():
	return frappe.db.get_single_value("Solar Settings", "company") or frappe.db.get_value(
		"Company", {"company_name": COMPANY}
	) or frappe.defaults.get_global_default("company")


def configure_company():
	company = get_company()
	if not company:
		return
	# Stock keeps quantities and values, but no accounting entries are posted:
	# the team's money is tracked in the fundraising budget (Money section).
	frappe.db.set_value("Company", company, "enable_perpetual_inventory", 0)


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def configure_settings():
	stock = frappe.get_single("Stock Settings")
	stock.item_naming_by = "Item Code"
	stock.allow_negative_stock = 0
	stock.auto_indent = 0
	# Batches carry expiry dates for perishables; outgoing batches are picked
	# automatically, first-expiring first.
	stock.enable_serial_and_batch_no_for_item = 1
	stock.use_serial_batch_fields = 1
	stock.auto_create_serial_and_batch_bundle_for_outward = 1
	stock.pick_serial_and_batch_based_on = "Expiry"
	stock.flags.ignore_permissions = True
	stock.save()

	buying = frappe.get_single("Buying Settings")
	buying.po_required = "No"
	buying.pr_required = "No"
	buying.flags.ignore_permissions = True
	buying.save()


# ------------------------------------------------------------------ starting data
def create_starting_data():
	company = get_company()
	settings = frappe.get_single("Solar Settings")
	settings.company = company

	warehouses = create_warehouses(company)
	settings.receiving_warehouse = warehouses["Receiving"]
	settings.build_area_warehouse = warehouses["Build Area"]
	settings.competition_spares_warehouse = warehouses["Competition Spares"]

	create_item_groups()
	create_suppliers()
	create_team_structure()
	create_subsystems()
	create_harness_categories()
	settings.flags.ignore_permissions = True
	settings.save()

	frappe.db.set_single_value("Stock Settings", "default_warehouse", warehouses["Receiving"])
	frappe.db.set_single_value("Manufacturing Settings", "default_fg_warehouse", warehouses["Build Area"])
	frappe.db.set_single_value("Manufacturing Settings", "default_wip_warehouse", warehouses["Build Area"])

	create_cars()


def create_warehouses(company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	root = frappe.db.get_value("Warehouse", {"is_group": 1, "company": company, "parent_warehouse": ["in", ["", None]]})

	def make(name, parent, is_group=0):
		full = f"{name} - {abbr}"
		if not frappe.db.exists("Warehouse", full):
			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": name,
					"parent_warehouse": parent,
					"is_group": is_group,
					"company": company,
				}
			).insert(ignore_permissions=True)
		return full

	workshop = make("Workshop", root, 1)
	result = {
		"Workshop": workshop,
		"Electrical Storage": make("Electrical Storage", workshop, 1),
		"Mechanical Storage": make("Mechanical Storage", workshop, 1),
		"Receiving": make("Receiving", workshop),
		"Build Area": make("Build Area", workshop),
		"Fridge and Freezer": make("Fridge and Freezer", workshop),
		"Competition Spares": make("Competition Spares", root),
	}
	return result


def create_item_groups():
	parent = "All Item Groups"
	for group in ITEM_GROUPS:
		if not frappe.db.exists("Item Group", group):
			frappe.get_doc(
				{"doctype": "Item Group", "item_group_name": group, "parent_item_group": parent, "is_group": 0}
			).insert(ignore_permissions=True)


def create_suppliers():
	group = frappe.db.get_single_value("Buying Settings", "supplier_group") or frappe.db.get_value(
		"Supplier Group", {"is_group": 0}
	)
	for name in SUPPLIERS:
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": group}).insert(
				ignore_permissions=True
			)


def create_team_structure():
	for division, subteams in DIVISIONS.items():
		if not frappe.db.exists("Division", division):
			frappe.get_doc({"doctype": "Division", "division_name": division}).insert(ignore_permissions=True)
		for subteam in subteams:
			if not frappe.db.exists("Subteam", subteam):
				frappe.get_doc({"doctype": "Subteam", "subteam_name": subteam, "division": division}).insert(
					ignore_permissions=True
				)


def create_subsystems():
	for order, (name, subteams, is_harness, note) in enumerate(SUBSYSTEMS, start=1):
		if frappe.db.exists("Subsystem", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Subsystem",
				"subsystem_name": name,
				"is_vehicle_harnesses": is_harness,
				"sort_order": order,
				"lead_note": note,
				"subteams": [{"subteam": s} for s in subteams],
			}
		).insert(ignore_permissions=True)


def create_harness_categories():
	lv = make_quality_template("Harness checks (LV)", HARNESS_CHECKS)
	hv = make_quality_template("Harness checks (HV)", [*HARNESS_CHECKS, "Insulation resistance"])
	for name in HARNESS_CATEGORIES:
		if not frappe.db.exists("Harness Category", name):
			frappe.get_doc(
				{
					"doctype": "Harness Category",
					"category_name": name,
					"quality_inspection_template": hv if name == "HV" else lv,
				}
			).insert(ignore_permissions=True)


def make_quality_template(name, checks):
	if frappe.db.exists("Quality Inspection Template", name):
		return name
	for check in checks:
		if not frappe.db.exists("Quality Inspection Parameter", check):
			frappe.get_doc({"doctype": "Quality Inspection Parameter", "parameter": check}).insert(
				ignore_permissions=True
			)
	frappe.get_doc(
		{
			"doctype": "Quality Inspection Template",
			"quality_inspection_template_name": name,
			"item_quality_inspection_parameter": [
				{"specification": check, "numeric": 0, "value": "Pass"} for check in checks
			],
		}
	).insert(ignore_permissions=True)
	return name


def create_cars():
	"""The cars named in the plan. Statuses can be changed in the ERP."""
	for version, name, status in (("V4", "Cascadia", "Active"), ("V5", "", "In Design")):
		if not frappe.db.exists("Car", version):
			frappe.get_doc(
				{"doctype": "Car", "car_version": version, "car_name": name, "status": status}
			).insert(ignore_permissions=True)


def before_tests():
	"""Used by `bench run-tests`: make sure the site is fully set up."""
	frappe.clear_cache()
	if not frappe.is_setup_complete():
		after_install()
	frappe.db.commit()
