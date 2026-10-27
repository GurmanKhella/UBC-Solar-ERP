"""Wiki.js: the auto-updated "Current car" page and the end-of-car snapshot.

The page's main section shows the car being designed or built (subsystems,
projects, BOM status, budget spent per subsystem); below it, older cars still
active, with their repairs and next competition. Each car's status decides
which section it appears in, so the page switches over by itself.
"""

import re

import frappe
import requests
from frappe.utils import flt, fmt_money, get_url_to_form, nowdate

from ubc_solar.solar_automation import log


def settings():
	return frappe.get_cached_doc("Solar Settings")


def enabled():
	s = settings()
	return bool(s.wiki_enabled and s.wiki_url and s.get_password("wiki_api_key", raise_exception=False))


def money(value):
	return fmt_money(flt(value), currency="CAD")


def link(doctype, name, label=None):
	return f"[{(label or name).replace(']', '')}]({get_url_to_form(doctype, name)})"


# ------------------------------------------------------------------ content
def spent_by_subsystem(car):
	rows = frappe.db.sql(
		"""select sp.subsystem, sum(po.base_grand_total) as spent
		from `tabPurchase Order` po
		join `tabMaterial Request` mr on mr.name = po.solar_material_request
		join `tabSolar Project` sp on sp.name = mr.solar_project
		where po.docstatus = 1 and sp.car = %s
		group by sp.subsystem""",
		car,
		as_dict=True,
	)
	return {r.subsystem: flt(r.spent) for r in rows}


def project_bom_status(project):
	if frappe.db.exists("BOM", {"solar_project": project, "docstatus": 1, "is_active": 1}):
		return "Approved"
	state = frappe.db.get_value(
		"BOM", {"solar_project": project, "docstatus": 0}, "workflow_state", order_by="modified desc"
	)
	return state or "No BOM yet"


def car_section(car):
	lines = [f"## {link('Car', car.name, car.car_title)} · {car.status}", ""]
	if car.budget:
		from ubc_solar.money.budget import get_budget_summary

		s = get_budget_summary(car.budget)
		lines += [
			f"**Budget:** raised {money(s['raised'])} of {money(s['minimum_target'])} minimum target · "
			f"spent {money(s['spent'])} · available {money(s['available'])}",
			"",
		]
	spent = spent_by_subsystem(car.name)
	for subsystem in frappe.get_all("Subsystem", filters={"enabled": 1}, order_by="sort_order asc", pluck="name"):
		projects = frappe.get_all(
			"Solar Project",
			filters={"car": car.name, "subsystem": subsystem, "status": ["!=", "Cancelled"]},
			fields=["name", "project_name", "status", "project_owner"],
			order_by="project_name asc",
		)
		lines.append(f"### {subsystem} · spent {money(spent.get(subsystem, 0))}")
		if not projects:
			lines += ["_No projects yet._", ""]
			continue
		lines += ["| Project | Status | BOM | Owner |", "| --- | --- | --- | --- |"]
		for p in projects:
			lines.append(
				f"| {link('Solar Project', p.name, p.project_name)} | {p.status} | {project_bom_status(p.name)} | "
				f"{frappe.utils.get_fullname(p.project_owner)} |"
			)
		lines.append("")
	return lines


def older_car_section(car):
	lines = [f"### {link('Car', car.name, car.car_title)}"]
	repairs = frappe.get_all(
		"Car Repair",
		filters={"car": car.name, "status": ["!=", "Fixed"]},
		fields=["name", "title", "status"],
		order_by="creation desc",
	)
	if repairs:
		lines += [f"- Repair: {link('Car Repair', r.name, r.title)} ({r.status})" for r in repairs]
	else:
		lines.append("- No open repairs")
	next_comp = frappe.get_all(
		"Competition",
		filters={"car": car.name, "status": ["!=", "Done"], "start_date": [">=", nowdate()]},
		fields=["name", "start_date"],
		order_by="start_date asc",
		limit=1,
	)
	if next_comp:
		lines.append(f"- Next competition: {link('Competition', next_comp[0].name)} ({frappe.utils.format_date(next_comp[0].start_date)})")
	lines.append("")
	return lines


def current_car_markdown():
	main = frappe.get_all(
		"Car", filters={"status": ["in", ["In Design", "Building"]]}, fields=["*"], order_by="car_version desc"
	)
	active = frappe.get_all("Car", filters={"status": "Active"}, fields=["*"], order_by="car_version desc")
	lines = [
		"# Current car",
		"",
		f"_Updated automatically from the ERP on {frappe.utils.format_datetime(frappe.utils.now_datetime())}. "
		"Edit the records in the ERP, not this page._",
		"",
	]
	if not main and not active:
		lines.append("No car is in design, being built, or active.")
	for car in main:
		lines += car_section(car)
	if active:
		lines += ["## Older cars still active", ""]
		for car in active:
			lines += older_car_section(car)
	return "\n".join(lines)


