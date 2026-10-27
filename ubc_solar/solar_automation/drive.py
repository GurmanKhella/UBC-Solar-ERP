"""Google Drive: project docs and procedure docs are created from templates by
the ERP, with the same names and the links filled in both ways.

UBC Solar Shared Drive
  Projects/[Project name]/[Project name] Project Doc
  Manufacturing/[Subsystem name]/[Subsystem name] - [Procedure name] ([car])

Setup (once): a Google service account with access to the Shared Drive; its key
file is attached in Solar Settings > Google Drive.
"""

import json

import frappe
from frappe.utils import get_url_to_form

from ubc_solar.solar_automation import log

FOLDER = "application/vnd.google-apps.folder"
DOCUMENT = "application/vnd.google-apps.document"
SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"]
LINK_PLACEHOLDER = "{{ERP_LINK}}"


def settings():
	return frappe.get_cached_doc("Solar Settings")


def enabled():
	s = settings()
	return bool(s.drive_enabled and s.drive_service_account)


def services():
	"""(drive, docs) API clients authenticated as the service account."""
	from google.oauth2 import service_account
	from googleapiclient.discovery import build

	file_doc = frappe.get_doc("File", {"file_url": settings().drive_service_account})
	info = json.loads(file_doc.get_content())
	credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
	return (
		build("drive", "v3", credentials=credentials, cache_discovery=False),
		build("docs", "v1", credentials=credentials, cache_discovery=False),
	)


def _q(value):
	return value.replace("\\", "\\\\").replace("'", "\\'")


def find_or_create_folder(drive, name, parent):
	found = (
		drive.files()
		.list(
			q=f"name = '{_q(name)}' and '{parent}' in parents and mimeType = '{FOLDER}' and trashed = false",
			fields="files(id, name)",
			supportsAllDrives=True,
			includeItemsFromAllDrives=True,
			corpora="allDrives",
		)
		.execute()
		.get("files", [])
	)
	if found:
		return found[0]["id"]
	created = (
		drive.files()
		.create(body={"name": name, "mimeType": FOLDER, "parents": [parent]}, fields="id", supportsAllDrives=True)
		.execute()
	)
	return created["id"]


def make_doc(drive, docs, name, parent, template=None, erp_url=None):
	"""Copy the template (or start a blank doc) into `parent`; put the ERP link in it."""
	if template:
		created = (
			drive.files()
			.copy(fileId=template, body={"name": name, "parents": [parent]}, fields="id, webViewLink", supportsAllDrives=True)
			.execute()
		)
	else:
		created = (
			drive.files()
			.create(body={"name": name, "mimeType": DOCUMENT, "parents": [parent]}, fields="id, webViewLink", supportsAllDrives=True)
			.execute()
		)
	if erp_url:
		if template:
			request = {"replaceAllText": {"containsText": {"text": LINK_PLACEHOLDER, "matchCase": True}, "replaceText": erp_url}}
		else:
			request = {"insertText": {"location": {"index": 1}, "text": f"ERP record: {erp_url}\n"}}
		docs.documents().batchUpdate(documentId=created["id"], body={"requests": [request]}).execute()
	return created["id"], created.get("webViewLink") or f"https://docs.google.com/document/d/{created['id']}/edit"


def rename(drive, file_id, name):
	drive.files().update(fileId=file_id, body={"name": name}, supportsAllDrives=True).execute()


# ------------------------------------------------------------------ jobs
def create_project_doc(project):
	if not enabled():
		return
	doc = frappe.get_doc("Solar Project", project)
	if doc.drive_doc_id or not settings().drive_projects_folder:
		return
	with log.tracked("Google Drive", "Create project doc", doc):
		drive, docs = services()
		folder = find_or_create_folder(drive, doc.external_name, settings().drive_projects_folder)
		file_id, url = make_doc(
			drive,
			docs,
			f"{doc.external_name} Project Doc",
			folder,
			template=settings().drive_project_template,
			erp_url=get_url_to_form("Solar Project", doc.name),
		)
		doc.db_set({"drive_folder_id": folder, "drive_doc_id": file_id, "drive_doc_url": url})
		frappe.db.commit()


def rename_project_doc(project):
	if not enabled():
		return
	doc = frappe.get_doc("Solar Project", project)
	if not doc.drive_doc_id:
		return
	with log.tracked("Google Drive", "Rename project doc", doc):
		drive, _docs = services()
		if doc.drive_folder_id:
			rename(drive, doc.drive_folder_id, doc.external_name)
		rename(drive, doc.drive_doc_id, f"{doc.external_name} Project Doc")
		frappe.db.commit()


def procedure_name(stage):
	return f"{stage.subsystem} - {stage.stage_name} ({stage.car})"


def create_procedure_doc(stage):
	if not enabled():
		return
	doc = frappe.get_doc("Manufacturing Stage", stage)
	if doc.drive_doc_id or not settings().drive_manufacturing_folder:
		return
	with log.tracked("Google Drive", "Create procedure doc", doc):
		drive, docs = services()
		folder = find_or_create_folder(drive, doc.subsystem, settings().drive_manufacturing_folder)
		file_id, url = make_doc(
			drive,
			docs,
			procedure_name(doc),
			folder,
			template=settings().drive_procedure_template,
			erp_url=get_url_to_form("Manufacturing Stage", doc.name),
		)
		doc.db_set({"drive_doc_id": file_id, "procedure_doc_url": url})
		frappe.db.commit()


def rename_procedure_doc(stage):
	if not enabled():
		return
	doc = frappe.get_doc("Manufacturing Stage", stage)
	if not doc.drive_doc_id:
		return
	with log.tracked("Google Drive", "Rename procedure doc", doc):
		drive, _docs = services()
		rename(drive, doc.drive_doc_id, procedure_name(doc))
		frappe.db.commit()
