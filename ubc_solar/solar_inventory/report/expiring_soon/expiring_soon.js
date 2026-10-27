// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.query_reports["Expiring Soon"] = {
	filters: [{ fieldname: "days", label: __("Within (days)"), fieldtype: "Int", default: 30 }],
};
