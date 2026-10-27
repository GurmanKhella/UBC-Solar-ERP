// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Solar Budget", {
	refresh(frm) {
		const s = (frm.doc.__onload || {}).summary;
		if (!s) return;
		const fmt = (v) => format_currency(v, "CAD");
		const pct = s.minimum_target ? Math.min(100, Math.round((100 * s.raised) / s.minimum_target)) : 0;
		const esc = frappe.utils.escape_html;
		const card = (label, value, note) =>
			`<div class="col-sm-4" style="margin-bottom:10px"><div class="text-muted small">${label}</div><div class="h5">${value}</div>${note ? `<div class="text-muted small">${note}</div>` : ""}</div>`;
		const lines = s.lines
			.map(
				(l) => `<tr><td><a href="${frappe.utils.get_form_link("Budget Line", l.name)}">${esc(l.line_name)}</a></td>
				<td>${esc(l.subteam || l.division || "")}</td><td>${l.priority}</td>
				<td class="text-right">${fmt(l.amount)}</td><td class="text-right">${fmt(l.spent)}</td>
				<td class="text-right">${fmt(l.committed)}</td><td class="text-right">${fmt(l.remaining)}</td></tr>`
			)
			.join("");
		frm.get_field("summary_html").$wrapper.html(`
			<p><b>${__("Raised {0} of {1} minimum target", [fmt(s.raised), fmt(s.minimum_target)])}</b></p>
			<div class="progress" style="height:10px;margin-bottom:16px"><div class="progress-bar" style="width:${pct}%"></div></div>
			<div class="row">
				${card(__("Available"), fmt(s.available), __("raised − spent − committed"))}
				${card(__("Pledged"), fmt(s.pledged), __("promised, not received; not spendable yet"))}
				${card(__("Committed"), fmt(s.committed), __("approved, not ordered"))}
				${card(__("Spent"), fmt(s.spent), __("ordered and paid"))}
				${card(__("In-kind donations"), fmt(s.in_kind), __("donated parts and services"))}
			</div>
			<table class="table table-bordered table-sm">
				<thead><tr><th>${__("Line")}</th><th>${__("Subteam / division")}</th><th>${__("Priority")}</th>
				<th class="text-right">${__("Planned")}</th><th class="text-right">${__("Spent")}</th>
				<th class="text-right">${__("Committed")}</th><th class="text-right">${__("Left")}</th></tr></thead>
				<tbody>${lines}</tbody>
			</table>`);
		frm.add_custom_button(__("Add Line"), () => frappe.new_doc("Budget Line", { budget: frm.doc.name }));
		frm.add_custom_button(__("Record Funding"), () => frappe.new_doc("Funding Entry", { budget: frm.doc.name }));
	},
});
