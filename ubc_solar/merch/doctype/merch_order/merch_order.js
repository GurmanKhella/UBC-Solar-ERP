// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

const ORDER = "ubc_solar.merch.doctype.merch_order.merch_order";

frappe.ui.form.on("Merch Order", {
	refresh(frm) {
		if (frm.is_new() || frm.is_dirty()) return;
		const status = frm.doc.status;
		if (["Placed", "Ready for Pickup"].includes(status) && !frm.doc.paid_on) {
			frm.add_custom_button(__("Mark Paid"), () => mark_paid(frm)).addClass("btn-primary");
		}
		if (["Placed", "Paid"].includes(status)) {
			frm.add_custom_button(__("Ready for Pickup"), () => action(frm, "mark_ready"));
		}
		if (["Paid", "Ready for Pickup"].includes(status) && frm.doc.paid_on) {
			frm.add_custom_button(__("Hand Over"), () =>
				frappe.confirm(__("Hand the items over? They come out of merch stock."), () => action(frm, "fulfil"))
			).addClass("btn-primary");
		}
		if (status !== "Cancelled") {
			frm.add_custom_button(__("Cancel / Refund"), () => cancel(frm));
		}
	},
});

frappe.ui.form.on("Merch Order Item", {
	qty: update_total,
	items_remove: update_total,
});

function update_total(frm) {
	// The server sets prices on save; this just keeps the shown total in step.
	let total = 0;
	(frm.doc.items || []).forEach((row) => {
		row.amount = (row.rate || 0) * (row.qty || 0);
		total += row.amount;
	});
	frm.set_value("total", total);
	frm.refresh_field("items");
}

function action(frm, method, args = {}) {
	return frappe.call(`${ORDER}.${method}`, { order: frm.doc.name, ...args }).then(() => frm.reload_doc());
}

function mark_paid(frm) {
	frappe.prompt(
		[
			{
				fieldname: "payment_method",
				fieldtype: "Select",
				label: __("Paid by"),
				options: ["E-transfer", "Cash", "Card", "Other"],
				default: frm.doc.payment_method || "E-transfer",
				reqd: 1,
			},
			{ fieldname: "payment_reference", fieldtype: "Data", label: __("Reference (e.g. e-transfer number)") },
		],
		(values) => action(frm, "mark_paid", values),
		__("Mark {0} paid", [format_currency(frm.doc.total, "CAD")]),
		__("Mark Paid")
	);
}

function cancel(frm) {
	const msg =
		frm.doc.status === "Fulfilled"
			? __("The items go back into merch stock and the payment is marked refunded.")
			: frm.doc.paid_on
			? __("The payment is marked refunded. Refund the buyer yourself.")
			: "";
	frappe.prompt(
		[
			{ fieldtype: "HTML", options: msg ? `<p>${msg}</p>` : "" },
			{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason") },
		],
		(values) => action(frm, "cancel_order", values),
		__("Cancel order"),
		__("Cancel Order")
	);
}
