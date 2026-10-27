// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.query_reports["Team Access"] = {
	filters: [
		{ fieldname: "position", label: __("Position"), fieldtype: "Link", options: "Team Position" },
		{ fieldname: "subteam", label: __("Subteam"), fieldtype: "Link", options: "Subteam" },
		{ fieldname: "include_alumni", label: __("Include alumni"), fieldtype: "Check" },
	],
};
