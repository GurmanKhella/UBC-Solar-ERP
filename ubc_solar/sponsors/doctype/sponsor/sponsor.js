// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sponsor", {
	refresh(frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: "name", doctype: "Sponsor" };
		if (frm.is_new()) {
			frm.get_field("contact_html").$wrapper.html(`<p class="text-muted">${__("Save first to add contacts.")}</p>`);
			return;
		}
		frappe.contacts.render_address_and_contact(frm);
		frm.add_custom_button(__("Donation"), () => frappe.new_doc("Sponsor Donation", { sponsor: frm.doc.name }), __("Create"));
		frm.add_custom_button(__("Log a Conversation"), () => {
			frappe.prompt(
				[
					{ fieldname: "interaction_type", fieldtype: "Select", label: __("Type"), options: "Email\nCall\nMeeting\nEvent\nOther", default: "Email" },
					{ fieldname: "summary", fieldtype: "Small Text", label: __("Summary"), reqd: 1 },
					{ fieldname: "next_follow_up", fieldtype: "Date", label: __("Next follow-up (optional)") },
				],
				(v) => {
					frm.add_child("interactions", { date: frappe.datetime.get_today(), interaction_type: v.interaction_type, summary: v.summary, by_user: frappe.session.user });
					if (v.next_follow_up) frm.set_value("next_follow_up", v.next_follow_up);
					frm.save();
				},
				__("Log a conversation")
			);
		});
	},
});
