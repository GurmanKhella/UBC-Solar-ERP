// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reorder Point", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Request Reorder Now"), () =>
			frappe
				.call("ubc_solar.solar_inventory.doctype.reorder_point.reorder_point.request_reorder", { reorder_point: frm.doc.name })
				.then((r) => {
					frappe.show_alert(r.message.created ? __("Reorder requested") : __("Already requested"));
					frappe.set_route("Form", "Material Request", r.message.name);
				})
		);
		frm.add_custom_button(__("Print Card"), () =>
			window.open(`/printview?doctype=Reorder%20Point&name=${encodeURIComponent(frm.doc.name)}&format=${encodeURIComponent("Reorder Card")}&no_letterhead=1`)
		);
	},
});
