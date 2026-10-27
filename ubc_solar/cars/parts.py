"""Part numbers.

Anything the ERP tracks as a thing gets a part number:
- bought parts keep their manufacturer part number;
- parts the team makes get a team number: prefix, sequence and revision letter,
  e.g. M-0042-A (the suggested "simple" style; prefixes are set in Solar Settings).
"""

import re
import string

import frappe
from frappe import _
from frappe.model.naming import make_autoname

TEAM_NUMBER = re.compile(r"^(?P<base>[A-Z]+-\d+)-(?P<rev>[A-Z]{1,2})$")


def settings():
	return frappe.get_cached_doc("Solar Settings")


def prefix_for(discipline):
	s = settings()
	prefix = {
		"Mechanical": s.mechanical_prefix,
		"Electrical": s.electrical_prefix,
		"Assembly": s.assembly_prefix,
	}.get(discipline)
	if not prefix:
		frappe.throw(_("Pick a discipline (Mechanical, Electrical or Assembly) to generate a part number."))
	return prefix.strip().upper()


def next_base_number(prefix):
	digits = settings().number_digits or 4
	return make_autoname(f"{prefix}-.{'#' * digits}")


def next_team_number(discipline):
	"""Returns (item_code, base, revision), e.g. ("M-0042-A", "M-0042", "A")."""
	base = next_base_number(prefix_for(discipline))
	revision = (settings().first_revision or "A").strip().upper()
	return f"{base}-{revision}", base, revision


def next_bought_number():
	return next_base_number((settings().bought_prefix or "B").strip().upper())


def next_revision(revision):
	if revision == "Z":
		frappe.throw(_("This part has used every revision letter (A-Z). Give the new design a new part number."))
	return string.ascii_uppercase[string.ascii_uppercase.index(revision) + 1]


# ------------------------------------------------------------------ Item hooks
def item_before_insert(doc, method=None):
	if doc.item_code:
		doc.item_code = doc.item_code.strip()
		match = TEAM_NUMBER.match(doc.item_code)
		if match and doc.solar_make_or_buy == "Make" and not doc.solar_base_part_number:
			doc.solar_base_part_number, doc.solar_revision = match.group("base"), match.group("rev")
	elif doc.solar_make_or_buy == "Make":
		doc.item_code, doc.solar_base_part_number, doc.solar_revision = next_team_number(
			doc.solar_discipline
		)
	elif doc.solar_make_or_buy == "Buy":
		doc.item_code = (doc.solar_mpn or "").strip() or next_bought_number()
	else:
		frappe.throw(_("Enter an item code, or set Make or Buy so one is generated."))
	if not doc.item_name:
		doc.item_name = doc.item_code


def item_validate(doc, method=None):
	if doc.solar_mpn:
		doc.solar_mpn = doc.solar_mpn.strip()
	if doc.solar_make_or_buy == "Make":
		doc.default_material_request_type = "Manufacture"
	elif doc.solar_make_or_buy == "Buy":
		doc.default_material_request_type = "Purchase"
		doc.is_purchase_item = 1

	if doc.solar_inventory_type == "Shop Consumable":
		if doc.is_new():
			doc.is_stock_item = 0
		elif doc.is_stock_item:
			frappe.msgprint(
				_("Shop consumables are never counted. Untick Maintain Stock if this part has no stock history."),
				indicator="orange",
				alert=True,
			)
	if doc.solar_inventory_type == "Perishable" and not doc.has_batch_no:
		if doc.is_new() or not frappe.db.exists("Stock Ledger Entry", {"item_code": doc.name, "is_cancelled": 0}):
			doc.has_batch_no = 1
			doc.has_expiry_date = 1
			doc.create_new_batch = 1
		else:
			frappe.msgprint(
				_("This part already has stock history, so expiry tracking couldn't be switched on automatically."),
				indicator="orange",
			)


@frappe.whitelist()
def new_revision(item_code: str):
	"""Copy a team part to its next revision (M-0042-A -> M-0042-B)."""
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	if not frappe.has_permission("Item", "create"):
		frappe.throw(_("You can't create parts."), frappe.PermissionError)
	if not (item.solar_base_part_number and item.solar_revision):
		frappe.throw(_("Only team part numbers (like M-0042-A) have revisions."))
	revision = next_revision(item.solar_revision)
	new_code = f"{item.solar_base_part_number}-{revision}"
	while frappe.db.exists("Item", new_code):
		revision = next_revision(revision)
		new_code = f"{item.solar_base_part_number}-{revision}"
	copy = frappe.copy_doc(item)
	copy.item_code = new_code
	copy.solar_revision = revision
	copy.barcodes = []
	copy.default_bom = None
	copy.insert()
	return copy.name
