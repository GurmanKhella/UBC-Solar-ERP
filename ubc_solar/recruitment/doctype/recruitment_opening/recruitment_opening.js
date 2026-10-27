// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Recruitment Opening", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Published") {
			frm.add_web_link("/apply", __("Public application form"));
		}
		frm.add_custom_button(__("Copy From a Previous Opening"), () =>
			frappe.prompt(
				{
					fieldname: "from_opening",
					fieldtype: "Link",
					options: "Recruitment Opening",
					label: __("Previous opening"),
					reqd: 1,
					get_query: () => ({ filters: { name: ["!=", frm.doc.name] } }),
				},
				(v) =>
					frappe
						.call("ubc_solar.recruitment.doctype.recruitment_opening.recruitment_opening.copy_from", {
							opening: frm.doc.name,
							from_opening: v.from_opening,
						})
						.then(() => frm.reload_doc()),
				__("Reuse a description and challenge")
			)
		);
	},
});
