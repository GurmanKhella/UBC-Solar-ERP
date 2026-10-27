// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Budget Line", {
	refresh(frm) {
		const s = (frm.doc.__onload || {}).summary;
		if (!s) return;
		const fmt = (v) => format_currency(v, "CAD");
		frm.get_field("summary_html").$wrapper.html(
			`<p>${__("Spent {0} · committed {1} · {2} left of {3}", [fmt(s.spent), fmt(s.committed), fmt(s.remaining), fmt(frm.doc.amount)])}</p>`
		);
	},
});
