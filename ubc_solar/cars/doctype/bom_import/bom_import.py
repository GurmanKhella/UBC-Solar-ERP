# Copyright (c) 2026, UBC Solar and contributors
# For license information, please see license.txt

"""Import a CAD BOM export into a draft BOM owned by the project owner.

This is the only manual step: the designer exports the BOM from Altium or
SolidWorks/3DEXPERIENCE and uploads the file. The owner then reviews the draft,
adds what CAD left out, and marks it Ready for Review.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from ubc_solar.cars import bom_parsers
from ubc_solar.cars.parts import TEAM_NUMBER
from ubc_solar.cars.utils import assert_car_editable, item_group

SMALL_PART_PREFIXES = ("R", "C", "L", "FB")


class BOMImport(Document):
	def validate(self):
		car = frappe.db.get_value("Solar Project", self.solar_project, "car")
		assert_car_editable(car, self)

	@frappe.whitelist()
	def run_import(self):
		self.check_permission("write")
		if not frappe.has_permission("BOM", "create"):
			frappe.throw(_("You can't create BOMs."), frappe.PermissionError)
		file_doc = frappe.get_doc("File", {"file_url": self.bom_file})
		content = file_doc.get_content()
		if isinstance(content, str):
			content = content.encode()
		try:
			parsed = bom_parsers.parse(self.source, file_doc.file_name or self.bom_file, content)
		except bom_parsers.BomParseError as e:
			self.db_set({"status": "Failed", "log": str(e), "summary": _("Import failed.")})
			frappe.throw(str(e), title=_("Couldn't read the BOM"))

		importer = Importer(self, parsed)
		bom = importer.run()
		summary = _("Draft BOM {0} with {1} lines. {2} new parts created.").format(
			bom, importer.line_count, len(importer.created_items)
		)
		if importer.sub_boms:
			summary += " " + _("Sub-assembly BOMs: {0}. Approve them before the main BOM.").format(", ".join(importer.sub_boms))
		messages = importer.warnings
		self.db_set(
			{
				"status": "Imported",
				"bom": bom,
				"summary": summary,
				"log": "\n".join(messages) if messages else _("No problems found."),
			}
		)
		return {"bom": bom, "summary": summary, "warnings": messages}


class Importer:
	def __init__(self, doc, parsed):
		self.doc = doc
		self.parsed = parsed
		self.project = frappe.get_doc("Solar Project", doc.solar_project)
		self.company = frappe.db.get_single_value("Solar Settings", "company")
		self.warnings = list(parsed.warnings)
		self.created_items = []
		self.sub_boms = []
		self.line_count = 0

	def run(self):
		lines = self.parsed.lines
		if self.parsed.source != "Altium" and len(lines) == 1 and lines[0].is_assembly:
			top = lines[0]
			if top.part_number and top.part_number != self.project.part:
				self.warnings.append(
					_("The top assembly in the file is {0}; it was imported as this project's part {1}.").format(
						top.part_number, self.project.part
					)
				)
			lines = top.children
		bom = self.make_bom(self.project.part, lines)
		self.line_count = frappe.db.count("BOM Item", {"parent": bom, "parenttype": "BOM"})
		return bom

	def make_bom(self, item_code, lines):
		rows = []
		for line in lines:
			code = self.resolve_item(line)
			if not code:
				continue
			if line.children:
				self.sub_boms.append(self.make_bom(code, line.children))
			rows.append(
				{
					"item_code": code,
					"qty": flt(line.qty) or 1,
					"rate": flt(line.unit_price),
					"solar_designators": line.designators,
				}
			)
		if not rows:
			frappe.throw(_("No parts could be imported from this file."))
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": item_code,
				"quantity": 1,
				"company": self.company,
				"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				"rm_cost_as_per": "Valuation Rate",
				"solar_project": self.project.name,
				"solar_bom_owner": self.project.project_owner,
				"solar_design_revision": self.doc.design_revision,
				"is_default": 1,
				"items": rows,
			}
		)
		bom.insert()
		return bom.name

	# -------------------------------------------------------------- items
	def resolve_item(self, line):
		if self.parsed.source == "Altium":
			return self.altium_item(line)
		return self.mechanical_item(line)

	def altium_item(self, line):
		if line.mpn:
			existing = frappe.db.get_value("Item", line.mpn) or frappe.db.get_value("Item", {"solar_mpn": line.mpn})
			if existing:
				return existing
			return self.create_item(
				item_code=line.mpn,
				item_name=line.description or line.mpn,
				item_group=item_group("electrical"),
				make_or_buy="Buy",
				discipline="Electrical",
				inventory_type="Small Part" if self.is_small_part(line.designators) else "Component / Material",
				manufacturer=line.manufacturer,
				mpn=line.mpn,
				price=line.unit_price,
				supplier=line.supplier,
				supplier_part_number=line.supplier_part_number,
			)
		return self.match_or_create_unnumbered(line, item_group("electrical"), "Electrical")

	def mechanical_item(self, line):
		code = line.part_number
		if code and frappe.db.exists("Item", code):
			return code
		make = line.make_or_buy == bom_parsers.MAKE
		group = item_group("assemblies") if line.children else item_group("mechanical")
		if code:
			return self.create_item(
				item_code=code,
				item_name=line.description or code,
				item_group=group,
				make_or_buy="Make" if make else "Buy",
				discipline="Mechanical",
				material=line.material,
				vendor=line.vendor,
				mpn=None if make else (line.mpn or code),
			)
		if make:
			return self.create_item(
				item_code=None,
				item_name=line.description or _("Unnamed part"),
				item_group=group,
				make_or_buy="Make",
				discipline="Mechanical",
				material=line.material,
				vendor=line.vendor,
			)
		return self.match_or_create_unnumbered(line, item_group("mechanical"), "Mechanical")

	def match_or_create_unnumbered(self, line, group, discipline):
		"""A bought part with no part number: reuse one with the same description, or number it."""
		description = (line.description or "").strip()
		if not description:
			self.warnings.append(_("Row {0}: no part number or description; skipped.").format(line.row))
			return None
		existing = frappe.db.get_value(
			"Item", {"item_name": description[:140], "solar_make_or_buy": "Buy", "solar_mpn": ["in", ["", None]]}
		)
		if existing:
			return existing
		return self.create_item(
			item_code=None,
			item_name=description,
			item_group=group,
			make_or_buy="Buy",
			discipline=discipline,
			vendor=line.vendor,
		)

	def create_item(self, item_code, item_name, item_group, make_or_buy, discipline, inventory_type="Component / Material",
		manufacturer=None, mpn=None, material=None, vendor=None, price=0, supplier=None, supplier_part_number=None):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": (item_name or item_code or "")[:140],
				"description": item_name,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"include_item_in_manufacturing": 1,
				"solar_make_or_buy": make_or_buy,
				"solar_discipline": discipline,
				"solar_inventory_type": inventory_type,
				"solar_manufacturer": manufacturer,
				"solar_mpn": mpn,
				"solar_material": material,
				"solar_vendor": vendor or supplier,
				"solar_project": self.project.name if make_or_buy == "Make" else None,
				"valuation_rate": flt(price),
			}
		)
		if item_code and make_or_buy == "Make":
			match = TEAM_NUMBER.match(item_code)
			if match:
				item.solar_base_part_number, item.solar_revision = match.group("base"), match.group("rev")
		if supplier and supplier_part_number and frappe.db.exists("Supplier", supplier):
			item.append("supplier_items", {"supplier": supplier, "supplier_part_no": supplier_part_number})
		item.insert()
		self.created_items.append(item.name)
		return item.name

	@staticmethod
	def is_small_part(designators):
		first = bom_parsers.split_designators(designators or "")[:1]
		if not first:
			return False
		prefix = "".join(ch for ch in first[0] if ch.isalpha()).upper()
		return prefix in SMALL_PART_PREFIXES
