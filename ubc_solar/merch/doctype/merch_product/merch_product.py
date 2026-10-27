# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt

from ubc_solar.merch import store


class MerchProduct(Document):
	def validate(self):
		self.product_name = (self.product_name or "").strip()
		if flt(self.public_price) < 0 or flt(self.team_price) < 0:
			frappe.throw(_("Prices can't be negative."))
		if not self.variants:
			self.append("variants", {"option_label": "One size", "enabled": 1})
		labels = [v.option_label.strip() for v in self.variants]
		if len(labels) != len(set(labels)):
			frappe.throw(_("Each option needs a different name."))
		for v in self.variants:
			v.option_label = v.option_label.strip()
			if not v.item_code:
				v.item_code = make_stock_item(self.product_name, v.option_label)
			else:
				frappe.db.set_value("Item", v.item_code, "item_name", f"{self.product_name} ({v.option_label})"[:140])

	def onload(self):
		for v in self.variants:
			v.in_stock = store.variant_stock(v.item_code)


def make_stock_item(product_name, option_label):
	group = store.settings().group_merch
	if not group or not frappe.db.exists("Item Group", group):
		frappe.throw(_("Pick the merch item group in Merch Settings."))
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": make_autoname("MERCH-.####"),
			"item_name": f"{product_name} ({option_label})"[:140],
			"item_group": group,
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"is_sales_item": 1,
			"is_purchase_item": 1,
			"include_item_in_manufacturing": 0,
			"solar_make_or_buy": "Buy",
			"solar_inventory_type": "Component / Material",
		}
	)
	location = store.settings().merch_location
	company = frappe.db.get_single_value("Solar Settings", "company")
	if location:
		item.append("item_defaults", {"company": company, "default_warehouse": location})
	item.insert(ignore_permissions=True)
	return item.name


@frappe.whitelist()
def make_restock_request(product: str):
	"""A draft purchase request for every option, received into the merch location.
	Change the quantities (delete options not needed), pick the budget line and supplier, then submit as usual."""
	doc = frappe.get_doc("Merch Product", product)
	doc.check_permission("read")
	location = store.merch_location()
	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	for v in doc.variants:
		if v.enabled and v.item_code:
			item = frappe.db.get_value("Item", v.item_code, ["item_name", "stock_uom"], as_dict=True)
			mr.append(
				"items",
				{
					"item_code": v.item_code,
					"item_name": item.item_name,
					"uom": item.stock_uom,
					"stock_uom": item.stock_uom,
					"conversion_factor": 1,
					"qty": 1,
					"warehouse": location,
				},
			)
	return mr.as_dict()
