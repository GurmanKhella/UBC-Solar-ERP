// Locations: open the phone scan page or print the bin/shelf label.

frappe.ui.form.on("Warehouse", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Open Scan Page"), () => window.open(`/scan?l=${encodeURIComponent(frm.doc.name)}`));
		frm.add_custom_button(__("Print Label"), () =>
			window.open(
				`/printview?doctype=Warehouse&name=${encodeURIComponent(frm.doc.name)}&format=${encodeURIComponent("Location Label")}&no_letterhead=1`
			)
		);
	},
});
