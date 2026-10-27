"""Daily inventory jobs."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate


def batch_qty(batch):
	"""Quantity left in a batch across all locations (expired batches included)."""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	return sum(flt(row.get("qty")) for row in get_batch_qty(batch_no=batch, for_stock_levels=True) or [])


def expiring_batches(days=None):
	"""Batches with stock left that expire within `days` (or have already expired)."""
	days = cint(days if days is not None else frappe.db.get_single_value("Solar Settings", "expiry_warning_days")) or 30
	batches = frappe.get_all(
		"Batch",
		filters={"expiry_date": ["<=", add_days(nowdate(), days)], "disabled": 0},
		fields=["name", "item", "item_name", "expiry_date", "solar_expiry_notified"],
		order_by="expiry_date asc",
	)
	result = []
	for b in batches:
		qty = batch_qty(b.name)
		if qty > 0:
			result.append({**b, "qty": qty})
	return [frappe._dict(r) for r in result]


def flag_expiring_batches():
	"""The ERP flags perishables (prepreg, solder paste) before they expire."""
	from ubc_solar.solar_automation import notify

	rows = [r for r in expiring_batches() if not r.solar_expiry_notified]
	if not rows:
		return
	lines = ", ".join(f"{r.item_name or r.item} (batch {r.name}, {flt(r.qty):g} left, expires {r.expiry_date})" for r in rows)
	notify.send("Expiring soon", _("Expiring soon: {0}. Use it or toss it at the monthly fridge check.").format(lines))
	for r in rows:
		frappe.db.set_value("Batch", r.name, "solar_expiry_notified", 1)
