app_name = "ubc_solar"
app_title = "UBC Solar"
app_publisher = "UBC Solar"
app_description = "UBC Solar operations system (ERP) on ERPNext"
app_email = "ubcsolar@example.com"
app_license = "unlicensed"

required_apps = ["frappe/erpnext"]

add_to_apps_screen = [
	{
		"name": "ubc_solar",
		"logo": "/assets/ubc_solar/images/logo.svg",
		"title": "UBC Solar",
		"route": "/desk/cars",
	}
]

# Install / migrate
after_install = "ubc_solar.setup.install.after_install"
after_migrate = "ubc_solar.setup.install.after_migrate"
before_tests = "ubc_solar.setup.install.before_tests"

# Forms of ERPNext doctypes extended by this app
doctype_js = {
	"Item": "public/js/item.js",
	"BOM": "public/js/bom.js",
	"Material Request": "public/js/material_request.js",
	"Warehouse": "public/js/warehouse.js",
}

doc_events = {
	"Item": {
		"before_insert": "ubc_solar.cars.parts.item_before_insert",
		"validate": "ubc_solar.cars.parts.item_validate",
	},
	"BOM": {
		"validate": "ubc_solar.cars.bom.validate",
		"before_submit": "ubc_solar.cars.bom.before_submit",
		"on_submit": "ubc_solar.cars.bom.on_submit",
		"on_update": "ubc_solar.cars.bom.on_update",
		"before_cancel": "ubc_solar.cars.bom.before_cancel",
	},
	"Material Request": {
		"before_validate": "ubc_solar.money.purchasing.before_validate",
		"validate": "ubc_solar.money.purchasing.validate",
		"before_submit": "ubc_solar.money.purchasing.before_submit",
		"on_submit": "ubc_solar.money.purchasing.on_submit",
		"on_update": "ubc_solar.money.purchasing.on_update",
	},
	"Role Profile": {
		"on_update": "ubc_solar.team.doctype.team_member.team_member.role_profile_updated",
	},
	"Purchase Receipt": {
		"on_submit": "ubc_solar.money.purchasing.purchase_receipt_on_submit",
	},
}

scheduler_events = {
	"daily": [
		"ubc_solar.solar_inventory.tasks.flag_expiring_batches",
		"ubc_solar.solar_automation.tasks.escalate_waiting_approvals",
		"ubc_solar.sponsors.tasks.remind_follow_ups",
	],
	"hourly": [
		"ubc_solar.solar_automation.wiki.refresh_current_car_page",
	],
}

jinja = {
	"methods": [
		"ubc_solar.utils.qr.qr_svg",
		"ubc_solar.utils.qr.scan_url",
	],
}

