// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sponsor Donation", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.donation_type === "Parts" && !frm.doc.stock_entry) {
			frm.add_custom_button(__("Parts Arrived: Put in Stock"), () =>
				frappe
					.call("ubc_solar.sponsors.doctype.sponsor_donation.sponsor_donation.receive_parts", { donation: frm.doc.name })
					.then(() => frm.reload_doc())
			).addClass("btn-primary");
		}
	},
});