def snapshot_markdown(car_name):
	car = frappe.get_doc("Car", car_name)
	lines = [f"# {car.car_title}: end-of-car snapshot", "", f"_Published from the ERP when the car was retired ({frappe.utils.format_date(car.retired_on or nowdate())})._", ""]
	vehicle_bom = frappe.db.get_value("Item", car.vehicle_item, "default_bom") if car.vehicle_item else None
	if vehicle_bom:
		lines += [f"**Vehicle BOM:** {vehicle_bom} · total cost {money(frappe.db.get_value('BOM', vehicle_bom, 'total_cost'))}", ""]
	if car.budget:
		from ubc_solar.money.budget import get_budget_summary

		s = get_budget_summary(car.budget)
		lines += [f"**Budget:** raised {money(s['raised'])}, spent {money(s['spent'])}, minimum target {money(s['minimum_target'])}", ""]

	lines += ["## Final BOMs", "", "| Project | Subsystem | BOM | Cost |", "| --- | --- | --- | --- |"]
	for p in frappe.get_all("Solar Project", filters={"car": car.name}, fields=["name", "project_name", "subsystem", "part"], order_by="subsystem, project_name"):
		bom = frappe.db.get_value("Item", p.part, "default_bom") if p.part else None
		cost = money(frappe.db.get_value("BOM", bom, "total_cost")) if bom else "-"
		lines.append(f"| {p.project_name} | {p.subsystem or '-'} | {bom or '-'} | {cost} |")

	lines += ["", "## Manufacturing packages", ""]
	for pkg in frappe.get_all("Manufacturing Package", filters={"car": car.name}, fields=["name", "subsystem"], order_by="subsystem"):
		lines.append(f"### {pkg.subsystem}")
		stages = frappe.get_all(
			"Manufacturing Stage",
			filters={"manufacturing_package": pkg.name},
			fields=["stage_name", "manufacturing_bom", "total_minutes", "procedure_doc_url"],
			order_by="sequence asc",
		)
		for st in stages:
			doc_link = f" · [procedure]({st.procedure_doc_url})" if st.procedure_doc_url else ""
			lines.append(f"- {st.stage_name} (BOM {st.manufacturing_bom or '-'}, {st.total_minutes or 0} min){doc_link}")
		if not stages:
			lines.append("- No stages recorded")
		lines.append("")

	lines += ["## Repair history", ""]
	repairs = frappe.get_all(
		"Car Repair",
		filters={"car": car.name},
		fields=["title", "solar_subsystem", "solar_project", "status", "fixed_on", "what_changed", "why"],
		order_by="creation asc",
	)
	for r in repairs:
		where = " / ".join(x for x in (r.solar_subsystem, r.solar_project) if x)
		lines.append(f"- **{r.title}** ({where or 'car'}, {r.status}{', fixed ' + str(r.fixed_on) if r.fixed_on else ''}): {r.what_changed or ''} {('Why: ' + r.why) if r.why else ''}".rstrip())
	if not repairs:
		lines.append("- No repairs recorded")
	return "\n".join(lines)


# ------------------------------------------------------------------ Wiki.js API
def graphql(gql, variables):
	s = settings()
	response = requests.post(
		s.wiki_url.rstrip("/") + "/graphql",
		json={"query": gql, "variables": variables},
		headers={"Authorization": f"Bearer {s.get_password('wiki_api_key')}"},
		timeout=30,
	)
	response.raise_for_status()
	data = response.json()
	if data.get("errors"):
		raise frappe.ValidationError(f"Wiki.js error: {data['errors']}")
	return data["data"]


FIND = """query ($path: String!, $locale: String!) { pages { singleByPath(path: $path, locale: $locale) { id } } }"""

CREATE = """mutation ($content: String!, $description: String!, $path: String!, $title: String!, $locale: String!) {
	pages { create(content: $content, description: $description, editor: "markdown", isPublished: true, isPrivate: false,
		locale: $locale, path: $path, tags: ["erp"], title: $title) { responseResult { succeeded message } page { id } } } }"""

UPDATE = """mutation ($id: Int!, $content: String!) {
	pages { update(id: $id, content: $content, isPublished: true) { responseResult { succeeded message } } } }"""


def find_page(path):
	try:
		page = graphql(FIND, {"path": path, "locale": settings().wiki_locale or "en"})["pages"]["singleByPath"]
	except frappe.ValidationError as e:
		message = str(e).lower()
		# Wiki.js 2.x answers "This page does not exist." (PageNotFound) for a new path.
		if "does not exist" in message or "pagenotfound" in message or "not found" in message:
			return None
		raise
	return page["id"] if page else None


def save_page(path, title, content, description):
	page_id = find_page(path)
	if page_id:
		result = graphql(UPDATE, {"id": int(page_id), "content": content})["pages"]["update"]["responseResult"]
	else:
		result = graphql(
			CREATE,
			{"content": content, "description": description, "path": path, "title": title, "locale": settings().wiki_locale or "en"},
		)["pages"]["create"]["responseResult"]
	if not result.get("succeeded"):
		raise frappe.ValidationError(f"Wiki.js refused the page: {result.get('message')}")
	return f"{settings().wiki_url.rstrip('/')}/{path}"


def refresh_current_car_page():
	"""Hourly: rewrite the Current car page."""
	if not enabled():
		return
	with log.tracked("Wiki", "Refresh current car page"):
		save_page(settings().wiki_current_car_path or "current-car", "Current car", current_car_markdown(), "Auto-updated from the ERP")
		frappe.db.commit()


def slug(text):
	return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def publish_car_snapshot(car):
	if not enabled():
		return
	doc = frappe.get_doc("Car", car)
	with log.tracked("Wiki", "Publish end-of-car snapshot", doc):
		path = f"{(settings().wiki_snapshot_prefix or 'cars').strip('/')}/{slug(doc.car_title)}"
		url = save_page(path, f"{doc.car_title} (end-of-car snapshot)", snapshot_markdown(car), "Final BOMs, costs, manufacturing and repairs")
		doc.db_set("wiki_snapshot_url", url)
		frappe.db.commit()
	refresh_current_car_page()
