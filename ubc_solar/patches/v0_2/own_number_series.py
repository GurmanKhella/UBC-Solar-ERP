"""Each numbered record type now has its own counter (PRJ-00001, PRJ-00002, ...) instead
of one counter shared by all of them. Start each counter after the highest number
already used, so new names never clash with existing ones."""

import re

import frappe


def execute():
	modules = frappe.get_all("Module Def", filters={"app_name": "ubc_solar"}, pluck="name")
	for doctype, autoname in frappe.get_all(
		"DocType", filters={"module": ["in", modules], "autoname": ["like", "%.#%"]}, fields=["name", "autoname"], as_list=True
	):
		prefix = autoname.split(".")[0]
		pattern = re.compile(rf"^({re.escape(prefix)}(?:\d{{4}}-)?)(\d+)$")
		highest = {}
		for name in frappe.get_all(doctype, pluck="name"):
			match = pattern.match(name)
			if match:
				key, number = match.group(1), int(match.group(2))
				highest[key] = max(highest.get(key, 0), number)
		for key, number in highest.items():
			current = frappe.db.get_value("Series", key, "current", order_by=None)
			if current is None:
				frappe.db.sql("insert into `tabSeries` (`name`, `current`) values (%s, %s)", (key, number))
			elif int(current) < number:
				frappe.db.sql("update `tabSeries` set `current` = %s where `name` = %s", (number, key))
