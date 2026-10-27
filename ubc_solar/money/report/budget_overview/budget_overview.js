// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.query_reports["Budget Overview"] = {
	filters: [{ fieldname: "budget", label: __("Budget"), fieldtype: "Link", options: "Solar Budget" }],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && !data.budget_line) value = `<b>${value}</b>`;
		else if (data && column.fieldname === "label") value = `&nbsp;&nbsp;&nbsp;&nbsp;${value}`;
		return value;
	},
};
