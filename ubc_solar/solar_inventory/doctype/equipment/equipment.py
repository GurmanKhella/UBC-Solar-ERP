# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, nowdate

from ubc_solar.solar_inventory.stock import check_member


class Equipment(Document):
	def validate(self):
		self.equipment_name = (self.equipment_name or "").strip()
		if self.tracking != "By toolbox or wall":
			self.group_location = None

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.condition != self.condition and self.condition in ("Needs Repair", "Missing"):
			notify_attention(self)


def notify_attention(doc):
	from ubc_solar.solar_automation import notify
	from ubc_solar.team import scope

	notify.send(
		"Equipment needs attention",
		_("{0} is marked {1}.").format(doc.equipment_name, doc.condition.lower()),
		doc,
		users=scope.get_approvers([], level="exec"),
	)


def _get(name):
	check_member()
	return frappe.get_doc("Equipment", name)


@frappe.whitelist()
def check_out(equipment: str, purpose: str | None = None, competition: str | None = None):
	doc = _get(equipment)
	if doc.tracking == "By toolbox or wall":
		frappe.throw(_("{0} is tracked by toolbox or wall, not checked out.").format(doc.equipment_name))
	if doc.checked_out_to:
		frappe.throw(
			_("{0} is already checked out to {1}.").format(doc.equipment_name, frappe.utils.get_fullname(doc.checked_out_to))
		)
	now = now_datetime()
	frappe.get_doc(
		{
			"doctype": "Equipment Checkout",
			"equipment": doc.name,
			"user": frappe.session.user,
			"checked_out_on": now,
			"purpose": purpose,
			"competition": competition,
		}
	).insert(ignore_permissions=True)
	doc.db_set(
		{
			"checked_out_to": frappe.session.user,
			"checked_out_on": now,
			"checkout_purpose": purpose,
			"competition": competition,
		}
	)
	return doc.name


@frappe.whitelist()
def return_equipment(equipment: str):
	doc = _get(equipment)
	if not doc.checked_out_to:
		return doc.name
	open_checkout = frappe.db.get_value(
		"Equipment Checkout", {"equipment": doc.name, "returned_on": ["is", "not set"]}, "name", order_by="creation desc"
	)
	if open_checkout:
		frappe.db.set_value("Equipment Checkout", open_checkout, "returned_on", now_datetime())
	doc.db_set(
		{"checked_out_to": None, "checked_out_on": None, "checkout_purpose": None, "competition": None}
	)
	return doc.name


@frappe.whitelist()
def confirm_check(equipment: str, condition: str = "Working", location: str | None = None):
	"""Walk-through or packing check: confirm it's here and what condition it's in."""
	if condition not in ("Working", "Needs Repair", "Missing"):
		frappe.throw(_("Unknown condition {0}").format(condition))
	doc = _get(equipment)
	doc.condition = condition
	if location:
		doc.location = location
	doc.last_checked_on = nowdate()
	doc.last_checked_by = frappe.session.user
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name
