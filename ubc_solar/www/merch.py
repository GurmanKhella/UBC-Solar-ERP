from frappe import _

from ubc_solar.merch import store

no_cache = 1


def get_context(context):
	settings = store.settings()
	member = store.team_member_for_session()
	context.title = _("UBC Solar Merch")
	context.no_breadcrumbs = True
	context.store_open = settings.store_open
	context.intro = settings.store_intro
	context.is_team = bool(member)
	context.products = store.catalog(context.is_team) if settings.store_open else []
	context.buyer = {"name": "", "email": ""}
	if member:
		import frappe

		row = frappe.db.get_value("Team Member", member, ["full_name", "email"], as_dict=True)
		context.buyer = {"name": row.full_name or "", "email": row.email or ""}
	return context
