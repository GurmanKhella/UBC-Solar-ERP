"""Purchasing: Draft -> Pending Approval -> Approved -> Ordered -> Received.

Every purchase is approved once, within the approver's scope. Whoever approved it
owns it: they order it (attaching the receipt) and mark it received, which puts
the parts into stock and pings the requester.

ERPNext pieces: Material Request (the purchase request), Purchase Order (made when
it's ordered) and Purchase Receipt (made when it's received).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from ubc_solar.cars.utils import assert_car_editable, default_location
from ubc_solar.solar_automation import notify
from ubc_solar.team import scope


def settings():
	return frappe.get_cached_doc("Solar Settings")


# ------------------------------------------------------------------ hooks
def before_validate(doc, method=None):
	"""Fill in defaults before ERPNext's own checks run."""
	if doc.material_request_type != "Purchase":
		return
	if doc.solar_project:
		project = frappe.db.get_value("Solar Project", doc.solar_project, ["car", "subteam"], as_dict=True)
		doc.solar_car = doc.solar_car or project.car
		doc.solar_subteam = doc.solar_subteam or project.subteam
	if doc.solar_repair and not doc.solar_car:
		doc.solar_car = frappe.db.get_value("Car Repair", doc.solar_repair, "car")
	if not doc.solar_requested_by:
		doc.solar_requested_by = doc.owner or frappe.session.user
	if not doc.solar_budget_line:
		doc.solar_budget_line = default_budget_line(doc.solar_subteam, doc.solar_source)
	if not doc.solar_subteam and doc.solar_budget_line:
		doc.solar_subteam = frappe.db.get_value("Budget Line", doc.solar_budget_line, "subteam")

	schedule = doc.schedule_date or add_days(nowdate(), cint(settings().default_lead_days) or 7)
	doc.schedule_date = schedule
	receiving = settings().receiving_warehouse
	for row in doc.items:
		row.schedule_date = row.schedule_date or schedule
		if getdate(row.schedule_date) < getdate(doc.transaction_date):
			row.schedule_date = doc.transaction_date
		row.warehouse = row.warehouse or default_location(row.item_code) or receiving
	doc.solar_estimated_total = sum(flt(r.qty) * flt(r.rate) for r in doc.items)
	if doc.solar_paid_by == "Member (reimbursement)" and not doc.solar_reimburse_to:
		doc.solar_reimburse_to = doc.solar_requested_by


def validate(doc, method=None):
	if doc.material_request_type != "Purchase":
		return
	assert_car_editable(doc.solar_car, doc)


def before_submit(doc, method=None):
	if doc.material_request_type != "Purchase":
		return
	if not scope.can_approve([doc.solar_subteam] if doc.solar_subteam else []):
		who = doc.solar_subteam or _("team-wide purchases")
		frappe.throw(
			_("Only the {0} Lead, their division's Exec, or the Captain can approve this purchase.").format(who)
			if doc.solar_subteam
			else _("Only an Exec or the Captain can approve {0}.").format(who),
			frappe.PermissionError,
		)
	if not doc.solar_budget_line:
		frappe.throw(_("Pick the budget line this purchase comes out of."))
	check_must_have(doc)
	doc.solar_approver = frappe.session.user
	doc.solar_approved_on = now_datetime()
	warn_unrecounted(doc)


def on_submit(doc, method=None):
	if doc.material_request_type != "Purchase":
		return
	notify.send(
		"Purchase to order",
		_("Purchase approved — please order it and attach the receipt."),
		doc,
		users=[doc.solar_approver],
		subteam=doc.solar_subteam,
	)


def on_update(doc, method=None):
	if doc.material_request_type != "Purchase" or not doc.has_value_changed("workflow_state"):
		return
	if doc.workflow_state == "Pending Approval":
		notify.send(
			"Purchase needs approval",
			_("Purchase needs approval."),
			doc,
			users=scope.get_approvers([doc.solar_subteam] if doc.solar_subteam else []),
			subteam=doc.solar_subteam,
		)
	elif doc.workflow_state == "Rejected":
		notify.send(
			"Purchase needs approval",
			_("Purchase rejected, see comments."),
			doc,
			users=[doc.solar_requested_by],
			subteam=doc.solar_subteam,
		)


def default_budget_line(subteam, source=None):
	budget = active_budget()
	if not budget:
		return None
	if source in ("Two-bin", "Reorder card") and settings().shop_supplies_line:
		return settings().shop_supplies_line
	if subteam:
		line = frappe.db.get_value("Budget Line", {"budget": budget, "subteam": subteam}, "name")
		if line:
			return line
	return None


def active_budget():
	return settings().active_budget or frappe.db.get_value("Solar Budget", {"is_active": 1}, "name")


def check_must_have(doc):
	"""Optional rule: until the minimum target is raised, only must-have lines are approved."""
	from ubc_solar.money.budget import get_budget_summary

	line = frappe.db.get_value("Budget Line", doc.solar_budget_line, ["budget", "priority"], as_dict=True)
	if not line or line.priority != "Nice-to-have":
		return
	if not frappe.db.get_value("Solar Budget", line.budget, "enforce_must_have"):
		return
	summary = get_budget_summary(line.budget)
	if summary["raised"] < summary["minimum_target"]:
		frappe.throw(
			_("{0} is a nice-to-have line, and the minimum target isn't raised yet ({1} of {2}).").format(
				doc.solar_budget_line,
				frappe.format(summary["raised"], "Currency"),
				frappe.format(summary["minimum_target"], "Currency"),
			)
		)


