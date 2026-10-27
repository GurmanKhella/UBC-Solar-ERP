"""Tests for the CAD BOM parsers. Pure Python: run with
`python -m pytest ubc_solar/cars/test_bom_parsers.py` or through bench run-tests."""

import io
import unittest

from ubc_solar.cars import bom_parsers as p

ALTIUM_CSV = """\
"Bill of Materials for Project [BMS Slave.PrjPcb]"
""
"Comment","Description","Designator","Footprint","LibRef","Quantity","Manufacturer 1","Manufacturer Part Number 1","Supplier 1","Supplier Part Number 1","Supplier Unit Price 1"
"10k","RES 10K 1% 0603","R1, R2, R3","0603","RES","3","Yageo","RC0603FR-0710KL","Digi-Key","311-10.0KHRCT-ND","0.10"
"100nF","CAP CER 0.1UF 50V X7R 0603","C1-C4","0603","CAP","4","Samsung","CL10B104KB8NNNC","Digi-Key","1276-1000-1-ND","0.08"
"LTC6811","Battery monitor","U1","SSOP48","LTC6811","1","Analog Devices","LTC6811HG-1#3ZZPBF","Digi-Key","LTC6811HG-1#3ZZPBF-ND","18.50"
"TP","Test point","TP1, TP2","TP","TP","","","","","",""
"10k","RES 10K 1% 0603","R9","0603","RES","1","Yageo","RC0603FR-0710KL","Digi-Key","311-10.0KHRCT-ND","0.10"
"""

SOLIDWORKS_CSV = """\
ITEM NO.,PART NUMBER,DESCRIPTION,Material,MakeBuy,Vendor,QTY.
1,M-0042-A,Upper A-arm mount bracket,6061-T6 aluminum,Make,Sponsor machine shop,4
2,M-0050-A,Upright assembly,,,,2
2.1,M-0051-A,Upright body,7075-T6 aluminum,Make,,1
2.2,6383K221,Ball bearing,,Buy,McMaster-Carr,2
3,,Bracket spacer,Delrin,,,8
"""


class TestAltium(unittest.TestCase):
	def test_parses_altium_csv_with_title_rows(self):
		result = p.parse("Altium", "bms.csv", ALTIUM_CSV.encode())
		mpns = [line.mpn for line in result.lines]
		self.assertEqual(mpns, ["RC0603FR-0710KL", "CL10B104KB8NNNC", "LTC6811HG-1#3ZZPBF", ""])
		resistor = result.lines[0]
		self.assertEqual(resistor.qty, 4)  # 3 + 1 merged from the duplicate row
		self.assertEqual(resistor.designators, "R1, R2, R3, R9")
		self.assertEqual(resistor.manufacturer, "Yageo")
		self.assertEqual(resistor.supplier_part_number, "311-10.0KHRCT-ND")
		self.assertAlmostEqual(resistor.unit_price, 0.10)
		self.assertTrue(all(line.make_or_buy == p.BUY for line in result.lines))

	def test_quantity_from_designators_when_blank(self):
		result = p.parse("Altium", "bms.csv", ALTIUM_CSV.encode())
		test_points = result.lines[3]
		self.assertEqual(test_points.qty, 2)
		self.assertTrue(any("no manufacturer part number" in w for w in result.warnings))

	def test_designator_ranges(self):
		self.assertEqual(p.split_designators("C1-C4"), ["C1", "C2", "C3", "C4"])
		self.assertEqual(p.split_designators("R1-3, R7"), ["R1", "R2", "R3", "R7"])

	def test_xlsx(self):
		from openpyxl import Workbook

		wb = Workbook()
		ws = wb.active
		ws.append(["Designator", "Quantity", "Manufacturer Part Number", "Description"])
		ws.append(["J1", 1, "B2B-XH-A(LF)(SN)", "Connector"])
		ws.append(["J2", 2.0, "B3B-XH-A(LF)(SN)", "Connector 3p"])
		buf = io.BytesIO()
		wb.save(buf)
		result = p.parse("Altium", "bom.xlsx", buf.getvalue())
		self.assertEqual([(line.mpn, line.qty) for line in result.lines], [("B2B-XH-A(LF)(SN)", 1), ("B3B-XH-A(LF)(SN)", 2)])

	def test_missing_header(self):
		with self.assertRaises(p.BomParseError):
			p.parse("Altium", "x.csv", b"foo,bar\n1,2\n")

	def test_unsupported_extension(self):
		with self.assertRaises(p.BomParseError):
			p.parse("Altium", "x.pdf", b"")


class TestSolidWorks(unittest.TestCase):
	def test_indented_structure(self):
		result = p.parse("SolidWorks", "upright.csv", SOLIDWORKS_CSV.encode())
		self.assertEqual([line.part_number for line in result.lines], ["M-0042-A", "M-0050-A", ""])
		bracket, upright, spacer = result.lines
		self.assertEqual(bracket.material, "6061-T6 aluminum")
		self.assertEqual(bracket.vendor, "Sponsor machine shop")
		self.assertEqual(bracket.make_or_buy, p.MAKE)
		self.assertEqual(bracket.qty, 4)
		self.assertTrue(upright.is_assembly)
		self.assertEqual(upright.make_or_buy, p.MAKE)
		self.assertEqual([c.part_number for c in upright.children], ["M-0051-A", "6383K221"])
		self.assertEqual(upright.children[1].make_or_buy, p.BUY)
		self.assertEqual(upright.children[1].qty, 2)
		self.assertEqual(spacer.make_or_buy, p.MAKE)
		self.assertTrue(any("no part number" in w for w in result.warnings))

	def test_level_column(self):
		csv_text = "Level,Name,Title,Quantity\n0,ASM-1,Enclosure,1\n1,M-0001-A,Lid,1\n1,M-0002-A,Base,1\n2,91251A540,Screw,4\n"
		result = p.parse("3DEXPERIENCE", "enc.csv", csv_text.encode())
		self.assertEqual(len(result.lines), 1)
		root = result.lines[0]
		self.assertEqual(root.part_number, "ASM-1")
		self.assertEqual([c.part_number for c in root.children], ["M-0001-A", "M-0002-A"])
		self.assertEqual(root.children[1].children[0].qty, 4)

	def test_make_buy_words(self):
		self.assertEqual(p.parse_make_or_buy("Purchased"), p.BUY)
		self.assertEqual(p.parse_make_or_buy("make"), p.MAKE)
		self.assertEqual(p.parse_make_or_buy(""), "")


if __name__ == "__main__":
	unittest.main()
