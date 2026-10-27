"""Answers for the /erp Slack command, so people can ask the ERP quick questions
without opening it.

/erp part M5 bolt          stock and shelf location
/erp bom BMS               that BOM's status
/erp budget electrical     remaining budget (subteam, division, or all)
/erp equipment scope       where it is and whether it works
/erp project BMS           project status, owner and links
"""

import frappe
from frappe.utils import flt, fmt_money, get_url_to_form

from ubc_solar.money.budget import active_budget, get_budget_summary
from ubc_solar.solar_inventory.stock import stock_by_location

HELP = (
	"*Ask the ERP:*\n"
	"`/erp part M5 bolt` — stock and shelf location\n"
	"`/erp bom BMS` — a BOM's status\n"
	"`/erp budget electrical` — remaining budget (a subteam, a division, or `all`)\n"
	"`/erp equipment oscilloscope` — where it is and whether it works\n"
	"`/erp project BMS` — project status and links"
)


def money(value):
	return fmt_money(flt(value), currency="CAD")


def url(doctype, name, label):
	return f"<{get_url_to_form(doctype, name)}|{label}>"


def like(text):
	return f"%{text.strip()}%"


def answer(text, slack_user_id=None):
	command, _sep, rest = (text or "").strip().partition(" ")
	command = command.lower()
	rest = rest.strip()
	handlers = {
		"part": part,
		"parts": part,
		"bom": bom,
		"budget": budget,
		"equipment": equipment,
		"tool": equipment,
		"project": project,
	}
	if command not in handlers:
		return HELP
	if not rest and command != "budget":
		return f"What should I look up? e.g. `/erp {command} ...`\n\n{HELP}"
	return handlers[command](rest)


def part(q):
	items = frappe.get_all(
		"Item",
		or_filters={"item_code": ["like", like(q)], "item_name": ["like", like(q)], "solar_mpn": ["like", like(q)]},
		fields=["name", "item_name", "stock_uom", "is_stock_item"],
		filters={"disabled": 0},
		limit=5,
		order_by="modified desc",
	)
	if not items:
		return f"No parts match *{q}*."
	lines = []
	for item in items:
		if not item.is_stock_item:
			lines.append(f"• {url('Item', item.name, item.item_name)} — shop consumable, not counted (reordered with the two-bin cards)")
			continue
		locations = stock_by_location(item.name)
		if locations:
			where = ", ".join(f"{flt(q):g} in {w}" for w, q in locations[:4])
			total = sum(qty for _w, qty in locations)
			lines.append(f"• {url('Item', item.name, item.item_name)} (`{item.name}`): {total:g} {item.stock_uom} — {where}")
		else:
			lines.append(f"• {url('Item', item.name, item.item_name)} (`{item.name}`): none in stock")
	return "\n".join(lines)


def bom(q):
	projects = frappe.get_all("Solar Project", filters={"project_name": ["like", like(q)]}, pluck="name", limit=10)
	or_filters = {"name": ["like", like(q)], "item_name": ["like", like(q)]}
	if projects:
		or_filters["solar_project"] = ["in", projects]
	boms = frappe.get_all(
		"BOM",
		or_filters=or_filters,
		filters={"docstatus": ["<", 2]},
		fields=["name", "item_name", "workflow_state", "is_default", "is_active", "solar_approved_by", "modified"],
		order_by="modified desc",
		limit=5,
	)
	if not boms:
		return f"No BOMs match *{q}*."
	lines = []
	for b in boms:
		flag = " (active version)" if b.is_default and b.is_active and b.workflow_state == "Approved" else ""
		by = f", approved by {frappe.utils.get_fullname(b.solar_approved_by)}" if b.solar_approved_by else ""
		lines.append(f"• {url('BOM', b.name, b.name)} — {b.item_name}: *{b.workflow_state or 'Draft'}*{flag}{by}")
	return "\n".join(lines)


def budget(q):
	name = active_budget()
	if not name:
		return "There's no active budget yet."
	s = get_budget_summary(name)
	q = (q or "").strip().lower()
	if not q or q == "all":
		return (
			f"*{name}*: raised {money(s['raised'])} of {money(s['minimum_target'])} minimum target "
			f"(pledged {money(s['pledged'])}). Spent {money(s['spent'])}, committed {money(s['committed'])}, "
			f"*available {money(s['available'])}*."
		)
	lines = [
		line for line in s["lines"]
		if q in (line.get("subteam") or "").lower() or q in (line.get("division") or "").lower() or q in (line.get("line_name") or "").lower()
	]
	if not lines:
		return f"No budget line matches *{q}*. Try a subteam, a division, or `all`."
	total = {k: sum(flt(line[k]) for line in lines) for k in ("amount", "spent", "committed", "remaining")}
	detail = "\n".join(f"• {line['line_name']}: {money(line['remaining'])} left of {money(line['amount'])}" for line in lines)
	return (
		f"*{q.title()}*: {money(total['remaining'])} left of {money(total['amount'])} "
		f"(spent {money(total['spent'])}, committed {money(total['committed'])}).\n{detail}\n"
		f"Team-wide available (raised − spent − committed): {money(s['available'])}"
	)


def equipment(q):
	rows = frappe.get_all(
		"Equipment",
		filters={"equipment_name": ["like", like(q)]},
		fields=["name", "equipment_name", "condition", "location", "group_location", "checked_out_to"],
		limit=5,
	)
	if not rows:
		return f"No equipment matches *{q}*."
	lines = []
	for r in rows:
		where = r.group_location or r.location or "no home location set"
		out = f", checked out to {frappe.utils.get_fullname(r.checked_out_to)}" if r.checked_out_to else ""
		lines.append(f"• {url('Equipment', r.name, r.equipment_name)}: {r.condition}, {where}{out}")
	return "\n".join(lines)


def project(q):
	rows = frappe.get_all(
		"Solar Project",
		filters={"project_name": ["like", like(q)]},
		fields=["name", "project_name", "car", "subsystem", "status", "project_owner", "drive_doc_url", "monday_item_url"],
		order_by="modified desc",
		limit=5,
	)
	if not rows:
		return f"No projects match *{q}*."
	lines = []
	for r in rows:
		links = " · ".join(
			x for x in (f"<{r.drive_doc_url}|doc>" if r.drive_doc_url else "", f"<{r.monday_item_url}|Monday>" if r.monday_item_url else "") if x
		)
		lines.append(
			f"• {url('Solar Project', r.name, r.project_name)} ({r.car}, {r.subsystem or 'no subsystem'}): *{r.status}*, "
			f"owner {frappe.utils.get_fullname(r.project_owner)}{(' · ' + links) if links else ''}"
		)
	return "\n".join(lines)
