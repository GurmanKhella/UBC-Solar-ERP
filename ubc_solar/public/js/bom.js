// BOM versions: approved versions are fixed; reverting makes an earlier one active again.

frappe.ui.form.on("BOM", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && !(frm.doc.is_active && frm.doc.is_default)) {
			frm.add_custom_button(__("Make This Version Active"), () => {
				frappe.confirm(__("Make {0} the active version for {1}?", [frm.doc.name, frm.doc.item]), () =>
					frappe.call("ubc_solar.cars.bom.make_version_active", { bom: frm.doc.name }).then(() => frm.reload_doc())
				);
			});
		}
		if (frm.doc.solar_project) {
			frm.add_custom_button(__("Project"), () => frappe.set_route("Form", "Solar Project", frm.doc.solar_project), __("Open"));
		}
		if (frm.doc.solar_purchase_request) {
			frm.add_custom_button(
				__("Purchase Request"),
				() => frappe.set_route("Form", "Material Request", frm.doc.solar_purchase_request),
				__("Open")
			);
		}
		if (frm.doc.docstatus === 0 && frm.doc.workflow_state === "Draft") {
			frm.dashboard.set_headline(
				__("Review what CAD left out (fabrication, connectors, raw stock, fasteners, shipping), then use Actions > Mark Ready for Review.")
			);
		}
	},
});
