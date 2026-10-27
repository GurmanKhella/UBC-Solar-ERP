// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Applicant", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Schedule Interview"), () => frappe.new_doc("Applicant Interview", { applicant: frm.doc.name }), __("Create"));
		if (!frm.doc.team_member && frm.doc.status !== "Rejected") {
			frm.add_custom_button(__("Accept and Create Account"), () =>
				frappe.confirm(__("Accept {0}? Their ERP account is created with their subteam and role.", [frm.doc.full_name]), () =>
					frappe.call("ubc_solar.recruitment.doctype.applicant.applicant.accept", { applicant: frm.doc.name }).then(() => frm.reload_doc())
				)
			).addClass("btn-primary");
		}
		if (frm.doc.team_member) {
			frm.add_custom_button(__("Team Member"), () => frappe.set_route("Form", "Team Member", frm.doc.team_member), __("Open"));
		}
	},
});
