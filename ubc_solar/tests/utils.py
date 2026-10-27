"""Helpers shared by the app's tests."""

from contextlib import contextmanager

import frappe

_counter = {"n": 0}


def unique(prefix):
	_counter["n"] += 1
	return f"{prefix}-{frappe.generate_hash(length=6)}-{_counter['n']}"


def make_member(position="Member", subteam=None, division=None, full_name=None, is_erp_admin=0):
	"""Create a team member (as Administrator) and return the doc."""
	email = f"{unique('m').lower()}@example.com"
	doc = frappe.get_doc(
		{
			"doctype": "Team Member",
			"full_name": full_name or email.split("@")[0],
			"email": email,
			"position": position,
			"subteam": subteam,
			"division": division,
			"is_erp_admin": is_erp_admin,
		}
	)
	doc.flags.no_welcome_email = True
	with as_user("Administrator"):
		doc.insert()
	return doc


@contextmanager
def as_user(user):
	previous = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(previous)


def company():
	return frappe.db.get_single_value("Solar Settings", "company")


def warehouse(name):
	abbr = frappe.get_cached_value("Company", company(), "abbr")
	return f"{name} - {abbr}"


def make_location(name, parent="Electrical Storage"):
	full = warehouse(name)
	if not frappe.db.exists("Warehouse", full):
		frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": name,
				"parent_warehouse": warehouse(parent),
				"company": company(),
			}
		).insert(ignore_permissions=True)
	return full


def make_item(make_or_buy="Buy", mpn=None, discipline="Electrical", inventory_type="Component / Material", **kw):
	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": kw.pop("item_code", None),
			"item_name": kw.pop("item_name", None) or (mpn or unique("part")),
			"item_group": kw.pop("item_group", "Electrical Components"),
			"stock_uom": kw.pop("stock_uom", "Nos"),
			"is_stock_item": kw.pop("is_stock_item", 1),
			"solar_make_or_buy": make_or_buy,
			"solar_mpn": mpn,
			"solar_discipline": discipline,
			"solar_inventory_type": inventory_type,
			**kw,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def add_stock(item_code, qty, location, rate=1.0):
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": company(),
			"items": [{"item_code": item_code, "qty": qty, "t_warehouse": location, "basic_rate": rate}],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def stock_qty(item_code, location=None):
	filters = {"item_code": item_code}
	if location:
		filters["warehouse"] = location
	return sum(frappe.get_all("Bin", filters=filters, pluck="actual_qty"))
