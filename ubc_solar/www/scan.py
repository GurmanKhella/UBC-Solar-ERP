"""/scan: the page a phone opens from a QR label.

?l=<location>     items in a bin or shelf: take, recount, move, count a new item in
?e=<equipment>    check out, return, confirm condition
?r=<reorder card> request a reorder (two-bin or reorder card)
?i=<item>         where a part is
"""

import frappe
from frappe import _
from frappe.utils import flt

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(frappe.request.full_path)
		raise frappe.Redirect
	if not ("Solar Member" in frappe.get_roles() or "Solar Alumni" in frappe.get_roles() or frappe.session.user == "Administrator"):
		raise frappe.PermissionError(_("Only UBC Solar members can use the scanner."))

	args = frappe.form_dict
	context.no_breadcrumbs = True
	context.can_edit = "Solar Member" in frappe.get_roles() or frappe.session.user == "Administrator"
	context.kind = None
	if args.get("l") and frappe.db.exists("Warehouse", args.l):
		context.kind = "location"
		context.location = location_context(args.l)
		context.title = context.location["title"]
	elif args.get("e") and frappe.db.exists("Equipment", args.e):
		context.kind = "equipment"
		context.equipment = frappe.get_doc("Equipment", args.e).as_dict()
		context.checked_out_name = (
			frappe.utils.get_fullname(context.equipment.checked_out_to) if context.equipment.checked_out_to else None
		)
		context.last_checked = (
			frappe.utils.format_date(context.equipment.last_checked_on) if context.equipment.last_checked_on else None
		)
		context.title = context.equipment.equipment_name
	elif args.get("r") and frappe.db.exists("Reorder Point", args.r):
		from ubc_solar.solar_inventory.doctype.reorder_point.reorder_point import open_request

		point = frappe.get_doc("Reorder Point", args.r)
		context.kind = "reorder"
		context.point = point.as_dict()
		context.open_request = open_request(point.name)
		context.open_state = frappe.db.get_value("Material Request", context.open_request, "workflow_state") if context.open_request else None
		context.title = point.item_name or point.item_code
	elif args.get("i") and frappe.db.exists("Item", args.i):
		from ubc_solar.solar_inventory.stock import stock_by_location

		item = frappe.db.get_value("Item", args.i, ["name", "item_name", "stock_uom"], as_dict=True)
		context.kind = "item"
		context.item = item
		context.stock = [{"warehouse": w, "qty": q} for w, q in stock_by_location(args.i)]
		context.title = item.item_name
	else:
		context.title = _("Scan a label")
	return context


def location_context(warehouse):
	wh = frappe.db.get_value("Warehouse", warehouse, ["name", "warehouse_name", "is_group", "lft", "rgt", "parent_warehouse"], as_dict=True)
	children = frappe.get_all(
		"Warehouse", filters={"parent_warehouse": warehouse}, fields=["name", "warehouse_name"], order_by="warehouse_name asc"
	)
	items = []
	if not wh.is_group:
		items = frappe.db.sql(
			"""select b.item_code, i.item_name, b.actual_qty, i.stock_uom, i.has_batch_no
			from tabBin b join tabItem i on i.name = b.item_code
			where b.warehouse = %s and b.actual_qty != 0 order by i.item_name""",
			warehouse,
			as_dict=True,
		)
		for row in items:
			row.actual_qty = flt(row.actual_qty)
	equipment = frappe.get_all(
		"Equipment", filters={"location": warehouse}, fields=["name", "equipment_name", "condition", "checked_out_to"]
	)
	return {
		"name": wh.name,
		"title": wh.warehouse_name,
		"is_group": wh.is_group,
		"parent": wh.parent_warehouse,
		"children": children,
		"items": items,
		"equipment": equipment,
	}