def warn_unrecounted(doc):
	"""Anything expensive gets a quick count before it's reordered."""
	days = cint(settings().recount_window_days) or 30
	since = add_days(nowdate(), -days)
	stale = []
	for row in doc.items:
		if frappe.db.get_value("Item", row.item_code, "solar_inventory_type") != "Expensive / Long-lead":
			continue
		counted = frappe.db.sql(
			"""select 1 from `tabStock Reconciliation Item` sri join `tabStock Reconciliation` sr on sr.name = sri.parent
			where sr.docstatus = 1 and sri.item_code = %s and sr.posting_date >= %s limit 1""",
			(row.item_code, since),
		)
		if not counted:
			stale.append(row.item_code)
	if stale:
		frappe.msgprint(
			_("Recount these before ordering (not counted in the last {0} days): {1}").format(days, ", ".join(stale)),
			title=_("Expensive parts"),
			indicator="orange",
		)


# ------------------------------------------------------------------ from a BOM
def create_purchase_from_bom(bom):
	"""Turn an approved BOM's buy lines into one approved purchase request."""
	full_quantity = settings().bom_purchase_quantity == "Full BOM quantity"
	lines = []
	for row in bom.items:
		item = frappe.db.get_value(
			"Item",
			row.item_code,
			["solar_make_or_buy", "default_material_request_type", "is_stock_item", "is_purchase_item",
			 "last_purchase_rate", "valuation_rate", "stock_uom"],
			as_dict=True,
		)
		buy = item.solar_make_or_buy == "Buy" or (not item.solar_make_or_buy and item.default_material_request_type == "Purchase")
		if not buy:
			continue
		needed = flt(row.stock_qty)
		in_stock = available_qty(row.item_code) if item.is_stock_item else 0
		qty = needed if full_quantity or not item.is_stock_item else max(0.0, needed - max(0.0, projected_qty(row.item_code)))
		if qty <= 0:
			continue
		lines.append(
			{
				"item_code": row.item_code,
				"qty": qty,
				"uom": item.stock_uom,
				"conversion_factor": 1,
				"rate": flt(item.last_purchase_rate) or flt(row.rate) or flt(item.valuation_rate),
				"solar_in_stock": in_stock,
			}
		)
	if not lines:
		frappe.msgprint(_("Everything on this BOM is made in-house or already in stock, so nothing needs buying."), alert=True)
		return None

	from ubc_solar.cars.bom import approval_subteams

	subteams = approval_subteams(bom)
	subteam = next((s for s in subteams if scope.can_approve([s])), subteams[0] if subteams else None)
	mr = frappe.get_doc(
		{
			"doctype": "Material Request",
			"material_request_type": "Purchase",
			"company": bom.company,
			"transaction_date": nowdate(),
			"solar_source": "BOM",
			"solar_bom": bom.name,
			"solar_project": bom.solar_project,
			"solar_car": bom.solar_car,
			"solar_subteam": subteam,
			"solar_requested_by": bom.solar_bom_owner or bom.owner,
			"items": lines,
		}
	)
	mr.insert(ignore_permissions=True)
	from frappe.model.workflow import apply_workflow

	apply_workflow(mr, "Approve")
	return mr.name


def available_qty(item_code):
	return flt(frappe.db.sql("select sum(actual_qty) from tabBin where item_code=%s", item_code)[0][0])


def projected_qty(item_code):
	"""In stock, plus already requested or ordered, minus reserved."""
	return flt(frappe.db.sql("select sum(projected_qty) from tabBin where item_code=%s", item_code)[0][0])


# ------------------------------------------------------------------ order and receive
def _check_owner(mr):
	if mr.material_request_type != "Purchase" or mr.docstatus != 1:
		frappe.throw(_("This purchase isn't approved yet."))
	user = frappe.session.user
	if user == mr.solar_approver or scope.is_admin(user) or scope.is_captain(user):
		return
	division = scope.get_division(mr.solar_subteam)
	if division and division in scope.exec_divisions(user):
		return
	frappe.throw(
		_("{0} approved this purchase, so they order and receive it (or their division's Exec, or the Captain).").format(
			frappe.utils.get_fullname(mr.solar_approver)
		),
		frappe.PermissionError,
	)


def _attach_file(file_url, doctype, name):
	"""Attach an uploaded file (the receipt) to a record."""
	if not file_url:
		return None
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if file_name:
		file_doc = frappe.get_doc("File", file_name)
		if not file_doc.attached_to_doctype:
			file_doc.attached_to_doctype, file_doc.attached_to_name = doctype, name
			file_doc.save(ignore_permissions=True)
	return file_url


