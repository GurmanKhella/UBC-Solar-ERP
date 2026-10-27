// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Manufacturing Stage", {
	setup(frm) {
		frm.set_query("manufacturing_bom", () => ({ filters: { item: frm.doc.output_item } }));
	},
	refresh(frm) {
		if (frm.doc.procedure_doc_url) frm.add_web_link(frm.doc.procedure_doc_url, __("Written procedure (Drive)"));
		if (frm.is_new() || !frm.doc.output_item) return;
		if (!frm.doc.manufacturing_bom) {
			frm.add_custom_button(__("Manufacturing BOM"), () =>
				frappe.new_doc("BOM", {
					item: frm.doc.output_item,
					solar_bom_kind: "Manufacturing Stage",
					solar_manufacturing_stage: frm.doc.name,
					solar_car: frm.doc.car,
				})
			, __("Create"));
		} else {
			frm.add_custom_button(__("Record a Build"), () =>
				frappe.new_doc("Build Record", { bom: frm.doc.manufacturing_bom, manufacturing_stage: frm.doc.name })
			);
		}
	},
});
