"""One place that sends notifications.

Every notification is posted in a Slack channel with @mentions (never as a DM)
and also shows in the ERP's notification bell for the people mentioned.
"""

import frappe
from frappe.utils import get_url_to_form

from ubc_solar.team import scope


def channel_for(event, subteam=None):
	settings = frappe.get_cached_doc("Solar Settings")
	if subteam:
		channel = frappe.get_cached_value("Subteam", subteam, "slack_channel")
		if channel:
			return channel
	for route in settings.slack_routes:
		if route.event == event and route.channel:
			return route.channel
	return settings.default_channel or "#general"


def send(event, text, doc=None, users=None, subteam=None):
	"""Notify `users` about `doc`.

	event: one of the Solar Slack Route events (decides the channel).
	text: the message, without mentions or link.
	"""
	users = [u for u in dict.fromkeys(users or []) if u and u not in ("Administrator", "Guest")]
	link = get_url_to_form(doc.doctype, doc.name) if doc else None
	title = (doc.get_title() if doc else "") or (doc.name if doc else "")

	if users:
		_bell(users, text, doc)

	settings = frappe.get_cached_doc("Solar Settings")
	if not settings.slack_enabled:
		return
	mentions = scope.slack_mentions(users)
	message = " ".join(p for p in (mentions, text) if p)
	if link:
		message += f" <{link}|{frappe.utils.escape_html(title)}>"
	frappe.enqueue(
		"ubc_solar.solar_automation.slack.post_job",
		channel=channel_for(event, subteam),
		text=message,
		event=event,
		reference_doctype=doc.doctype if doc else None,
		reference_name=doc.name if doc else None,
		enqueue_after_commit=True,
		queue="short",
	)


def _bell(users, text, doc):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"subject": frappe.utils.escape_html(text),
			"document_type": doc.doctype if doc else None,
			"document_name": doc.name if doc else None,
			"from_user": frappe.session.user,
		},
	)
