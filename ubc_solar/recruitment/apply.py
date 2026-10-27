"""The public application form (/apply).

A small custom page rather than a generic Web Form so that only published
openings are listed and résumés and challenge files are stored privately.
"""

import os

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils.file_manager import MaxFileSizeReachedError

MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".zip", ".png", ".jpg", ".jpeg", ".txt", ".md"}


def published_openings():
	return frappe.get_all(
		"Recruitment Opening",
		filters={"status": "Published"},
		fields=["name", "opening_title", "cycle", "subteam", "description", "challenge_instructions"],
		order_by="cycle desc, opening_title asc",
	)


def _save_file(applicant, fieldname, upload):
	if not upload or not upload.filename:
		return None
	extension = os.path.splitext(upload.filename)[1].lower()
	if extension not in ALLOWED_EXTENSIONS:
		frappe.throw(_("{0}: please upload a PDF, Word document, ZIP or image.").format(upload.filename))
	content = upload.stream.read()
	if len(content) > MAX_FILE_BYTES:
		raise MaxFileSizeReachedError(_("{0} is larger than 10 MB.").format(upload.filename))
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": upload.filename,
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Applicant",
			"attached_to_name": applicant.name,
			"attached_to_field": fieldname,
		}
	)
	file_doc.insert(ignore_permissions=True)
	return file_doc.file_url


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def submit():
	form = frappe.form_dict
	required = {"full_name": _("your name"), "email": _("your email"), "opening": _("the opening")}
	for key, label in required.items():
		if not (form.get(key) or "").strip():
			frappe.throw(_("Please enter {0}.").format(label))
	if not form.get("consent"):
		frappe.throw(_("Please confirm you've read how application data is kept."))

	applicant = frappe.get_doc(
		{
			"doctype": "Applicant",
			"full_name": form.full_name.strip(),
			"email": form.email.strip(),
			"phone": (form.get("phone") or "").strip(),
			"program_and_year": (form.get("program_and_year") or "").strip(),
			"opening": form.opening,
			"challenge_link": (form.get("challenge_link") or "").strip(),
			"why_solar": (form.get("why_solar") or "").strip(),
			"consent": 1,
			"status": "Applied",
		}
	)
	applicant.insert(ignore_permissions=True)
	files = frappe.request.files if frappe.request else {}
	values = {}
	for fieldname in ("resume", "challenge_submission"):
		url = _save_file(applicant, fieldname, files.get(fieldname))
		if url:
			values[fieldname] = url
	if values:
		applicant.db_set(values)
	return {"name": applicant.name}
