// Captain and Execs (Solar Access Manager) edit access profiles too. Frappe only shows the
// role checkboxes to System Managers; the server still limits them to roles they have.
frappe.ui.form.on("Role Profile", {
	refresh(frm) {
		if (frm.roles_editor || has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;
		if (!frappe.user_roles.includes("Solar Access Manager")) return;
		frm.roles_editor = new frappe.RoleEditor($(frm.fields_dict.roles_html.wrapper), frm);
		frm.roles_editor.show();
	},
});
