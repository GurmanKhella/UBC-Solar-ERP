// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Manufacturing Package", {
	refresh(frm) {
		if (frm.is_new()) return;
		const stages = (frm.doc.__onload || {}).stages || [];
		const esc = frappe.utils.escape_html;
		let html = "";
		if (!stages.length) {
			html = `<p class="text-muted">${__("No stages yet. Add one per procedure, e.g. module assembly, BMS installation, final assembly.")}</p>`;
		} else {
			html = `<table class="table table-bordered"><thead><tr>
				<th>#</th><th>${__("Stage")}</th><th>${__("Produces")}</th><th>${__("Manufacturing BOM")}</th><th>${__("Time")}</th><th>${__("Procedure")}</th>
			</tr></thead><tbody>${stages
				.map(
					(s) => `<tr>
					<td>${s.sequence}</td>
					<td><a href="${frappe.utils.get_form_link("Manufacturing Stage", s.name)}">${esc(s.stage_name)}</a>${s.is_final_stage ? ` <span class="indicator-pill green">${__("final")}</span>` : ""}</td>
					<td>${esc(s.output_item || "")}</td>
					<td>${s.manufacturing_bom ? `<a href="${frappe.utils.get_form_link("BOM", s.manufacturing_bom)}">${esc(s.manufacturing_bom)}</a>` : "-"}</td>
					<td>${s.total_minutes || 0} min</td>
					<td>${s.procedure_doc_url ? `<a target="_blank" href="${esc(s.procedure_doc_url)}">${__("Drive doc")}</a>` : "-"}</td>
				</tr>`
				)
				.join("")}</tbody></table>`;
		}
		frm.get_field("stages_html").$wrapper.html(html);
		frm.add_custom_button(__("Add Stage"), () =>
			frappe.new_doc("Manufacturing Stage", { manufacturing_package: frm.doc.name, sequence: stages.length + 1 })
		);
	},
});
