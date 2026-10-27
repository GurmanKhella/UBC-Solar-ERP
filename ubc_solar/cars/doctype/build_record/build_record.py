# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from ubc_solar.cars.utils import assert_car_editable, default_location
from ubc_solar.solar_inventory.stock import company, pick_sources


class BuildRecord(Document):
	def validate(self):
		bom = frappe.db.get_value(
			"BOM",
			self.bom,
			["item", "docstatus", "is_active", "solar_car", "solar_project", "solar_manufacturing_stage", "solar_bom_kind"],
			as_dict=True,
		)
		if bom.docstatus != 1 or not bom.is_active:
			frappe.throw(_("{0} isn't an approved, active BOM.").format(self.bom))
		self.item_code = bom.item
		self.car = bom.solar_car
		self.solar_project = bom.solar_project
		self.manufacturing_stage = self.manufacturing_stage or bom.solar_manufacturing_stage
		assert_car_editable(self.car, self)
		if flt(self.qty) <= 0:
			frappe.throw(_("Enter how many were built."))
		self.target_warehouse = (
			self.target_warehouse
			or default_location(self.item_code)
			or frappe.db.get_single_value("Solar Settings", "build_area_warehouse")
		)
		if not self.items:
			self.set("items", get_build_items(self.bom, self.qty))
		self.quality_inspection_template = self.quality_inspection_template or quality_template_for(self.bom, self.manufacturing_stage)
		if self.quality_inspection_template and not self.quality_results:
			self.set("quality_results", get_quality_rows(self.quality_inspection_template, self.serial_list()))

	def serial_list(self):
		return [s.strip() for s in (self.serial_numbers or "").splitlines() if s.strip()]

	def before_submit(self):
		self.check_stock()
		for row in self.quality_results:
			if not row.result:
				frappe.throw(_("Record a result for every quality check ({0}).").format(row.parameter))
		serials = self.serial_list()
		if serials and len(serials) != flt(self.qty):
			frappe.throw(_("Enter one serial number per unit built ({0}).").format(flt(self.qty)))
		self.stock_entry = self.make_stock_entry()
		self.quality_status = self.make_quality_inspections()

	def check_stock(self):
		short = []
		for row in self.items:
			if flt(row.qty) <= 0:
				continue
			if not row.source_warehouse:
				short.append(row.item_code)
				continue
			available = flt(frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": row.source_warehouse}, "actual_qty"))
			if available + 1e-9 < flt(row.qty):
				short.append(f"{row.item_code} ({available:g} in {row.source_warehouse})")
		if short:
			frappe.throw(
				_("Not enough in stock for: {0}. Pick another location, recount the bin, or adjust the quantity.").format(
					", ".join(short)
				),
				title=_("Missing parts"),
			)

	def make_stock_entry(self):
		item = frappe.db.get_value("Item", self.item_code, ["stock_uom", "has_serial_no"], as_dict=True)
		se = frappe.new_doc("Stock Entry")
		se.update(
			{
				"stock_entry_type": "Manufacture",
				"purpose": "Manufacture",
				"company": company(),
				"posting_date": self.build_date,
				"from_bom": 1,
				"bom_no": self.bom,
				"fg_completed_qty": flt(self.qty),
				"use_multi_level_bom": 0,
				"solar_source": "Build",
				"solar_car": self.car,
				"solar_reference_doctype": self.doctype,
				"solar_reference_name": self.name,
			}
		)
		for row in self.items:
			if flt(row.qty) > 0:
				se.append("items", {"item_code": row.item_code, "qty": flt(row.qty), "s_warehouse": row.source_warehouse})
		finished = {
			"item_code": self.item_code,
			"qty": flt(self.qty),
			"t_warehouse": self.target_warehouse,
			"is_finished_item": 1,
			"bom_no": self.bom,
			"uom": item.stock_uom,
			"conversion_factor": 1,
		}
		if item.has_serial_no and self.serial_list():
			finished.update({"use_serial_batch_fields": 1, "serial_no": "\n".join(self.serial_list())})
		se.append("items", finished)
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		return se.name

	def make_quality_inspections(self):
		if not self.quality_results:
			return None
		has_serial = frappe.db.get_value("Item", self.item_code, "has_serial_no")
		groups = {}
		for row in self.quality_results:
			groups.setdefault(row.serial_no or "", []).append(row)
		overall = "Accepted"
		for serial, rows in groups.items():
			status = "Rejected" if any(r.result == "Rejected" for r in rows) else "Accepted"
			if status == "Rejected":
				overall = "Rejected"
			qi = frappe.get_doc(
				{
					"doctype": "Quality Inspection",
					"inspection_type": "In Process",
					"reference_type": "Stock Entry",
					"reference_name": self.stock_entry,
					"item_code": self.item_code,
					"sample_size": 1 if serial else flt(self.qty),
					"inspected_by": self.built_by,
					"quality_inspection_template": self.quality_inspection_template,
					"manual_inspection": 1,
					"status": status,
					"item_serial_no": serial if serial and has_serial and frappe.db.exists("Serial No", serial) else None,
					"remarks": _("Build {0}{1}").format(self.name, f", unit {serial}" if serial else ""),
					"readings": [
						{
							"specification": r.parameter,
							"manual_inspection": 1,
							"numeric": 0,
							"reading_value": r.reading or r.result,
							"status": r.result,
						}
						for r in rows
					],
				}
			)
			qi.flags.ignore_permissions = True
			qi.insert()
			qi.submit()
		return overall

	def on_submit(self):
		bom_kind = frappe.db.get_value("BOM", self.bom, "solar_bom_kind")
		if bom_kind == "Vehicle" and self.car:
			car = frappe.get_doc("Car", self.car)
			car.built_on = self.build_date
			if car.status in ("In Design", "Building"):
				car.status = "Active"
			car.save(ignore_permissions=True)
		if self.solar_project:
			status = frappe.db.get_value("Solar Project", self.solar_project, "status")
			if status in ("Planning", "Design", "Review", "Manufacturing"):
				frappe.db.set_value("Solar Project", self.solar_project, "status", "Built")

	def on_cancel(self):
		for qi in frappe.get_all(
			"Quality Inspection", filters={"reference_type": "Stock Entry", "reference_name": self.stock_entry, "docstatus": 1}, pluck="name"
		):
			doc = frappe.get_doc("Quality Inspection", qi)
			doc.flags.ignore_permissions = True
			doc.cancel()
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.flags.ignore_permissions = True
				se.cancel()


def quality_template_for(bom, stage=None):
	if stage:
		template = frappe.db.get_value("Manufacturing Stage", stage, "quality_inspection_template")
		if template:
			return template
	template = frappe.db.get_value("BOM", bom, "quality_inspection_template")
	if template:
		return template
	project = frappe.db.get_value("BOM", bom, "solar_project")
	if project:
		category = frappe.db.get_value("Solar Project", project, "harness_category")
		if category:
			return frappe.db.get_value("Harness Category", category, "quality_inspection_template")
	return None


@frappe.whitelist()
def get_build_items(bom: str, qty: float):
	"""The parts a build uses, with the locations they'll come from."""
	doc = frappe.get_doc("BOM", bom)
	doc.check_permission("read")
	factor = flt(qty) / flt(doc.quantity or 1)
	rows = []
	for item in doc.items:
		if not frappe.db.get_value("Item", item.item_code, "is_stock_item"):
			continue  # services (PCB fab, shipping) aren't stock
		required = flt(item.stock_qty) * factor
		for warehouse, take, available in pick_sources(item.item_code, required):
			rows.append(
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"required_qty": take,
					"qty": take,
					"source_warehouse": warehouse,
					"available_qty": available,
				}
			)
	return rows


@frappe.whitelist()
def get_quality_rows(template: str, serials: list | str | None = None):
	serials = frappe.parse_json(serials) if isinstance(serials, str) else serials
	params = frappe.get_all(
		"Item Quality Inspection Parameter",
		filters={"parent": template, "parenttype": "Quality Inspection Template"},
		fields=["specification", "value", "numeric", "min_value", "max_value"],
		order_by="idx asc",
	)
	rows = []
	for serial in serials or [""]:
		for p in params:
			criteria = f"{flt(p.min_value):g} to {flt(p.max_value):g}" if p.numeric else (p.value or "")
			rows.append({"serial_no": serial, "parameter": p.specification, "criteria": criteria})
	return rows