@frappe.whitelist()
def mark_ordered(material_request: str, supplier: str, receipt: str, order_number: str | None = None,
	rates: str | dict | None = None, paid_by: str | None = None):
	"""The approver placed the order: record it with the receipt (creates the Purchase Order)."""
	from erpnext.stock.doctype.material_request.material_request import make_purchase_order

	mr = frappe.get_doc("Material Request", material_request)
	_check_owner(mr)
	if mr.workflow_state != "Approved":
		frappe.throw(_("This purchase is {0}, not waiting to be ordered.").format(mr.workflow_state))
	if not receipt:
		frappe.throw(_("Attach the receipt."))
	rates = frappe.parse_json(rates) if isinstance(rates, str) else (rates or {})

	po = make_purchase_order(mr.name)
	po.supplier = supplier
	po.transaction_date = nowdate()
	po.schedule_date = max(getdate(r.schedule_date) for r in mr.items)
	po.solar_material_request = mr.name
	po.solar_budget_line = mr.solar_budget_line
	po.solar_receipt = receipt
	for row in po.items:
		if row.item_code in rates and rates[row.item_code] is not None:
			row.rate = flt(rates[row.item_code])
		row.schedule_date = max(getdate(row.schedule_date or nowdate()), getdate(po.transaction_date))
	po.flags.ignore_permissions = True
	po.insert()
	po.submit()

	_attach_file(receipt, "Material Request", mr.name)
	values = {
		"solar_supplier": supplier,
		"solar_order_number": order_number,
		"solar_receipt": receipt,
		"solar_purchase_order": po.name,
		"workflow_state": "Ordered",
	}
	if paid_by:
		values["solar_paid_by"] = paid_by
		if paid_by == "Member (reimbursement)":
			values["solar_reimbursement_status"] = "Requested"
			values["solar_reimburse_to"] = mr.solar_reimburse_to or frappe.session.user
	mr.db_set(values)
	mr.add_comment("Info", _("Ordered from {0}{1}.").format(supplier, f" (order {order_number})" if order_number else ""))
	return po.name


@frappe.whitelist()
def mark_received(material_request: str, lines: str | list):
	"""The delivery arrived and was checked: put the parts into stock (Purchase Receipt).

	lines: [{"item_code", "qty", "warehouse", "expiry_date"}]
	"""
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	mr = frappe.get_doc("Material Request", material_request)
	_check_owner(mr)
	if mr.workflow_state != "Ordered" or not mr.solar_purchase_order:
		frappe.throw(_("Mark this purchase as ordered first."))
	lines = frappe.parse_json(lines) if isinstance(lines, str) else lines
	by_item = {}
	for line in lines or []:
		if flt(line.get("qty")) > 0:
			by_item.setdefault(line["item_code"], []).append(line)
	if not by_item:
		frappe.throw(_("Enter what arrived."))

	pr = make_purchase_receipt(mr.solar_purchase_order)
	ordered = {}
	for row in pr.items:
		data = row.as_dict()
		for key in ("name", "idx", "parent", "parentfield", "parenttype", "doctype"):
			data.pop(key, None)
		ordered.setdefault(row.item_code, data)
	missing = set(by_item) - set(ordered)
	if missing:
		frappe.throw(_("These aren't waiting to be received on this order: {0}").format(", ".join(sorted(missing))))

	pr.items = []
	for item_code, item_lines in by_item.items():
		has_batch = frappe.db.get_value("Item", item_code, "has_batch_no")
		for line in item_lines:  # one line per shelf the delivery is split across
			row = dict(ordered[item_code])
			row["qty"] = row["received_qty"] = flt(line["qty"])
			row["stock_qty"] = flt(line["qty"]) * flt(row.get("conversion_factor") or 1)
			row["warehouse"] = line.get("warehouse") or row.get("warehouse")
			if has_batch:
				if not line.get("expiry_date"):
					frappe.throw(_("{0} is perishable: enter its expiry date.").format(item_code))
				row["use_serial_batch_fields"] = 1
				row["batch_no"] = make_batch(item_code, line["expiry_date"], pr.supplier)
			pr.append("items", row)
	pr.flags.ignore_permissions = True
	pr.insert()
	pr.submit()
	return pr.name


def make_batch(item_code, expiry_date, supplier=None):
	batch = frappe.get_doc(
		{"doctype": "Batch", "item": item_code, "expiry_date": expiry_date, "supplier": supplier}
	)
	batch.insert(ignore_permissions=True)
	return batch.name


def purchase_receipt_on_submit(doc, method=None):
	"""After a delivery is received (by button or by hand): update the purchase and ping the requester."""
	requests = {row.material_request for row in doc.items if row.material_request}
	for name in requests:
		mr = frappe.get_doc("Material Request", name)
		if mr.material_request_type != "Purchase":
			continue
		mr.reload()
		if flt(mr.per_received) >= 100:
			mr.db_set("workflow_state", "Received")
		places = ", ".join(sorted({row.warehouse for row in doc.items if row.material_request == name and row.warehouse}))
		notify.send(
			"Parts arrived",
			_("Your parts arrived and are in stock ({0}).").format(places),
			mr,
			users=[mr.solar_requested_by],
			subteam=mr.solar_subteam,
		)
