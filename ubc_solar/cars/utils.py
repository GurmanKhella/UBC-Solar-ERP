"""Shared helpers for the Cars section."""

import frappe
from frappe import _


def assert_car_editable(car, doc=None):
	"""Retired cars, and everything recorded against them, are view-only."""
	if not car:
		return
	if doc is not None and doc.flags.ignore_car_lock:
		return
	if frappe.session.user == "Administrator":
		return
	if frappe.get_cached_value("Car", car, "status") == "Retired":
		frappe.throw(_("{0} is retired, so its records are view-only.").format(car), frappe.ValidationError)


def vehicle_harness_subsystem():
	name = frappe.db.get_value("Subsystem", {"is_vehicle_harnesses": 1, "enabled": 1})
	if not name:
		frappe.throw(_("No subsystem is marked as the Vehicle harnesses section (Subsystem list)."))
	return name


def subsystem_subteams(subsystem):
	if not subsystem:
		return []
	return frappe.get_all(
		"Subsystem Subteam", filters={"parent": subsystem, "parenttype": "Subsystem"}, pluck="subteam"
	)


def car_subteams():
	"""Subteams that build parts of the car (listed on some subsystem)."""
	return set(frappe.get_all("Subsystem Subteam", filters={"parenttype": "Subsystem"}, pluck="subteam"))


def make_team_item(item_name, discipline, item_group, project=None, description=None):
	"""Create a part the team makes, with the next team part number."""
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_name": item_name[:140],
			"description": description or item_name,
			"item_group": item_group,
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"include_item_in_manufacturing": 1,
			"solar_make_or_buy": "Make",
			"solar_discipline": discipline,
			"solar_inventory_type": "Component / Material",
			"solar_project": project,
		}
	)
	item.insert(ignore_permissions=True)
	return item.name


def default_location(item_code):
	"""An item's own shelf, if it has one."""
	company = frappe.db.get_single_value("Solar Settings", "company")
	return frappe.db.get_value(
		"Item Default", {"parent": item_code, "company": company}, "default_warehouse"
	)
