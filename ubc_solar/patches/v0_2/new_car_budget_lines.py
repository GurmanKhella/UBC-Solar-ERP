"""Seed Solar Settings > New car budget lines (previously fixed in code)."""

import frappe


def execute():
	from ubc_solar.money.budget import DEFAULT_TEMPLATE

	settings = frappe.get_single("Solar Settings")
	if settings.new_car_budget_lines:
		return
	for row in DEFAULT_TEMPLATE:
		settings.append("new_car_budget_lines", row)
	settings.add_line_per_subteam = 1
	settings.flags.ignore_permissions = True
	settings.save()
