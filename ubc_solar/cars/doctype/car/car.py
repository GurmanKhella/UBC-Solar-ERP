# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from ubc_solar.cars.utils import make_team_item
from ubc_solar.team import scope


class Car(Document):
	def validate(self):
		self.car_version = (self.car_version or "").strip()
		self.car_title = f"{self.car_version} {(self.car_name or '').strip()}".strip()
		before = self.get_doc_before_save()
		if before and before.status == "Retired" and not self.flags.unretire:
			if frappe.session.user != "Administrator":
				frappe.throw(_("{0} is retired, so it's view-only.").format(self.car_title))
		if self.status == "Retired" and (not before or before.status != "Retired") and not self.flags.retiring:
			frappe.throw(_("Use the Retire Car button: it salvages parts and publishes the wiki snapshot."))
		if self.previous_car == self.name:
			self.previous_car = None

	def after_insert(self):
		if not self.vehicle_item:
			item = make_team_item(f"{self.car_title} vehicle", "Assembly", "Vehicles")
			self.db_set("vehicle_item", item)

	def onload(self):
		self.set_onload("overview", get_overview(self.name))


def get_overview(car):
	vehicle_item = frappe.db.get_value("Car", car, "vehicle_item")
	vehicle_bom = frappe.db.get_value("Item", vehicle_item, "default_bom") if vehicle_item else None
	return {
		"vehicle_bom": vehicle_bom,
		"vehicle_cost": flt(frappe.db.get_value("BOM", vehicle_bom, "total_cost")) if vehicle_bom else 0,
		"projects": frappe.db.count("Solar Project", {"car": car}),
		"boms_waiting": frappe.db.count(
			"BOM", {"solar_car": car, "docstatus": 0, "workflow_state": "Ready for Review"}
		),
		"open_repairs": frappe.db.count("Car Repair", {"car": car, "status": ["!=", "Fixed"]}),
		"packages": frappe.db.count("Manufacturing Package", {"car": car}),
	}


def _require_top_position():
	if not (scope.is_admin() or scope.is_captain() or scope.exec_divisions()):
		frappe.throw(_("Only the Captain or an Exec can do this."), frappe.PermissionError)


@frappe.whitelist()
def set_up_car(car: str, make_budget_active: int = 0):
	"""Start a new car: a manufacturing package per subsystem and a budget with a
	line per subteam (amounts to fill in)."""
	_require_top_position()
	doc = frappe.get_doc("Car", car)
	if doc.status == "Retired":
		frappe.throw(_("{0} is retired.").format(doc.car_title))
	created = {"packages": [], "budget": None}
	for subsystem in frappe.get_all("Subsystem", filters={"enabled": 1}, order_by="sort_order asc", pluck="name"):
		if not frappe.db.exists("Manufacturing Package", {"car": car, "subsystem": subsystem}):
			pkg = frappe.get_doc({"doctype": "Manufacturing Package", "car": car, "subsystem": subsystem})
			pkg.insert()
			created["packages"].append(pkg.name)

	if not doc.budget:
		from ubc_solar.money.budget import make_budget_for_car

		budget = make_budget_for_car(doc, make_active=bool(int(make_budget_active)))
		doc.db_set("budget", budget)
		created["budget"] = budget
	return created


@frappe.whitelist()
def salvage_parts(car: str, rows: str | list):
	"""Add usable parts from a car back into stock (Material Receipt)."""
	rows = frappe.parse_json(rows) if isinstance(rows, str) else rows
	rows = [r for r in rows or [] if r.get("item_code") and flt(r.get("qty")) > 0]
	if not rows:
		return None
	if not frappe.has_permission("Stock Entry", "create"):
		frappe.throw(_("You can't add stock."), frappe.PermissionError)
	from ubc_solar.solar_inventory.stock import make_stock_entry

	se = make_stock_entry(
		"Material Receipt",
		[
			{
				"item_code": r["item_code"],
				"qty": flt(r["qty"]),
				"t_warehouse": r.get("warehouse") or frappe.db.get_single_value("Solar Settings", "receiving_warehouse"),
			}
			for r in rows
		],
		source="Salvage",
		car=car,
		reference=frappe.get_doc("Car", car),
	)
	return se.name


@frappe.whitelist()
def retire_car(car: str, salvage_rows: str | list | None = None):
	"""Retire a car: salvage parts, make it view-only, publish the end-of-car wiki snapshot."""
	_require_top_position()
	doc = frappe.get_doc("Car", car)
	if doc.status == "Retired":
		frappe.throw(_("{0} is already retired.").format(doc.car_title))
	stock_entry = salvage_parts(car, salvage_rows or [])
	doc.status = "Retired"
	doc.retired_on = nowdate()
	doc.flags.retiring = True
	doc.save()
	frappe.enqueue(
		"ubc_solar.solar_automation.wiki.publish_car_snapshot",
		car=car,
		enqueue_after_commit=True,
	)
	return {"stock_entry": stock_entry}
