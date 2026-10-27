"""Merch store (v0.2): its stock location, item group and stock-entry reason."""

import frappe

from ubc_solar.setup.install import create_item_groups, create_warehouses, get_company, set_up_merch


def execute():
	frappe.reload_doc("merch", "doctype", "merch_settings")
	create_item_groups()
	set_up_merch(create_warehouses(get_company())["Merch Stock"])

	field = frappe.db.get_value("Custom Field", {"dt": "Stock Entry", "fieldname": "solar_source"}, ["name", "options"], as_dict=True)
	if field and "Merch" not in (field.options or "").split("\n"):
		options = (field.options or "").split("\n")
		options.insert(options.index("Other") if "Other" in options else len(options), "Merch")
		frappe.db.set_value("Custom Field", field.name, "options", "\n".join(options))
		frappe.clear_cache(doctype="Stock Entry")
