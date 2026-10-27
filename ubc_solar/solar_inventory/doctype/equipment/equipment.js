// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Equipment", {
	refresh(frm) {
		if (frm.is_new()) return;
		const EQ = "ubc_solar.solar_inventory.doctype.equipment.equipment";
		if (frm.doc.tracking !== "By toolbox or wall") {
			if (frm.doc.checked_out_to) {
				frm.add_custom_button(__("Return"), () => frappe.call(`${EQ}.return_equipment`, { equipment: frm.doc.name }).then(() => frm.reload_doc()));
			} else {
				frm.add_custom_button(__("Check Out to Me"), () =>
					frappe.prompt(
						{ fieldname: "purpose", fieldtype: "Data", label: __("What is it for?") },
						(v) => frappe.call(`${EQ}.check_out`, { equipment: frm.doc.name, purpose: v.purpose }).then(() => frm.reload_doc()),
						__("Check out")
					)
				);
			}
		}
		frm.add_custom_button(__("Here and Working"), () =>
			frappe.call(`${EQ}.confirm_check`, { equipment: frm.doc.name, condition: "Working" }).then(() => frm.reload_doc())
		, __("Check"));
		frm.add_custom_button(__("Needs Repair"), () =>
			frappe.call(`${EQ}.confirm_check`, { equipment: frm.doc.name, condition: "Needs Repair" }).then(() => frm.reload_doc())
		, __("Check"));
		frm.add_custom_button(__("Missing"), () =>
			frappe.call(`${EQ}.confirm_check`, { equipment: frm.doc.name, condition: "Missing" }).then(() => frm.reload_doc())
		, __("Check"));
		frm.add_custom_button(__("Print Tag"), () =>
			window.open(`/printview?doctype=Equipment&name=${encodeURIComponent(frm.doc.name)}&format=${encodeURIComponent("Equipment Tag")}&no_letterhead=1`)
		);
	},
});
