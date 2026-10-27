// Team part numbers: make the next revision (M-0042-A -> M-0042-B).

frappe.ui.form.on("Item", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.solar_base_part_number && frm.doc.solar_revision) {
			frm.add_custom_button(__("New Revision"), () => {
				frappe.confirm(__("Create the next revision of {0}?", [frm.doc.name]), () =>
					frappe.call("ubc_solar.cars.parts.new_revision", { item_code: frm.doc.name }).then((r) => {
						frappe.set_route("Form", "Item", r.message);
					})
				);
			});
		}
		frm.add_custom_button(__("Where is it?"), () => window.open(`/scan?i=${encodeURIComponent(frm.doc.name)}`));
	},
});
