"""Automation health: every integration call is logged, and failures are posted to
the maintainers' Slack channel so nothing breaks quietly."""

from contextlib import contextmanager

import frappe


def write(integration, action, status, message="", reference=None):
	doc = frappe.get_doc(
		{
			"doctype": "Solar Automation Log",
			"integration": integration,
			"action": action,
			"status": status,
			"message": (message or "")[:50000],
			"reference_doctype": reference.doctype if reference else None,
			"reference_name": reference.name if reference else None,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


@contextmanager
def tracked(integration, action, reference=None, raise_exception=False):
	"""Log success or failure of a block; on failure alert maintainers instead of raising.

	Background jobs use this so one failed Drive call doesn't break saving a project.
	"""
	try:
		yield
	except Exception:
		message = frappe.get_traceback()
		frappe.db.rollback()
		write(integration, action, "Failed", message, reference)
		alert_maintainers(integration, action, reference)
		frappe.db.commit()
		if raise_exception:
			raise
	else:
		write(integration, action, "Success", "", reference)


def alert_maintainers(integration, action, reference=None):
	from ubc_solar.solar_automation import slack

	where = f" for {reference.doctype} {reference.name}" if reference else ""
	text = f":warning: Automation failed: {integration} — {action}{where}. See Solar Automation Log in the ERP."
	if integration == "Slack":
		return  # can't report a Slack failure through Slack; it's in the log
	try:
		settings = frappe.get_cached_doc("Solar Settings")
		if settings.slack_enabled and settings.maintainers_channel:
			slack.post_message(settings.maintainers_channel, text)
	except Exception:
		frappe.log_error(title="Could not alert maintainers")
