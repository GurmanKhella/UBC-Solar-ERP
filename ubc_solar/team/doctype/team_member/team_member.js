// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Team Member", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.position === "Alumni") return;
		frm.add_custom_button(__("Offboard to Alumni"), () => offboard(frm));
	},
});

function offboard(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Offboard {0}", [frm.doc.full_name]),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__(
					"Their projects, draft BOMs and sponsors move to the new owner, open purchases move to the new approver, and their role becomes Alumni (view-only). Equipment they have checked out must be returned first."
				)}</p>`,
			},
			{ fieldname: "new_owner", fieldtype: "Link", options: "User", label: __("New owner for projects, BOMs and sponsors") },
			{ fieldname: "new_approver", fieldtype: "Link", options: "User", label: __("Who takes over their open purchases") },
		],
		primary_action_label: __("Offboard"),
		primary_action(values) {
			frappe
				.call("ubc_solar.team.doctype.team_member.team_member.offboard", {
					member: frm.doc.name,
					new_owner: values.new_owner,
					new_approver: values.new_approver,
				})
				.then((r) => {
					d.hide();
					const s = r.message;
					let msg = __("Moved {0} projects, {1} BOMs, {2} purchases and {3} sponsors.", [
						s.projects.length,
						s.boms.length,
						s.purchases.length,
						s.sponsors.length,
					]);
					if (s.was_maintainer) {
						msg +=
							"<br><br>" +
							__("They were an ERP maintainer: hand over the admin login, backups and README during the summer handover.");
					}
					frappe.msgprint(msg, __("Offboarded"));
					frm.reload_doc();
				});
		},
	});
	d.show();
}
