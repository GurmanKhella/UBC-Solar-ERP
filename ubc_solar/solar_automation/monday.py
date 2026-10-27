"""Monday: when a project is created in the ERP its Monday item is created with the
same name and a link back; renames in the ERP are pushed to Monday."""

import json

import frappe
import requests
from frappe.utils import get_url_to_form

from ubc_solar.solar_automation import log

API = "https://api.monday.com/v2"


def settings():
	return frappe.get_cached_doc("Solar Settings")


def enabled():
	s = settings()
	return bool(s.monday_enabled and s.monday_board_id and s.get_password("monday_api_token", raise_exception=False))


def query(gql, variables=None):
	token = settings().get_password("monday_api_token")
	response = requests.post(
		API,
		json={"query": gql, "variables": variables or {}},
		headers={"Authorization": token, "API-Version": "2024-10", "Content-Type": "application/json"},
		timeout=20,
	)
	response.raise_for_status()
	data = response.json()
	if data.get("errors") or data.get("error_message"):
		raise frappe.ValidationError(f"Monday API error: {data.get('errors') or data.get('error_message')}")
	return data["data"]


def account_slug():
	cached = frappe.cache.get_value("ubc_solar:monday_slug")
	if cached:
		return cached
	slug = query("query { me { account { slug } } }")["me"]["account"]["slug"]
	frappe.cache.set_value("ubc_solar:monday_slug", slug, expires_in_sec=24 * 3600)
	return slug


CREATE_ITEM = """
mutation ($board: ID!, $group: String, $name: String!, $values: JSON) {
	create_item(board_id: $board, group_id: $group, item_name: $name, column_values: $values) { id }
}"""

CREATE_UPDATE = """
mutation ($item: ID!, $body: String!) { create_update(item_id: $item, body: $body) { id } }"""

RENAME = """
mutation ($board: ID!, $item: ID!, $value: String!) {
	change_simple_column_value(board_id: $board, item_id: $item, column_id: "name", value: $value) { id }
}"""


def create_project_item(project):
	if not enabled():
		return
	doc = frappe.get_doc("Solar Project", project)
	if doc.monday_item_id:
		return
	s = settings()
	erp_url = get_url_to_form("Solar Project", doc.name)
	with log.tracked("Monday", "Create project item", doc):
		values = {s.monday_link_column: {"url": erp_url, "text": "ERP"}} if s.monday_link_column else None
		item_id = query(
			CREATE_ITEM,
			{
				"board": str(s.monday_board_id),
				"group": s.monday_group_id or None,
				"name": doc.external_name,
				"values": json.dumps(values) if values else None,
			},
		)["create_item"]["id"]
		if not s.monday_link_column:
			query(CREATE_UPDATE, {"item": str(item_id), "body": f"ERP record: {erp_url}"})
		url = f"https://{account_slug()}.monday.com/boards/{s.monday_board_id}/pulses/{item_id}"
		doc.db_set({"monday_item_id": str(item_id), "monday_item_url": url})
		frappe.db.commit()


def rename_project_item(project):
	if not enabled():
		return
	doc = frappe.get_doc("Solar Project", project)
	if not doc.monday_item_id:
		return
	with log.tracked("Monday", "Rename project item", doc):
		query(RENAME, {"board": str(settings().monday_board_id), "item": doc.monday_item_id, "value": doc.external_name})
		frappe.db.commit()
