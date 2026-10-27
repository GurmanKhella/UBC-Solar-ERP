"""Slack: posting notifications, linking members to Slack users, and the /erp
lookup command."""

import hashlib
import hmac
import time

import frappe
import requests
from werkzeug.wrappers import Response

from ubc_solar.solar_automation import log

API = "https://slack.com/api/"


def _token():
	settings = frappe.get_cached_doc("Solar Settings")
	if not settings.slack_enabled:
		return None
	return settings.get_password("slack_bot_token", raise_exception=False)


def api(method, payload):
	token = _token()
	if not token:
		raise frappe.ValidationError("Slack is not connected (Solar Settings > Slack).")
	response = requests.post(
		API + method,
		json=payload if method != "users.lookupByEmail" else None,
		params=payload if method == "users.lookupByEmail" else None,
		headers={"Authorization": f"Bearer {token}"},
		timeout=15,
	)
	response.raise_for_status()
	data = response.json()
	if not data.get("ok"):
		raise frappe.ValidationError(f"Slack {method} failed: {data.get('error')}")
	return data


def post_message(channel, text):
	return api("chat.postMessage", {"channel": channel, "text": text, "unfurl_links": False})


def post_job(channel, text, event=None, reference_doctype=None, reference_name=None):
	"""Background job: post one notification and log the result."""
	reference = frappe._dict(doctype=reference_doctype, name=reference_name) if reference_doctype else None
	with log.tracked("Slack", f"Post '{event}' to {channel}", reference):
		post_message(channel, text)


def link_member_to_slack(member):
	"""Fill in a member's Slack user ID from their email, so @mentions work."""
	if not _token():
		return
	doc = frappe.get_doc("Team Member", member)
	if doc.slack_user_id:
		return
	with log.tracked("Slack", f"Look up Slack user for {doc.email}", doc):
		try:
			data = api("users.lookupByEmail", {"email": doc.email})
		except frappe.ValidationError as e:
			if "users_not_found" in str(e):
				return  # their Slack uses a different email; set the ID by hand
			raise
		frappe.db.set_value("Team Member", member, "slack_user_id", data["user"]["id"])


# ------------------------------------------------------------------ /erp command
def verify_request(signing_secret):
	request = frappe.request
	timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
	signature = request.headers.get("X-Slack-Signature", "")
	if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 60 * 5:
		return False
	body = request.get_data(as_text=True)
	base = f"v0:{timestamp}:{body}".encode()
	expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, signature)


def _json(payload, status=200):
	return Response(frappe.as_json(payload), status=status, mimetype="application/json")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def command():
	"""Endpoint for the /erp slash command (Request URL in the Slack app:
	https://<erp>/api/method/ubc_solar.solar_automation.slack.command)."""
	settings = frappe.get_cached_doc("Solar Settings")
	secret = settings.get_password("slack_signing_secret", raise_exception=False) if settings.slack_enabled else None
	if not secret or not verify_request(secret):
		return _json({"text": "Request could not be verified."}, status=401)

	text = (frappe.form_dict.get("text") or "").strip()
	from ubc_solar.solar_automation.lookup import answer

	try:
		reply = answer(text, slack_user_id=frappe.form_dict.get("user_id"))
	except Exception:
		frappe.log_error(title="Slack /erp command failed")
		reply = "Something went wrong looking that up. The maintainers have the error in the ERP's Error Log."
	return _json({"response_type": "ephemeral", "text": reply})
