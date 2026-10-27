"""Daily sponsor jobs."""

import frappe
from frappe import _
from frappe.utils import nowdate


def remind_follow_ups():
	"""Ping each relationship owner about sponsors whose follow-up date has come."""
	from ubc_solar.solar_automation import notify

	due = frappe.get_all(
		"Sponsor",
		filters={"next_follow_up": ["<=", nowdate()], "status": ["not in", ["Declined", "Past"]]},
		fields=["name", "relationship_owner", "follow_up_note", "next_follow_up"],
	)
	for row in due:
		doc = frappe.get_doc("Sponsor", row.name)
		note = f" ({row.follow_up_note})" if row.follow_up_note else ""
		notify.send(
			"Sponsor follow-up",
			_("Follow-up due {0}{1}.").format(frappe.utils.format_date(row.next_follow_up), note),
			doc,
			users=[row.relationship_owner] if row.relationship_owner else [],
		)
