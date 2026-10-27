"""Which built-in ERPNext roles each team position gets, and read-only access for
alumni on ERPNext's own doctypes."""

import frappe
from frappe.permissions import add_permission

# Everyone active on the team: open by default (create and edit parts, BOMs,
# stock moves, purchase requests, quality results).
WORKING_ROLES = ["Stock User", "Manufacturing User", "Item Manager", "Quality Manager"]

# Approvers also place orders, receive deliveries, add suppliers and recount stock.
APPROVER_ROLES = ["Purchase User", "Purchase Master Manager", "Stock Manager"]

POSITION_ROLES = {
	"Captain": ["Solar Captain", "Solar Member", *WORKING_ROLES, *APPROVER_ROLES],
	"Exec": ["Solar Exec", "Solar Member", *WORKING_ROLES, *APPROVER_ROLES],
	"Subteam Lead": ["Solar Lead", "Solar Member", *WORKING_ROLES, *APPROVER_ROLES],
	"Senior Design Member": ["Solar Senior Designer", "Solar Member", *WORKING_ROLES],
	"Member": ["Solar Member", *WORKING_ROLES],
	"Alumni": ["Solar Alumni"],
}

ADMIN_ROLES = ["System Manager", "Solar Admin"]

# Every role this app hands out; anything else on a user is left alone.
MANAGED_ROLES = sorted({role for roles in POSITION_ROLES.values() for role in roles} | set(ADMIN_ROLES))

# ERPNext doctypes alumni can read (they can read all of this app's doctypes
# except recruitment and attendance through the doctype permissions).
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


def apply():
	for doctype in ALUMNI_READ:
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": "Solar Alumni", "permlevel": 0}):
			add_permission(doctype, "Solar Alumni", 0, "read")
			frappe.db.set_value(
				"Custom DocPerm",
				{"parent": doctype, "role": "Solar Alumni", "permlevel": 0},
				{"report": 1, "print": 1, "export": 1},
			)
	frappe.clear_cache()
