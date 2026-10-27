"""Extra rights on ERPNext's own doctypes, added once.

They are Custom DocPerm rows, so the Role Permissions Manager shows and changes
them like any other permission. They're only added when missing and never reset,
so changes made in the ERP stay.
"""

import frappe
from frappe.permissions import add_permission

# ERPNext doctypes alumni can read (this app's own doctypes give alumni read access
# in their definitions, except recruitment and attendance).
ALUMNI_READ = [
	"Item",
	"Item Group",
	"BOM",
	"Warehouse",
	"Stock Entry",
	"Stock Reconciliation",
	"Material Request",
	"Purchase Order",
	"Purchase Receipt",
	"Batch",
	"Quality Inspection",
	"Quality Inspection Template",
	"Supplier",
	"UOM",
]

READ = {"read": 1, "report": 1, "print": 1, "export": 1}

GRANTS = [
	# Any member can recount a bin (normally Stock Manager only).
	("Stock Reconciliation", "Solar Member", {"read": 1, "write": 1, "create": 1, "submit": 1, "report": 1, "print": 1}),
	# Restrict access to anything: a User Permission limits a user to specific records.
	("User Permission", "Solar Access Manager", {"read": 1, "write": 1, "create": 1, "delete": 1}),
	*[(doctype, "Solar Alumni", READ) for doctype in ALUMNI_READ],
]


def grant(doctype, role, rights):
	"""Add a permission row if the role has none on this doctype yet."""
	if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		return False
	add_permission(doctype, role, 0, "read")
	frappe.db.set_value("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, rights)
	return True


def apply():
	changed = False
	for doctype, role, rights in GRANTS:
		changed = grant(doctype, role, rights) or changed
	if changed:
		frappe.clear_cache()
