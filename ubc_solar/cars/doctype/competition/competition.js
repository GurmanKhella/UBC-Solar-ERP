// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Competition", {
	setup(frm) {
		frm.set_query("vehicle_bom", () => ({ filters: { solar_car: frm.doc.car, solar_bom_kind: "Vehicle", docstatus: 1 } }));
	},
	refresh(frm) {
		if (frm.is_new()) return;
		const packed = (frm.doc.support_items || []).filter((r) => r.packed).length;
		const total = (frm.doc.support_items || []).length;
		if (total) frm.dashboard.set_headline(__("Packed {0} of {1} support items.", [packed, total]));
		frm.add_custom_button(__("Copy Support BOM From..."), () => {
			frappe.prompt(
				{ fieldname: "from_competition", fieldtype: "Link", options: "Competition", label: __("Past competition"), reqd: 1 },
				(v) =>
					frappe
						.call("ubc_solar.cars.doctype.competition.competition.copy_support_items", {
							competition: frm.doc.name,
							from_competition: v.from_competition,
						})
						.then((r) => {
							frappe.show_alert(__("Added {0} items", [r.message]));
							frm.reload_doc();
						}),
				__("Reuse a support BOM")
			);
		});
		frm.add_custom_button(__("Check Out Packed Equipment"), () =>
			frappe
				.call("ubc_solar.cars.doctype.competition.competition.check_out_packed_equipment", { competition: frm.doc.name })
				.then((r) => frappe.msgprint(__("Checked out {0} items to you for this competition.", [(r.message || []).length])))
		);
		frm.add_custom_button(__("Purchase Request"), () =>
			frappe.new_doc("Material Request", {
				material_request_type: "Purchase",
				solar_source: "Competition",
				solar_competition: frm.doc.name,
				solar_car: frm.doc.car,
			})
		, __("Create"));
	},
});
