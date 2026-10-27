"""BOM review: Draft -> Ready for Review -> Approved / Sent Back.

Approving a BOM approves the purchases for its "buy" lines: a purchase request
is created already approved, owned by the approver, who orders it.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from ubc_solar.cars.utils import assert_car_editable, subsystem_subteams
from ubc_solar.solar_automation import notify
from ubc_solar.team import scope


def validate(doc, method=None):
	set_context(doc)
	assert_car_editable(doc.solar_car, doc)
	if not doc.solar_bom_owner:
		doc.solar_bom_owner = (
			frappe.db.get_value("Solar Project", doc.solar_project, "project_owner") if doc.solar_project else None
		) or frappe.session.user
	if doc.has_value_changed("workflow_state") and doc.workflow_state == "Ready for Review":
		warn_about_duplicate_homes(doc)


def set_context(doc):
	"""Fill in the car, kind and subteam from what the BOM is for."""
	vehicle_of = frappe.db.get_value("Car", {"vehicle_item": doc.item}, "name")
	if vehicle_of:
		doc.solar_bom_kind = "Vehicle"
		doc.solar_car = vehicle_of
		doc.solar_project = None
		doc.solar_subteam = None
	elif doc.solar_manufacturing_stage:
		doc.solar_bom_kind = "Manufacturing Stage"
		doc.solar_car = frappe.db.get_value("Manufacturing Stage", doc.solar_manufacturing_stage, "car")
		doc.solar_project = None
		doc.solar_subteam = None
	else:
		if not doc.solar_project:
			doc.solar_project = frappe.db.get_value("Item", doc.item, "solar_project")
		doc.solar_bom_kind = "Project"
		if doc.solar_project:
			project = frappe.db.get_value("Solar Project", doc.solar_project, ["car", "subteam"], as_dict=True)
			doc.solar_car, doc.solar_subteam = project.car, project.subteam


def approval_subteams(doc):
	"""Whose Leads can approve this BOM."""
	if doc.solar_bom_kind == "Vehicle":
		return []  # the whole car: Execs and the Captain
	if doc.solar_bom_kind == "Manufacturing Stage":
		subsystem = frappe.db.get_value("Manufacturing Stage", doc.solar_manufacturing_stage, "subsystem")
		return subsystem_subteams(subsystem)
	return [doc.solar_subteam] if doc.solar_subteam else []


def before_submit(doc, method=None):
	subteams = approval_subteams(doc)
	if not scope.can_approve(subteams):
		who = ", ".join(subteams) if subteams else _("the whole car")
		frappe.throw(
			_("Only a Lead of {0}, their division's Exec, or the Captain can approve this BOM.").format(who),
			frappe.PermissionError,
		)
	doc.solar_approved_by = frappe.session.user
	doc.solar_approved_on = now_datetime()


def on_submit(doc, method=None):
	from ubc_solar.money.purchasing import create_purchase_from_bom

	request = create_purchase_from_bom(doc)
	if request:
		doc.db_set("solar_purchase_request", request)
	notify.send(
		"BOM reviewed",
		_("BOM approved.") + (_(" Its purchases are approved too.") if request else ""),
		doc,
		users=bom_owners(doc),
		subteam=doc.solar_subteam,
	)


def on_update(doc, method=None):
	if not doc.has_value_changed("workflow_state"):
		return
	if doc.workflow_state == "Ready for Review":
		notify.send(
			"BOM ready for review",
			_("BOM ready for review."),
			doc,
			users=scope.get_approvers(approval_subteams(doc)),
			subteam=doc.solar_subteam,
		)
	elif doc.workflow_state == "Sent Back":
		notify.send(
			"BOM reviewed",
			_("BOM sent back, see comments."),
			doc,
			users=bom_owners(doc),
			subteam=doc.solar_subteam,
		)


def before_cancel(doc, method=None):
	assert_car_editable(doc.solar_car, doc)


def bom_owners(doc):
	users = [doc.solar_bom_owner]
	if doc.solar_project:
		project = frappe.get_doc("Solar Project", doc.solar_project)
		users += project.owners()
	return list(dict.fromkeys(u for u in users if u))


def warn_about_duplicate_homes(doc):
	"""One home per item: a part the team makes should be on only one active BOM per car."""
	if not doc.solar_car:
		return
	made = [row.item_code for row in doc.items if frappe.db.get_value("Item", row.item_code, "solar_make_or_buy") == "Make"]
	if not made:
		return
	others = frappe.db.sql(
		"""select distinct bi.item_code, b.name from `tabBOM Item` bi join `tabBOM` b on b.name = bi.parent
		where b.docstatus = 1 and b.is_active = 1 and b.is_default = 1 and b.solar_car = %s
		and b.item != %s and bi.item_code in %s""",
		(doc.solar_car, doc.item, tuple(made)),
		as_dict=True,
	)
	if others:
		lines = ", ".join(f"{r.item_code} ({r.name})" for r in others)
		frappe.msgprint(
			_("These parts are already on another BOM for this car, so their cost may be counted twice: {0}").format(lines),
			title=_("One home per item"),
			indicator="orange",
		)


@frappe.whitelist()
def make_version_active(bom: str):
	"""Revert: make an earlier approved version the active, default one."""
	doc = frappe.get_doc("BOM", bom)
	doc.check_permission("write")
	if doc.docstatus != 1:
		frappe.throw(_("Only approved BOM versions can be made active."))
	assert_car_editable(doc.solar_car, doc)
	doc.is_active = 1
	doc.is_default = 1
	doc.save()
	return doc.name
