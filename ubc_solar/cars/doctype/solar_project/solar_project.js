// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Solar Project", {
	setup(frm) {
		frm.set_query("from_project", () => ({ filters: { car: frm.doc.car, project_type: "Design" } }));
		frm.set_query("to_project", () => ({ filters: { car: frm.doc.car, project_type: "Design" } }));
		frm.set_query("subsystem", () => ({ filters: { enabled: 1, is_vehicle_harnesses: 0 } }));
	},
	refresh(frm) {
		if (frm.is_new()) return;
		for (const [field, label] of [
			["drive_doc_url", __("Project Doc")],
			["monday_item_url", __("Monday")],
			["design_link", __("CAD / Altium 365")],
		]) {
			if (frm.doc[field]) frm.add_web_link(frm.doc[field], label);
		}
		frm.add_custom_button(__("Import BOM from CAD"), () =>
			frappe.new_doc("BOM Import", { solar_project: frm.doc.name, design_revision: frm.doc.design_revision })
		, __("Create"));
		if (frm.doc.part) {
			frm.add_custom_button(__("BOM (by hand)"), () =>
				frappe.new_doc("BOM", { item: frm.doc.part, solar_project: frm.doc.name, solar_bom_kind: "Project" })
			, __("Create"));
		}
		frm.add_custom_button(__("Purchase Request"), () =>
			frappe.new_doc("Material Request", {
				material_request_type: "Purchase",
				solar_project: frm.doc.name,
				solar_car: frm.doc.car,
				solar_subteam: frm.doc.subteam,
			})
		, __("Create"));
		frm.add_custom_button(__("Repair"), () =>
			frappe.new_doc("Car Repair", { car: frm.doc.car, solar_project: frm.doc.name, solar_subsystem: frm.doc.subsystem })
		, __("Create"));
		if (frm.doc.project_type === "Design") {
			frm.add_custom_button(__("Harnesses Touching This Project"), () =>
				frappe.set_route("query-report", "All Harnesses", { car: frm.doc.car, project: frm.doc.name })
			, __("Open"));
		}
	},
});
