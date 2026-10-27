"""Fields this app adds to ERPNext's own doctypes.

Applied on install and on every migrate (idempotent), so they survive upgrades
without editing ERPNext.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

INVENTORY_TYPES = (
	"\nComponent / Material\nExpensive / Long-lead\nSmall Part\nShop Consumable\nBuild Material\nPerishable"
)
PURCHASE_SOURCES = "Manual\nBOM\nTwo-bin\nReorder card\nRepair\nCompetition"
STOCK_SOURCES = "\nGrab\nBuild\nRepair\nSalvage\nDonation\nMove\nOther"


def get_custom_fields():
	return {
		"Item": [
			{
				"fieldname": "solar_section",
				"fieldtype": "Section Break",
				"label": "UBC Solar",
				"insert_after": "description",
			},
			{
				"fieldname": "solar_make_or_buy",
				"fieldtype": "Select",
				"label": "Make or Buy",
				"options": "\nMake\nBuy",
				"insert_after": "solar_section",
				"in_standard_filter": 1,
				"description": "Make: built in-house or by a sponsor shop. Buy: bought from a supplier. "
				"Only bought items become purchase requests.",
			},
			{
				"fieldname": "solar_discipline",
				"fieldtype": "Select",
				"label": "Discipline",
				"options": "\nMechanical\nElectrical\nAssembly",
				"insert_after": "solar_make_or_buy",
				"description": "Decides the part number prefix for parts the team makes.",
			},
			{
				"fieldname": "solar_inventory_type",
				"fieldtype": "Select",
				"label": "Inventory Type",
				"options": INVENTORY_TYPES,
				"insert_after": "solar_discipline",
				"in_standard_filter": 1,
				"description": "Shop consumables are never counted, only reordered. "
				"Perishables get an expiry date when received.",
			},
			{
				"fieldname": "solar_project",
				"fieldtype": "Link",
				"label": "Home Project",
				"options": "Solar Project",
				"insert_after": "solar_inventory_type",
			},
			{
				"fieldname": "solar_col_1",
				"fieldtype": "Column Break",
				"insert_after": "solar_project",
			},
			{
				"fieldname": "solar_manufacturer",
				"fieldtype": "Data",
				"label": "Manufacturer",
				"insert_after": "solar_col_1",
			},
			{
				"fieldname": "solar_mpn",
				"fieldtype": "Data",
				"label": "Manufacturer Part Number",
				"insert_after": "solar_manufacturer",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "solar_material",
				"fieldtype": "Data",
				"label": "Material",
				"insert_after": "solar_mpn",
			},
			{
				"fieldname": "solar_vendor",
				"fieldtype": "Data",
				"label": "Vendor",
				"insert_after": "solar_material",
				"description": "e.g. Digi-Key, or Sponsor machine shop",
			},
			{
				"fieldname": "solar_datasheet",
				"fieldtype": "Data",
				"label": "Datasheet",
				"options": "URL",
				"insert_after": "solar_vendor",
			},
			{
				"fieldname": "solar_base_part_number",
				"fieldtype": "Data",
				"label": "Base Part Number",
				"insert_after": "solar_datasheet",
				"read_only": 1,
				"description": "Team number without the revision letter, e.g. M-0042",
			},
			{
				"fieldname": "solar_revision",
				"fieldtype": "Data",
				"label": "Revision",
				"insert_after": "solar_base_part_number",
				"read_only": 1,
			},
		],
		"BOM": [
			{
				"fieldname": "solar_section",
				"fieldtype": "Section Break",
				"label": "UBC Solar",
				"insert_after": "company",
			},
			{
				"fieldname": "solar_bom_kind",
				"fieldtype": "Select",
				"label": "BOM Kind",
				"options": "Project\nManufacturing Stage\nVehicle",
				"default": "Project",
				"insert_after": "solar_section",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "solar_project",
				"fieldtype": "Link",
				"label": "Project",
				"options": "Solar Project",
				"insert_after": "solar_bom_kind",
				"in_standard_filter": 1,
				"depends_on": "eval:doc.solar_bom_kind=='Project'",
			},
			{
				"fieldname": "solar_manufacturing_stage",
				"fieldtype": "Link",
				"label": "Manufacturing Stage",
				"options": "Manufacturing Stage",
				"insert_after": "solar_project",
				"depends_on": "eval:doc.solar_bom_kind=='Manufacturing Stage'",
			},
			{
				"fieldname": "solar_car",
				"fieldtype": "Link",
				"label": "Car",
				"options": "Car",
				"insert_after": "solar_manufacturing_stage",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "solar_subteam",
				"fieldtype": "Link",
				"label": "Subteam",
				"options": "Subteam",
				"insert_after": "solar_car",
				"read_only": 1,
			},
			{
				"fieldname": "solar_col_1",
				"fieldtype": "Column Break",
				"insert_after": "solar_subteam",
			},
			{
				"fieldname": "solar_bom_owner",
				"fieldtype": "Link",
				"label": "BOM Owner",
				"options": "User",
				"insert_after": "solar_col_1",
				"description": "Pinged when the BOM is approved or sent back.",
			},
			{
				"fieldname": "solar_design_revision",
				"fieldtype": "Data",
				"label": "Design Revision",
				"insert_after": "solar_bom_owner",
				"description": "e.g. BMS PCB rev B",
			},
			{
				"fieldname": "solar_approved_by",
				"fieldtype": "Link",
				"label": "Approved By",
				"options": "User",
				"insert_after": "solar_design_revision",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_approved_on",
				"fieldtype": "Datetime",
				"label": "Approved On",
				"insert_after": "solar_approved_by",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_purchase_request",
				"fieldtype": "Link",
				"label": "Purchase Request",
				"options": "Material Request",
				"insert_after": "solar_approved_on",
				"read_only": 1,
				"no_copy": 1,
			},
		],
		"BOM Item": [
			{
				"fieldname": "solar_designators",
				"fieldtype": "Small Text",
				"label": "Designators",
				"insert_after": "item_name",
			},
			{
				"fieldname": "solar_make_or_buy",
				"fieldtype": "Data",
				"label": "Make or Buy",
				"fetch_from": "item_code.solar_make_or_buy",
				"read_only": 1,
				"in_list_view": 1,
				"columns": 1,
				"insert_after": "solar_designators",
			},
		],
		"Material Request": [
			{
				"fieldname": "solar_section",
				"fieldtype": "Section Break",
				"label": "Purchase Details",
				"insert_after": "material_request_type",
			},
			{
				"fieldname": "solar_source",
				"fieldtype": "Select",
				"label": "Came From",
				"options": PURCHASE_SOURCES,
				"default": "Manual",
				"insert_after": "solar_section",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "solar_subteam",
				"fieldtype": "Link",
				"label": "Subteam",
				"options": "Subteam",
				"insert_after": "solar_source",
				"in_standard_filter": 1,
				"description": "Decides who can approve: this subteam's Lead, the division's Exec, or the Captain.",
			},
			{
				"fieldname": "solar_budget_line",
				"fieldtype": "Link",
				"label": "Budget Line",
				"options": "Budget Line",
				"insert_after": "solar_subteam",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "solar_requested_by",
				"fieldtype": "Link",
				"label": "Requested By",
				"options": "User",
				"default": "__user",
				"insert_after": "solar_budget_line",
				"description": "Pinged in Slack when the parts arrive.",
			},
			{
				"fieldname": "solar_col_1",
				"fieldtype": "Column Break",
				"insert_after": "solar_requested_by",
			},
			{
				"fieldname": "solar_project",
				"fieldtype": "Link",
				"label": "Project",
				"options": "Solar Project",
				"insert_after": "solar_col_1",
			},
			{
				"fieldname": "solar_car",
				"fieldtype": "Link",
				"label": "Car",
				"options": "Car",
				"insert_after": "solar_project",
			},
			{
				"fieldname": "solar_bom",
				"fieldtype": "Link",
				"label": "From BOM",
				"options": "BOM",
				"insert_after": "solar_car",
				"read_only": 1,
			},
			{
				"fieldname": "solar_repair",
				"fieldtype": "Link",
				"label": "Repair",
				"options": "Car Repair",
				"insert_after": "solar_bom",
			},
			{
				"fieldname": "solar_competition",
				"fieldtype": "Link",
				"label": "Competition",
				"options": "Competition",
				"insert_after": "solar_repair",
			},
			{
				"fieldname": "solar_reorder_point",
				"fieldtype": "Link",
				"label": "Reorder Point",
				"options": "Reorder Point",
				"insert_after": "solar_competition",
				"read_only": 1,
			},
			{
				"fieldname": "solar_order_section",
				"fieldtype": "Section Break",
				"label": "Approval, order and receipt",
				"insert_after": "solar_reorder_point",
			},
			{
				"fieldname": "solar_approver",
				"fieldtype": "Link",
				"label": "Approved By (owns the order)",
				"options": "User",
				"insert_after": "solar_order_section",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_approved_on",
				"fieldtype": "Datetime",
				"label": "Approved On",
				"insert_after": "solar_approver",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_estimated_total",
				"fieldtype": "Currency",
				"label": "Estimated Total",
				"insert_after": "solar_approved_on",
				"read_only": 1,
			},
			{
				"fieldname": "solar_col_2",
				"fieldtype": "Column Break",
				"insert_after": "solar_estimated_total",
			},
			{
				"fieldname": "solar_supplier",
				"fieldtype": "Link",
				"label": "Ordered From",
				"options": "Supplier",
				"insert_after": "solar_col_2",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_order_number",
				"fieldtype": "Data",
				"label": "Order Number",
				"insert_after": "solar_supplier",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_receipt",
				"fieldtype": "Attach",
				"label": "Receipt",
				"insert_after": "solar_order_number",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_purchase_order",
				"fieldtype": "Link",
				"label": "Purchase Order",
				"options": "Purchase Order",
				"insert_after": "solar_receipt",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "solar_col_3",
				"fieldtype": "Column Break",
				"insert_after": "solar_purchase_order",
			},
			{
				"fieldname": "solar_paid_by",
				"fieldtype": "Select",
				"label": "Paid By",
				"options": "Team\nMember (reimbursement)",
				"default": "Team",
				"insert_after": "solar_col_3",
				"description": "Members are discouraged from buying things themselves.",
			},
			{
				"fieldname": "solar_reimburse_to",
				"fieldtype": "Link",
				"label": "Reimburse",
				"options": "User",
				"insert_after": "solar_paid_by",
				"depends_on": "eval:doc.solar_paid_by=='Member (reimbursement)'",
			},
			{
				"fieldname": "solar_reimbursement_status",
				"fieldtype": "Select",
				"label": "Reimbursement",
				"options": "\nRequested\nReimbursed",
				"insert_after": "solar_reimburse_to",
				"depends_on": "eval:doc.solar_paid_by=='Member (reimbursement)'",
				"allow_on_submit": 1,
			},
		],
		"Material Request Item": [
			{
				"fieldname": "solar_in_stock",
				"fieldtype": "Float",
				"label": "In Stock When Requested",
				"insert_after": "qty",
				"read_only": 1,
			},
		],
		"Purchase Order": [
			{
				"fieldname": "solar_material_request",
				"fieldtype": "Link",
				"label": "Purchase Request",
				"options": "Material Request",
				"insert_after": "supplier",
				"read_only": 1,
			},
			{
				"fieldname": "solar_budget_line",
				"fieldtype": "Link",
				"label": "Budget Line",
				"options": "Budget Line",
				"insert_after": "solar_material_request",
				"read_only": 1,
			},
			{
				"fieldname": "solar_receipt",
				"fieldtype": "Attach",
				"label": "Receipt",
				"insert_after": "solar_budget_line",
			},
		],
		"Stock Entry": [
			{
				"fieldname": "solar_section",
				"fieldtype": "Section Break",
				"label": "UBC Solar",
				"insert_after": "stock_entry_type",
				"collapsible": 1,
			},
			{
				"fieldname": "solar_source",
				"fieldtype": "Select",
				"label": "Reason",
				"options": STOCK_SOURCES,
				"insert_after": "solar_section",
			},
			{
				"fieldname": "solar_car",
				"fieldtype": "Link",
				"label": "Car",
				"options": "Car",
				"insert_after": "solar_source",
			},
			{
				"fieldname": "solar_reference_doctype",
				"fieldtype": "Link",
				"label": "From",
				"options": "DocType",
				"insert_after": "solar_car",
				"read_only": 1,
			},
			{
				"fieldname": "solar_reference_name",
				"fieldtype": "Dynamic Link",
				"label": "Record",
				"options": "solar_reference_doctype",
				"insert_after": "solar_reference_doctype",
				"read_only": 1,
			},
		],
		"Batch": [
			{
				"fieldname": "solar_expiry_notified",
				"fieldtype": "Check",
				"label": "Expiry Warning Sent",
				"insert_after": "expiry_date",
				"read_only": 1,
				"no_copy": 1,
			},
		],
	}


def get_property_setters():
	"""(doctype, fieldname, property, value, property_type)"""
	return [
		# A blank item code generates a team part number (Make) or uses the MPN (Buy).
		("Item", "item_code", "reqd", "0", "Check"),
		(
			"Item",
			"item_code",
			"description",
			"Leave blank: parts the team makes get the next team number, bought parts use the manufacturer part number.",
			"Text",
		),
		# Field-level history on BOMs ("edits to drafts are logged field by field").
		("BOM", None, "track_changes", "1", "Check"),
		("Item", None, "track_changes", "1", "Check"),
		("Material Request", "material_request_type", "default", "Purchase", "Text"),
	]


def apply():
	create_custom_fields(get_custom_fields(), ignore_validate=True, update=True)
	for doctype, fieldname, prop, value, prop_type in get_property_setters():
		make_property_setter(
			doctype,
			fieldname,
			prop,
			value,
			prop_type,
			for_doctype=fieldname is None,
			validate_fields_for_doctype=False,
		)
