// Copyright (c) 2026, UBC Solar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Car", {
	refresh(frm) {
		if (frm.is_new()) return;
		render_overview(frm);
		if (frm.doc.vehicle_item) {
			frm.add_custom_button(__("Vehicle BOM"), () => open_vehicle_bom(frm), __("Open"));
		}
		frm.add_custom_button(__("All Harnesses"), () => frappe.set_route("query-report", "All Harnesses", { car: frm.doc.name }), __("Open"));
		if (frm.doc.status === "Retired") {
			frm.set_intro(__("This car is retired, so it's view-only."), "orange");
			if (frm.doc.wiki_snapshot_url) frm.add_web_link(frm.doc.wiki_snapshot_url, __("End-of-car wiki snapshot"));
			return;
		}
		frm.add_custom_button(__("Set Up This Car"), () => set_up(frm), __("Actions"));
		frm.add_custom_button(__("Draft Vehicle BOM from Subsystems"), () =>
			frappe.call("ubc_solar.cars.doctype.car.car.draft_vehicle_bom", { car: frm.doc.name }).then((r) =>
				frappe.set_route("Form", "BOM", r.message)
			)
		, __("Actions"));
		frm.add_custom_button(__("Salvage Parts to Stock"), () => salvage(frm, false), __("Actions"));
		frm.add_custom_button(__("Retire Car"), () => salvage(frm, true), __("Actions"));
	},
});

function render_overview(frm) {
	const o = (frm.doc.__onload || {}).overview;
	if (!o) return;
	const cost = o.vehicle_bom ? format_currency(o.vehicle_cost, "CAD") : __("no vehicle BOM yet");
	frm.get_field("dashboard_html").$wrapper.html(`
		<div class="row">
			<div class="col-sm-4"><div class="text-muted small">${__("Total cost (vehicle BOM)")}</div><div class="h5">${cost}</div></div>
			<div class="col-sm-4"><div class="text-muted small">${__("Projects")}</div><div class="h5">${o.projects}</div></div>
			<div class="col-sm-4"><div class="text-muted small">${__("BOMs waiting for review")}</div><div class="h5">${o.boms_waiting}</div></div>
			<div class="col-sm-4"><div class="text-muted small">${__("Manufacturing packages")}</div><div class="h5">${o.packages}</div></div>
			<div class="col-sm-4"><div class="text-muted small">${__("Open repairs")}</div><div class="h5">${o.open_repairs}</div></div>
		</div>`);
}

function open_vehicle_bom(frm) {
	const o = (frm.doc.__onload || {}).overview || {};
	if (o.vehicle_bom) {
		frappe.set_route("Form", "BOM", o.vehicle_bom);
	} else {
		frappe.new_doc("BOM", { item: frm.doc.vehicle_item, solar_bom_kind: "Vehicle", solar_car: frm.doc.name });
	}
}

function set_up(frm) {
	frappe.confirm(
		__("Create a manufacturing package for every enabled subsystem, and the car's budget with its starting lines (Solar Settings > New car)? Running it again only adds what's missing, e.g. after adding a subsystem or subteam."),
		() =>
			frappe
				.call("ubc_solar.cars.doctype.car.car.set_up_car", { car: frm.doc.name, make_budget_active: 1 })
				.then((r) => {
					const m = r.message;
					frappe.msgprint(
						__("Created {0} manufacturing packages{1}. Next: add projects with owners, and fill in the budget amounts.", [
							m.packages.length,
							m.budget ? __(" and budget {0}", [m.budget]) : "",
						])
					);
					frm.reload_doc();
				})
	);
}

function salvage(frm, retire) {
	const d = new frappe.ui.Dialog({
		title: retire ? __("Retire {0}", [frm.doc.car_title]) : __("Salvage parts from {0}", [frm.doc.car_title]),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				options: retire
					? `<p>${__("Usable parts go back into stock, the car becomes view-only, and the end-of-car snapshot is published to the wiki.")}</p>`
					: `<p>${__("Add usable parts taken off this car back into stock.")}</p>`,
			},
			{
				fieldname: "rows",
				fieldtype: "Table",
				label: __("Salvaged parts"),
				in_place_edit: true,
				data: [],
				fields: [
					{ fieldname: "item_code", fieldtype: "Link", options: "Item", label: __("Part"), in_list_view: 1, reqd: 1 },
					{ fieldname: "qty", fieldtype: "Float", label: __("Qty"), in_list_view: 1, reqd: 1 },
					{ fieldname: "warehouse", fieldtype: "Link", options: "Warehouse", label: __("Put in"), in_list_view: 1 },
				],
			},
		],
		primary_action_label: retire ? __("Retire") : __("Add to stock"),
		primary_action(values) {
			const method = retire ? "ubc_solar.cars.doctype.car.car.retire_car" : "ubc_solar.cars.doctype.car.car.salvage_parts";
			const args = retire ? { car: frm.doc.name, salvage_rows: values.rows || [] } : { car: frm.doc.name, rows: values.rows || [] };
			frappe.call(method, args).then(() => {
				d.hide();
				frm.reload_doc();
			});
		},
	});
	d.show();
}
