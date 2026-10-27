// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOM Import", {
	refresh(frm) {
		if (frm.is_new()) {
			frm.set_intro(__("Export the BOM from Altium or SolidWorks/3DEXPERIENCE, attach the file, save, then click Import."));
			return;
		}
		frm.add_custom_button(frm.doc.status === "Imported" ? __("Import Again") : __("Import"), () => {
			frappe.dom.freeze(__("Reading the BOM..."));
			frm.call("run_import")
				.then((r) => {
					const res = r.message;
					let msg = res.summary;
					if (res.warnings && res.warnings.length) {
						msg += "<br><br><b>" + __("Check these:") + "</b><ul>" + res.warnings.map((w) => `<li>${frappe.utils.escape_html(w)}</li>`).join("") + "</ul>";
					}
					frappe.msgprint({ title: __("BOM imported"), message: msg, primary_action: {
						label: __("Open draft BOM"),
						action: () => frappe.set_route("Form", "BOM", res.bom),
					} });
					frm.reload_doc();
				})
				.always(() => frappe.dom.unfreeze());
		}).addClass("btn-primary");
		if (frm.doc.bom) {
			frm.add_custom_button(__("Draft BOM"), () => frappe.set_route("Form", "BOM", frm.doc.bom), __("Open"));
		}
	},
});
