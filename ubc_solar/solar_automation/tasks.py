"""Daily automation jobs."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime

from ubc_solar.solar_automation import notify
from ubc_solar.team import scope


def escalate_waiting_approvals():
	"""Anything waiting for approval too long: @mention the division's Exec."""
	days = cint(frappe.db.get_single_value("Solar Settings", "escalate_after_days")) or 2
	cutoff = add_days(now_datetime(), -days)

	for name in frappe.get_all(
		"Material Request",
		filters={"workflow_state": "Pending Approval", "docstatus": 0, "modified": ["<", cutoff]},
		pluck="name",
	):
		doc = frappe.get_doc("Material Request", name)
		subteams = [doc.solar_subteam] if doc.solar_subteam else []
		notify.send(
			"Approval waiting too long",
			_("This purchase has been waiting for approval for over {0} days.").format(days),
			doc,
			users=scope.get_approvers(subteams, level="exec"),
			subteam=doc.solar_subteam,
		)

	from ubc_solar.cars.bom import approval_subteams

	for name in frappe.get_all(
		"BOM", filters={"workflow_state": "Ready for Review", "docstatus": 0, "modified": ["<", cutoff]}, pluck="name"
	):
		doc = frappe.get_doc("BOM", name)
		notify.send(
			"Approval waiting too long",
			_("This BOM has been waiting for review for over {0} days.").format(days),
			doc,
			users=scope.get_approvers(approval_subteams(doc), level="exec"),
			subteam=doc.solar_subteam,
		)
