"""The merch store: products, pricing, and orders from the public page or in person.

Prices: team members logged in pay the team price (when one is set); everyone
else pays the public price. "Team only" products are sold to logged-in team
members and alumni only. Merch stock lives in the merch location; restocking
is an ordinary purchase request received into that location.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, flt

from ubc_solar.team import scope


def settings():
	return frappe.get_cached_doc("Merch Settings")


def merch_location():
	location = settings().merch_location
	if not location:
		frappe.throw(_("Set the merch stock location in Merch Settings."))
	return location


def team_member_for_session():
	"""The logged-in user's Team Member record (active or alumni), if any."""
	if frappe.session.user in ("Guest", None):
		return None
	return frappe.db.get_value("Team Member", {"user": frappe.session.user}, "name")


def price_for(product, is_team):
	if is_team and flt(product.team_price) > 0:
		return flt(product.team_price)
	return flt(product.public_price)


def variant_stock(item_code):
	location = settings().merch_location
	if not item_code:
		return 0.0
	filters = {"item_code": item_code}
	if location:
		filters["warehouse"] = location
	return sum(flt(q) for q in frappe.get_all("Bin", filters=filters, pluck="actual_qty"))


def reserved_qty(item_code, exclude_order=None):
	"""Ordered but not yet handed over (orders not fulfilled or cancelled)."""
	conditions = ""
	params = [item_code]
	if exclude_order:
		conditions = "and o.name != %s"
		params.append(exclude_order)
	return flt(
		frappe.db.sql(
			f"""select sum(i.qty) from `tabMerch Order Item` i join `tabMerch Order` o on o.name = i.parent
			where i.item_code = %s and o.status in ('Placed', 'Paid', 'Ready for Pickup') {conditions}""",
			params,
		)[0][0]
	)


def available_qty(item_code, exclude_order=None):
	return variant_stock(item_code) - reserved_qty(item_code, exclude_order)


def catalog(is_team):
	"""Products on sale that this viewer can buy, with prices and what's available."""
	filters = {"status": "On Sale"}
	if not is_team:
		filters["sold_to"] = "Everyone"
	products = frappe.get_all(
		"Merch Product",
		filters=filters,
		fields=["name", "product_name", "public_price", "team_price", "image", "description", "allow_preorder", "max_per_order", "sold_to"],
		order_by="sort_order asc, product_name asc",
	)
	for p in products:
		p.price = price_for(p, is_team)
		p.options = []
		for v in frappe.get_all(
			"Merch Product Variant",
			filters={"parent": p.name, "parenttype": "Merch Product", "enabled": 1},
			fields=["option_label", "item_code"],
			order_by="idx asc",
		):
			available = max(0.0, available_qty(v.item_code))
			if available > 0 or p.allow_preorder:
				p.options.append({"label": v.option_label, "available": available})
	return [p for p in products if p.options]


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def place_order(buyer_name: str, email: str, items: str | list, phone: str | None = None, notes: str | None = None):
	"""Order from the public store page. items: [{"product", "option", "qty"}]"""
	if not settings().store_open:
		frappe.throw(_("The merch store is closed right now."))
	items = frappe.parse_json(items) if isinstance(items, str) else items
	order = frappe.get_doc(
		{
			"doctype": "Merch Order",
			"buyer_name": (buyer_name or "").strip(),
			"email": (email or "").strip(),
			"phone": (phone or "").strip(),
			"notes": (notes or "").strip(),
			"source": "Online store",
			"items": [
				{"product": row.get("product"), "option_label": row.get("option"), "qty": cint(row.get("qty"))}
				for row in items or []
			],
		}
	)
	order.flags.from_store = True
	order.insert(ignore_permissions=True)
	return {
		"name": order.name,
		"total": order.total,
		"payment_instructions": settings().payment_instructions or "",
		"pickup_info": settings().pickup_info or "",
	}


def merch_managers():
	return [
		u
		for u in frappe.get_all("Has Role", filters={"role": "Solar Merch Manager", "parenttype": "User"}, pluck="parent")
		if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled")
	]


def is_team_member_session():
	member = team_member_for_session()
	return bool(member) or scope.is_admin()
