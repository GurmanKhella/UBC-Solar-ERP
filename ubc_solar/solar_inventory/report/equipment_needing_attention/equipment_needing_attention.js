// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.query_reports["Equipment Needing Attention"] = {
	filters: [{ fieldname: "include_unchecked", label: __("Include items not checked this term"), fieldtype: "Check" }],
};
