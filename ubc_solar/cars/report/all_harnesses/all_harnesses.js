// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.query_reports["All Harnesses"] = {
	filters: [
		{ fieldname: "car", label: __("Car"), fieldtype: "Link", options: "Car" },
		{ fieldname: "project", label: __("Touching Project"), fieldtype: "Link", options: "Solar Project" },
		{ fieldname: "harness_category", label: __("Category"), fieldtype: "Link", options: "Harness Category" },
	],
};
