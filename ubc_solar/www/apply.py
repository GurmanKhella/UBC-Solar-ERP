from frappe import _

from ubc_solar.recruitment.apply import published_openings

no_cache = 1


def get_context(context):
	context.title = _("Apply to UBC Solar")
	context.no_breadcrumbs = True
	context.openings = published_openings()
	return context
