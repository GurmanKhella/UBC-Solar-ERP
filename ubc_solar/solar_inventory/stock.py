"""Stock changes come from what people already do: receiving orders, recording
builds, grabbing parts (QR scan), moving parts, and recounting bins. Nobody types
a stock number in; current stock is the running total of these transactions."""

import frappe
from frappe import _
from frappe.utils import flt, nowdate


def company():
	return frappe.db.get_single_value("Solar Settings", "company")


def excluded_locations():
	"""Competition spares aren't picked for builds or grabs in the shop."""
	spares = frappe.db.get_single_value("Solar Settings", "competition_spares_warehouse")
	if not spares:
		return set()
	lft, rgt = frappe.db.get_value("Warehouse", spares, ["lft", "rgt"])
	return set(frappe.get_all("Warehouse", filters={"lft": [">=", lft], "rgt": ["<=", rgt]}, pluck="name"))


def stock_by_location(item_code):
	rows = frappe.get_all(
		"Bin",
		filters={"item_code": item_code, "actual_qty": [">", 0]},
		fields=["warehouse", "actual_qty"],
		order_by="actual_qty desc",
	)
	return [(r.warehouse, flt(r.actual_qty)) for r in rows]


def pick_sources(item_code, qty, preferred=None):
	"""Split `qty` across the locations that have it (most stock first).

	Returns [(warehouse, qty, available_there)]. A row with warehouse None means
	not enough is in stock.
	"""
	excluded = excluded_locations()
	locations = [(w, q) for w, q in stock_by_location(item_code) if w not in excluded]
	if preferred:
		locations.sort(key=lambda wq: wq[0] != preferred)
	remaining = flt(qty)
	picks = []
	for warehouse, available in locations:
		if remaining <= 0:
			break
		take = min(available, remaining)
		picks.append((warehouse, take, available))
		remaining -= take
	if remaining > 1e-9:
		picks.append((None, remaining, 0.0))
	return picks


def make_stock_entry(purpose, rows, source=None, car=None, reference=None, submit=True):
	"""Create (and submit) a Stock Entry. rows: dicts with item_code, qty, s_warehouse / t_warehouse."""
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": purpose,
			"purpose": purpose,
			"company": company(),
			"posting_date": nowdate(),
			"solar_source": source,
			"solar_car": car,
			"solar_reference_doctype": reference.doctype if reference else None,
			"solar_reference_name": reference.name if reference else None,
			"items": [
				{
					"allow_zero_valuation_rate": 1 if purpose == "Material Receipt" and not row.get("basic_rate") else 0,
					**row,
				}
				for row in rows
			],
		}
	)
	se.flags.ignore_permissions = True
	se.insert()
	if submit:
		se.submit()
	return se


def check_member():
	if frappe.session.user == "Guest" or not (
		"Solar Member" in frappe.get_roles() or frappe.session.user == "Administrator"
	):
		frappe.throw(_("Only team members can change stock."), frappe.PermissionError)


@frappe.whitelist()
def take(item_code: str, qty: float, warehouse: str, car: str | None = None):
	"""Someone grabs parts from a bin (Material Issue)."""
	check_member()
	qty = flt(qty)
	if qty <= 0:
		frappe.throw(_("Enter how many you took."))
	se = make_stock_entry(
		"Material Issue", [{"item_code": item_code, "qty": qty, "s_warehouse": warehouse}], source="Grab", car=car
	)
	return se.name


@frappe.whitelist()
def move(item_code: str, qty: float, from_warehouse: str, to_warehouse: str):
	"""Parts move to another shelf (Material Transfer)."""
	check_member()
	qty = flt(qty)
	if qty <= 0 or from_warehouse == to_warehouse:
		frappe.throw(_("Enter a quantity and a different location."))
	se = make_stock_entry(
		"Material Transfer",
		[{"item_code": item_code, "qty": qty, "s_warehouse": from_warehouse, "t_warehouse": to_warehouse}],
		source="Move",
	)
	return se.name


@frappe.whitelist()
def recount(item_code: str, warehouse: str, counted_qty: float):
	"""Someone recounts a bin (Stock Reconciliation): corrects the number and logs the difference."""
	check_member()
	counted_qty = flt(counted_qty)
	if counted_qty < 0:
		frappe.throw(_("A count can't be negative."))
	if not frappe.db.get_value("Item", item_code, "is_stock_item"):
		frappe.throw(_("{0} isn't counted (shop consumables are only reordered).").format(item_code))
	if frappe.db.get_value("Item", item_code, "has_batch_no"):
		frappe.throw(_("{0} is tracked by batch (expiry). Recount it from the Stock Reconciliation form.").format(item_code))
	from erpnext.stock.utils import get_stock_balance

	before = flt(get_stock_balance(item_code, warehouse))
	if abs(before - counted_qty) < 1e-9:
		return {"name": None, "difference": 0}
	valuation = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate")
	valuation = flt(valuation) or flt(frappe.db.get_value("Item", item_code, "valuation_rate"))
	recon = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"company": company(),
			"purpose": "Stock Reconciliation",
			"posting_date": nowdate(),
			"items": [
				{
					"item_code": item_code,
					"warehouse": warehouse,
					"qty": counted_qty,
					"valuation_rate": valuation,
					"allow_zero_valuation_rate": 0 if valuation else 1,
				}
			],
		}
	)
	recon.flags.ignore_permissions = True
	recon.insert()
	recon.submit()
	return {"name": recon.name, "difference": counted_qty - before}
