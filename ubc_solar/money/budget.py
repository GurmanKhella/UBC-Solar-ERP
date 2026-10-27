"""The fundraising-based budget.

Minimum target  the least the team needs: the total of every budget line
Raised          money actually received (sponsor money, grants, events)
Pledged         promised but not received; tracked separately so it isn't spent early
Committed       purchases approved but not yet ordered (ordering = paying)
Spent           purchases ordered and paid
Available       raised - spent - committed: what can still be approved
In-kind         value of donated parts and services; doesn't add to raised
"""

import frappe
from frappe.utils import flt


def _lines(budget):
	return frappe.get_all("Budget Line", filters={"budget": budget}, fields=["name", "amount", "line_name", "subteam", "division", "priority", "is_shop_supplies"])


def committed_by_line(lines):
	if not lines:
		return {}
	rows = frappe.db.sql(
		"""select mr.solar_budget_line as line,
			sum(greatest(mri.stock_qty - mri.ordered_qty, 0) * mri.rate / ifnull(nullif(mri.conversion_factor, 0), 1)) as amount
		from `tabMaterial Request Item` mri join `tabMaterial Request` mr on mr.name = mri.parent
		where mr.docstatus = 1 and mr.material_request_type = 'Purchase' and mr.status not in ('Stopped', 'Cancelled')
			and mr.solar_budget_line in %s
		group by mr.solar_budget_line""",
		(tuple(lines),),
		as_dict=True,
	)
	return {r.line: flt(r.amount) for r in rows}


def spent_by_line(lines):
	if not lines:
		return {}
	rows = frappe.db.sql(
		"""select solar_budget_line as line, sum(base_grand_total) as amount from `tabPurchase Order`
		where docstatus = 1 and solar_budget_line in %s group by solar_budget_line""",
		(tuple(lines),),
		as_dict=True,
	)
	return {r.line: flt(r.amount) for r in rows}


def _sum(doctype, field, filters):
	return sum(flt(v) for v in frappe.get_all(doctype, filters=filters, pluck=field))


def get_budget_summary(budget):
	lines = _lines(budget)
	names = [line.name for line in lines]
	committed = committed_by_line(names)
	spent = spent_by_line(names)

	raised = _sum("Funding Entry", "amount", {"budget": budget, "status": "Received"}) + _sum(
		"Sponsor Donation", "amount", {"budget": budget, "status": "Received", "donation_type": "Money"}
	)
	pledged = _sum("Funding Entry", "amount", {"budget": budget, "status": "Pledged"}) + _sum(
		"Sponsor Donation", "amount", {"budget": budget, "status": "Pledged", "donation_type": "Money"}
	)
	in_kind = _sum(
		"Sponsor Donation", "amount", {"budget": budget, "status": "Received", "donation_type": ["in", ["Parts", "Service"]]}
	)
	total_committed = sum(committed.values())
	total_spent = sum(spent.values())
	line_rows = []
	for line in lines:
		c, s = committed.get(line.name, 0.0), spent.get(line.name, 0.0)
		line_rows.append({**line, "committed": c, "spent": s, "remaining": flt(line.amount) - c - s})
	return {
		"budget": budget,
		"minimum_target": sum(flt(line.amount) for line in lines),
		"raised": raised,
		"pledged": pledged,
		"in_kind": in_kind,
		"committed": total_committed,
		"spent": total_spent,
		"available": raised - total_spent - total_committed,
		"lines": line_rows,
	}


def active_budget():
	return frappe.db.get_single_value("Solar Settings", "active_budget") or frappe.db.get_value(
		"Solar Budget", {"is_active": 1}, "name"
	)


@frappe.whitelist()
def summary(budget: str | None = None):
	budget = budget or active_budget()
	if not budget:
		return None
	frappe.has_permission("Solar Budget", "read", budget, throw=True)
	return get_budget_summary(budget)


def make_budget_for_car(car, make_active=False):
	"""A budget for a new car with one line per subteam (amounts filled in later)."""
	name = f"{car.car_title} Budget"
	if frappe.db.exists("Solar Budget", name):
		return name
	budget = frappe.get_doc(
		{"doctype": "Solar Budget", "budget_name": name, "car": car.name, "is_active": 1 if make_active else 0}
	)
	budget.insert(ignore_permissions=True)
	for subteam in frappe.get_all("Subteam", order_by="division asc, subteam_name asc", pluck="name"):
		make_line(name, subteam, subteam=subteam)
	make_line(name, "Shop Supplies", is_shop_supplies=1)
	make_line(name, "Competition and Travel", division="Business")
	make_line(name, "Operating Costs", division="Business", notes="Includes ERP hosting.")
	if make_active:
		frappe.get_doc("Solar Budget", name).save(ignore_permissions=True)  # applies the active flag
	return name


def make_line(budget, line_name, subteam=None, division=None, is_shop_supplies=0, notes=None):
	line = frappe.get_doc(
		{
			"doctype": "Budget Line",
			"budget": budget,
			"line_name": line_name,
			"subteam": subteam,
			"division": division,
			"amount": 0,
			"priority": "Must-have",
			"is_shop_supplies": is_shop_supplies,
			"notes": notes,
		}
	)
	line.insert(ignore_permissions=True)
	return line.name


# ------------------------------------------------------------------ number cards
def _card(key):
	budget = active_budget()
	value = get_budget_summary(budget)[key] if budget else 0
	return {"value": value, "fieldtype": "Currency"}


@frappe.whitelist()
def card_raised(filters=None):
	return _card("raised")


@frappe.whitelist()
def card_available(filters=None):
	return _card("available")


@frappe.whitelist()
def card_committed(filters=None):
	return _card("committed")


@frappe.whitelist()
def card_spent(filters=None):
	return _card("spent")


@frappe.whitelist()
def card_pledged(filters=None):
	return _card("pledged")


@frappe.whitelist()
def card_minimum_target(filters=None):
	return _card("minimum_target")
