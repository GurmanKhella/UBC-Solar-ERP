// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Merch Product", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("View Store"), () => window.open("/merch"));
		if (frappe.model.can_create("Material Request")) {
			frm.add_custom_button(__("Order More"), () =>
				frappe
					.call("ubc_solar.merch.doctype.merch_product.merch_product.make_restock_request", { product: frm.doc.name })
					.then((r) => {
						const doc = frappe.model.sync(r.message)[0];
						frappe.set_route("Form", doc.doctype, doc.name);
					})
			);
		}
	},
});
