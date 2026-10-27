"""Parse BOM exports from Altium and SolidWorks/3DEXPERIENCE into a common tree.

This module has no Frappe dependency so it can be tested on its own. The BOM
Import doctype turns the parsed tree into Items and draft BOMs.

Supported files: .csv, .xlsx, .xls (Altium can produce all three; SolidWorks
BOM tables save as .xlsx or .csv; 3DEXPERIENCE exports .csv/.xlsx).
"""

import csv
import io
import re
from dataclasses import dataclass, field

MAKE = "Make"
BUY = "Buy"


@dataclass
class BomLine:
	"""One row of a CAD BOM. Children are set for SolidWorks subassemblies."""

	part_number: str = ""  # team part number (SolidWorks PART NUMBER property)
	mpn: str = ""  # manufacturer part number
	manufacturer: str = ""
	description: str = ""
	qty: float = 0
	designators: str = ""
	footprint: str = ""
	material: str = ""
	make_or_buy: str = ""  # MAKE, BUY or "" when the file doesn't say
	vendor: str = ""
	supplier: str = ""
	supplier_part_number: str = ""
	unit_price: float = 0
	row: int = 0  # 1-based row in the source file, for messages
	children: list["BomLine"] = field(default_factory=list)

	@property
	def is_assembly(self):
		return bool(self.children)


@dataclass
class ParsedBom:
	lines: list[BomLine]
	warnings: list[str]
	source: str


class BomParseError(Exception):
	pass


# Column aliases, compared after normalising (lowercase, letters and digits only).
ALTIUM_COLUMNS = {
	"mpn": [
		"manufacturerpartnumber",
		"manufacturerpartnumber1",
		"manufacturer1partnumber",
		"mfrpartnumber",
		"mfrpartno",
		"mfrpn",
		"mpn",
		"partnumber",
	],
	"manufacturer": ["manufacturer", "manufacturer1", "manufacturername", "mfr", "mfrname"],
	"designators": ["designator", "designators", "reference", "references", "refdes"],
	"qty": ["quantity", "qty"],
	"description": ["description", "comment", "value", "name"],
	"footprint": ["footprint", "package"],
	"supplier": ["supplier1", "supplier"],
	"supplier_part_number": ["supplierpartnumber1", "supplierpartnumber", "supplierorderno1"],
	"unit_price": ["supplierunitprice1", "unitprice", "price"],
}

SOLIDWORKS_COLUMNS = {
	"item_no": ["itemno", "item", "itemnumber", "find", "findno"],
	"level": ["level", "depth"],
	"part_number": ["partnumber", "partno", "pn", "name", "number"],
	"description": ["description", "title"],
	"qty": ["qty", "quantity"],
	"material": ["material"],
	"make_or_buy": ["makeorbuy", "makebuy", "makeby", "source", "procurement"],
	"vendor": ["vendor", "supplier", "manufacturer"],
	"mpn": ["manufacturerpartnumber", "mpn", "vendorpartnumber", "mfrpartnumber"],
}


def normalise(header):
	return re.sub(r"[^a-z0-9]", "", str(header or "").lower())


