// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Build Record", {
	setup(frm) {
		frm.set_query("bom", () => ({ filters: { docstatus: 1, is_active: 1 } }));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.set_intro(__("Pick the BOM and quantity; the parts and where they come from fill in automatically. Adjust if extra parts were used, then Submit."));
		}
		if (frm.doc.stock_entry) {
			frm.add_custom_button(__("Stock Entry"), () => frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry), __("Open"));
		}
	},
	bom(frm) {
		fill_items(frm);
	},
	qty(frm) {
		fill_items(frm);
	},
	serial_numbers(frm) {
		fill_quality(frm);
	},
	quality_inspection_template(frm) {
		fill_quality(frm);
	},
});

function fill_items(frm) {
	if (!frm.doc.bom || !frm.doc.qty) return;
	frappe.call("ubc_solar.cars.doctype.build_record.build_record.get_build_items", { bom: frm.doc.bom, qty: frm.doc.qty }).then((r) => {
		frm.clear_table("items");
		(r.message || []).forEach((row) => frm.add_child("items", row));
		frm.refresh_field("items");
		const short = (r.message || []).filter((row) => !row.source_warehouse).map((row) => row.item_code);
		if (short.length) {
			frappe.msgprint(__("Not enough in stock for: {0}. Recount the bins or receive the parts first.", [short.join(", ")]));
		}
	});
}

function fill_quality(frm) {
	if (!frm.doc.quality_inspection_template) return;
	const serials = (frm.doc.serial_numbers || "").split("\n").map((s) => s.trim()).filter(Boolean);
	frappe
		.call("ubc_solar.cars.doctype.build_record.build_record.get_quality_rows", {
			template: frm.doc.quality_inspection_template,
			serials: serials,
		})
		.then((r) => {
			frm.clear_table("quality_results");
			(r.message || []).forEach((row) => frm.add_child("quality_results", row));
			frm.refresh_field("quality_results");
		});
}
