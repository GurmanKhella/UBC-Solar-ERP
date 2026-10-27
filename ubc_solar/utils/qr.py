"""QR codes for bin labels, equipment tags and reorder cards.

Each QR code is a link to the ERP's /scan page, which opens the right screen on a
phone (take parts, recount a bin, check out equipment, request a reorder).
"""

from urllib.parse import urlencode

import frappe
import pyqrcode
from frappe.utils import get_url

SCAN_KEYS = {
	"Warehouse": "l",
	"Equipment": "e",
	"Reorder Point": "r",
	"Item": "i",
}


def base_url():
	configured = frappe.db.get_single_value("Solar Settings", "site_url")
	return (configured or get_url()).rstrip("/")


def scan_url(doctype, name):
	"""Link encoded in a label's QR code, e.g. https://erp/scan?l=E-A3 - UBCS"""
	key = SCAN_KEYS.get(doctype)
	if not key:
		frappe.throw(f"No scan link for {doctype}")
	return f"{base_url()}/scan?{urlencode({key: name})}"


def qr_svg(doctype, name, scale=4):
	"""An <img> tag with the QR code as a PNG data URI (works in print and PDF)."""
	data = pyqrcode.create(scan_url(doctype, name), error="M").png_as_base64_str(scale=int(scale))
	return f'<img class="solar-qr" src="data:image/png;base64,{data}" alt="QR code">'