def read_rows(filename, content):
	"""Return the file as a list of rows (lists of strings)."""
	name = filename.lower()
	if name.endswith(".csv") or name.endswith(".txt"):
		text = _decode(content)
		dialect = csv.excel
		try:
			dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
		except csv.Error:
			pass
		return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text), dialect)]
	if name.endswith(".xlsx") or name.endswith(".xlsm"):
		from openpyxl import load_workbook

		wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
		ws = wb.worksheets[0]
		return [[_cell(c) for c in row] for row in ws.iter_rows(values_only=True)]
	if name.endswith(".xls"):
		import xlrd

		book = xlrd.open_workbook(file_contents=content)
		sheet = book.sheet_by_index(0)
		return [[_cell(sheet.cell_value(r, c)) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
	raise BomParseError(f"Unsupported file type: {filename}. Upload a .csv, .xlsx or .xls export.")


def _decode(content):
	if isinstance(content, str):
		return content
	for encoding in ("utf-8-sig", "cp1252", "latin-1"):
		try:
			return content.decode(encoding)
		except UnicodeDecodeError:
			continue
	raise BomParseError("Could not read the file's text encoding.")


def _cell(value):
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	return str(value).strip()


def _to_float(value):
	text = str(value or "").strip().replace(",", "").replace("$", "")
	if not text:
		return 0.0
	try:
		return float(text)
	except ValueError:
		return 0.0


def find_header(rows, aliases, required):
	"""Find the header row (the first row that has every required column).

	Returns (row_index, {field: column_index}).
	"""
	for index, row in enumerate(rows[:40]):
		normalised = [normalise(c) for c in row]
		mapping = {}
		for fieldname, names in aliases.items():
			for name in names:  # aliases are in priority order
				if name in normalised:
					mapping[fieldname] = normalised.index(name)
					break
		if all(any(r in mapping for r in group) for group in required):
			return index, mapping
	return None, {}


def _get(row, mapping, fieldname):
	col = mapping.get(fieldname)
	if col is None or col >= len(row):
		return ""
	return str(row[col]).strip()


def parse_make_or_buy(value):
	v = normalise(value)
	if v in ("make", "m", "made", "manufactured", "inhouse", "fabricate", "fab", "machined"):
		return MAKE
	if v in ("buy", "b", "bought", "purchase", "purchased", "cots", "ots", "offtheshelf"):
		return BUY
	return ""


def parse_altium(filename, content):
	rows = read_rows(filename, content)
	header_index, mapping = find_header(
		rows, ALTIUM_COLUMNS, required=[("qty", "designators"), ("mpn", "description")]
	)
	if header_index is None:
		raise BomParseError(
			"Could not find the header row. An Altium BOM needs a Quantity or Designator column "
			"and a Manufacturer Part Number or Description/Comment column."
		)

	lines, warnings = [], []
	for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
		if not any(str(c).strip() for c in row):
			continue
		line = BomLine(
			mpn=_get(row, mapping, "mpn"),
			manufacturer=_get(row, mapping, "manufacturer"),
			description=_get(row, mapping, "description"),
			designators=_get(row, mapping, "designators"),
			footprint=_get(row, mapping, "footprint"),
			supplier=_get(row, mapping, "supplier"),
			supplier_part_number=_get(row, mapping, "supplier_part_number"),
			unit_price=_to_float(_get(row, mapping, "unit_price")),
			make_or_buy=BUY,
			row=offset,
		)
		if not line.mpn and not line.description:
			continue
		qty_text = _get(row, mapping, "qty")
		line.qty = _to_float(qty_text)
		if not line.qty and line.designators:
			line.qty = float(len(split_designators(line.designators)))
		if not line.qty:
			warnings.append(f"Row {offset}: no quantity for {line.mpn or line.description}; skipped.")
			continue
		if not line.mpn:
			warnings.append(
				f"Row {offset}: {line.description} has no manufacturer part number. "
				"Add it in Altium, or fill it in on the BOM during review."
			)
		lines.append(line)

	return ParsedBom(lines=_merge_duplicates(lines, warnings), warnings=warnings, source="Altium")


def split_designators(text):
	parts = re.split(r"[,\s;]+", text.strip())
	result = []
	for part in parts:
		if not part:
			continue
		match = re.fullmatch(r"([A-Za-z_]+)(\d+)-\1?(\d+)", part)  # R1-R4 or R1-4
		if match and int(match.group(3)) >= int(match.group(2)):
			prefix = match.group(1)
			result.extend(f"{prefix}{n}" for n in range(int(match.group(2)), int(match.group(3)) + 1))
		else:
			result.append(part)
	return result


def _merge_duplicates(lines, warnings):
	"""Altium sometimes lists the same MPN on several rows; combine them."""
	merged, by_key = [], {}
	for line in lines:
		key = (line.mpn or "").upper() or None
		if key and key in by_key:
			first = by_key[key]
			first.qty += line.qty
			first.designators = ", ".join(d for d in (first.designators, line.designators) if d)
			warnings.append(f"Row {line.row}: {line.mpn} also appears on row {first.row}; quantities combined.")
			continue
		if key:
			by_key[key] = line
		merged.append(line)
	return merged


def parse_solidworks(filename, content, source="SolidWorks"):
	"""Parse an indented SolidWorks or 3DEXPERIENCE BOM.

	Structure comes from ITEM NO. (1, 1.1, 1.2, 2) or a Level column (0/1/2...).
	Quantities in an indented BOM are per parent assembly.
	"""
	rows = read_rows(filename, content)
	header_index, mapping = find_header(
		rows, SOLIDWORKS_COLUMNS, required=[("part_number", "description"), ("qty",)]
	)
	if header_index is None:
		raise BomParseError(
			"Could not find the header row. A SolidWorks BOM needs PART NUMBER (or DESCRIPTION) "
			"and QTY columns. Check the part-properties standard is used in the BOM table."
		)

	warnings, flat = [], []
	for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
		if not any(str(c).strip() for c in row):
			continue
		line = BomLine(
			part_number=_get(row, mapping, "part_number"),
			description=_get(row, mapping, "description"),
			material=_get(row, mapping, "material"),
			vendor=_get(row, mapping, "vendor"),
			mpn=_get(row, mapping, "mpn"),
			make_or_buy=parse_make_or_buy(_get(row, mapping, "make_or_buy")),
			qty=_to_float(_get(row, mapping, "qty")),
			row=offset,
		)
		if not line.part_number and not line.description:
			continue
		depth = _depth(_get(row, mapping, "item_no"), _get(row, mapping, "level"))
		if depth is None:
			depth = 1
		if not line.qty:
			warnings.append(f"Row {offset}: no quantity for {line.part_number or line.description}; using 1.")
			line.qty = 1
		if not line.part_number:
			warnings.append(
				f"Row {offset}: {line.description} has no part number. Fill in the PART NUMBER "
				"property in SolidWorks, or a new team number will be generated."
			)
		flat.append((depth, line))

	if not flat:
		raise BomParseError("The file has a header row but no parts under it.")

	# Normalise so the shallowest level in the file is depth 1.
	shallowest = min(d for d, _ in flat)
	roots, stack = [], []
	for depth, line in flat:
		depth = depth - shallowest + 1
		while stack and stack[-1][0] >= depth:
			stack.pop()
		if stack:
			stack[-1][1].children.append(line)
		else:
			roots.append(line)
		stack.append((depth, line))

	_fill_make_or_buy(roots)
	return ParsedBom(lines=roots, warnings=warnings, source=source)


def _depth(item_no, level):
	if level not in ("", None):
		try:
			return int(float(level))
		except ValueError:
			pass
	if item_no:
		parts = [p for p in str(item_no).strip().split(".") if p != ""]
		if parts and all(p.isdigit() for p in parts):
			return len(parts)
	return None


def _fill_make_or_buy(lines):
	"""Assemblies are made; anything unmarked defaults to Make (designed in CAD)."""
	for line in lines:
		if line.children:
			line.make_or_buy = line.make_or_buy or MAKE
			_fill_make_or_buy(line.children)
		elif not line.make_or_buy:
			line.make_or_buy = BUY if line.mpn else MAKE


def parse(source, filename, content):
	if source == "Altium":
		return parse_altium(filename, content)
	if source in ("SolidWorks", "3DEXPERIENCE"):
		return parse_solidworks(filename, content, source=source)
	raise BomParseError(f"Unknown BOM source: {source}")
