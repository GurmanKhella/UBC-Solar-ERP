// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Car Repair", {
	setup(frm) {
		frm.set_query("solar_project", () => ({ filters: { car: frm.doc.car } }));
		frm.set_query("new_bom", () => ({ filters: { solar_project: frm.doc.solar_project } }));
	},
	refresh(frm) {
		if (frm.doc.project_doc_url) frm.add_web_link(frm.doc.project_doc_url, __("Project doc (write up what failed and why)"));
		if (frm.is_new()) return;
		frm.add_custom_button(__("Purchase Request"), () => {
			const make = (subteam) =>
				frappe.new_doc("Material Request", {
					material_request_type: "Purchase",
					solar_source: "Repair",
					solar_repair: frm.doc.name,
					solar_car: frm.doc.car,
					solar_project: frm.doc.solar_project,
					solar_subteam: subteam,
				});
			if (!frm.doc.solar_project) return make(null);
			frappe.db.get_value("Solar Project", frm.doc.solar_project, "subteam").then(({ message }) => make(message.subteam));
		}, __("Create"));
	},
});
