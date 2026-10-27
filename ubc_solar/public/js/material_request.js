// Purchase requests: the approver orders (with the receipt) and marks received.

frappe.ui.form.on("Material Request", {
	refresh(frm) {
		if (frm.doc.material_request_type !== "Purchase" || frm.is_new()) return;
		show_budget(frm);
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.workflow_state === "Approved") {
			frm.add_custom_button(__("Mark Ordered"), () => mark_ordered(frm)).addClass("btn-primary");
		}
		if (frm.doc.workflow_state === "Ordered") {
			frm.add_custom_button(__("Mark Received"), () => mark_received(frm)).addClass("btn-primary");
		}
	},
});

function show_budget(frm) {
	if (!frm.doc.solar_budget_line) return;
	frappe.db.get_value("Budget Line", frm.doc.solar_budget_line, "budget").then(({ message }) => {
		if (!message || !message.budget) return;
		frappe.call("ubc_solar.money.budget.summary", { budget: message.budget }).then((r) => {
			const s = r.message;
			if (!s) return;
			const line = (s.lines || []).find((l) => l.name === frm.doc.solar_budget_line);
			const fmt = (v) => format_currency(v, "CAD");
			let html = __("Team available: {0} (raised {1} of {2} target).", [fmt(s.available), fmt(s.raised), fmt(s.minimum_target)]);
			if (line) html += " " + __("{0}: {1} left of {2}.", [line.line_name, fmt(line.remaining), fmt(line.amount)]);
			frm.dashboard.set_headline(html);
		});
	});
}

function mark_ordered(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Mark Ordered"),
		fields: [
			{ fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: __("Ordered from"), reqd: 1 },
			{ fieldname: "order_number", fieldtype: "Data", label: __("Order number") },
			{ fieldname: "receipt", fieldtype: "Attach", label: __("Receipt"), reqd: 1 },
			{
				fieldname: "paid_by",
				fieldtype: "Select",
				label: __("Paid by"),
				options: "Team\nMember (reimbursement)",
				default: frm.doc.solar_paid_by || "Team",
			},
			{ fieldtype: "Section Break", label: __("Actual prices (per unit)") },
			{
				fieldname: "rates",
				fieldtype: "Table",
				cannot_add_rows: true,
				in_place_edit: true,
				data: frm.doc.items.map((row) => ({ item_code: row.item_code, qty: row.qty, rate: row.rate })),
				fields: [
					{ fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("Item"), read_only: 1, in_list_view: 1 },
					{ fieldname: "qty", fieldtype: "Float", label: __("Qty"), read_only: 1, in_list_view: 1 },
					{ fieldname: "rate", fieldtype: "Currency", label: __("Price"), in_list_view: 1 },
				],
			},
		],
		primary_action_label: __("Save"),
		primary_action(values) {
			const rates = {};
			(values.rates || []).forEach((r) => (rates[r.item_code] = r.rate));
			frappe
				.call("ubc_solar.money.purchasing.mark_ordered", {
					material_request: frm.doc.name,
					supplier: values.supplier,
					receipt: values.receipt,
					order_number: values.order_number,
					rates: rates,
					paid_by: values.paid_by,
				})
				.then(() => {
					d.hide();
					frm.reload_doc();
				});
		},
	});
	d.show();
}

function mark_received(frm) {
	frappe.call("ubc_solar.money.receiving.get_receivable", { material_request: frm.doc.name }).then((r) => {
		const rows = r.message || [];
		const d = new frappe.ui.Dialog({
			title: __("Mark Received"),
			size: "large",
			fields: [
				{
					fieldtype: "HTML",
					options: `<p>${__("Open the box and check everything is there. Enter what arrived and which shelf it goes on. Perishables need their expiry date.")}</p>`,
				},
				{
					fieldname: "lines",
					fieldtype: "Table",
					in_place_edit: true,
					data: rows,
					fields: [
						{ fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("Item"), in_list_view: 1, reqd: 1 },
						{ fieldname: "qty", fieldtype: "Float", label: __("Arrived"), in_list_view: 1, reqd: 1 },
						{ fieldname: "warehouse", fieldtype: "Link", options: "Warehouse", label: __("Shelf"), in_list_view: 1, reqd: 1 },
						{ fieldname: "expiry_date", fieldtype: "Date", label: __("Expiry (perishables)"), in_list_view: 1 },
					],
				},
			],
			primary_action_label: __("Put in stock"),
			primary_action(values) {
				frappe
					.call("ubc_solar.money.purchasing.mark_received", {
						material_request: frm.doc.name,
						lines: values.lines,
					})
					.then(() => {
						d.hide();
						frm.reload_doc();
					});
			},
		});
		d.show();
	});
}
