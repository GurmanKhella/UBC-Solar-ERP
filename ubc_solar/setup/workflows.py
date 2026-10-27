"""The two approval workflows from the plan, built on Frappe's Workflow.

The Solar Approver role decides who sees the Approve / Reject / Send Back buttons;
the server also checks scope from the person's Team Position (own subteam, own
division, or everything) plus their "Also Approves For" subteams.

Created once; after that the workflows are edited in the ERP (Workflow list).
"""

import frappe

APPROVERS = ["Solar Approver"]

STATE_STYLES = {
	"Draft": "",
	"Ready for Review": "Warning",
	"Sent Back": "Danger",
	"Pending Approval": "Warning",
	"Approved": "Success",
	"Rejected": "Danger",
	"Ordered": "Primary",
	"Received": "Success",
	"Cancelled": "Inverse",
}

ACTIONS = ["Mark Ready for Review", "Approve", "Send Back", "Request Approval", "Reject", "Revise", "Cancel"]

BOM_REVIEW = {
	"workflow_name": "BOM Review",
	"document_type": "BOM",
	"states": [
		("Draft", 0, ["Solar Member"]),
		("Ready for Review", 0, ["Solar Member"]),
		("Sent Back", 0, ["Solar Member"]),
		("Approved", 1, APPROVERS),
		("Cancelled", 2, ["System Manager"]),
	],
	"transitions": [
		("Draft", "Mark Ready for Review", "Ready for Review", ["Solar Member"]),
		("Sent Back", "Mark Ready for Review", "Ready for Review", ["Solar Member"]),
		("Ready for Review", "Approve", "Approved", APPROVERS),
		("Ready for Review", "Send Back", "Sent Back", APPROVERS),
		("Approved", "Cancel", "Cancelled", APPROVERS),
	],
}

PURCHASE_APPROVAL = {
	"workflow_name": "Purchase Approval",
	"document_type": "Material Request",
	"states": [
		("Draft", 0, ["Solar Member"]),
		("Pending Approval", 0, ["Solar Member"]),
		("Rejected", 0, ["Solar Member"]),
		("Approved", 1, APPROVERS),
		("Ordered", 1, APPROVERS),
		("Received", 1, APPROVERS),
		("Cancelled", 2, ["System Manager"]),
	],
	"transitions": [
		("Draft", "Request Approval", "Pending Approval", ["Solar Member"]),
		("Draft", "Approve", "Approved", APPROVERS),
		("Pending Approval", "Approve", "Approved", APPROVERS),
		("Pending Approval", "Reject", "Rejected", APPROVERS),
		("Rejected", "Revise", "Draft", ["Solar Member"]),
		("Approved", "Cancel", "Cancelled", APPROVERS),
	],
}


def apply():
	for state, style in STATE_STYLES.items():
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": style}).insert(
				ignore_permissions=True
			)
	for action in ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)
	for spec in (BOM_REVIEW, PURCHASE_APPROVAL):
		if not frappe.db.exists("Workflow", spec["workflow_name"]):
			make_workflow(spec)


def make_workflow(spec):
	"""Create (or, from a patch, rebuild) a workflow. Normal migrates never call this for an
	existing workflow, so changes made in the ERP's Workflow screen stay."""
	if frappe.db.exists("Workflow", spec["workflow_name"]):
		doc = frappe.get_doc("Workflow", spec["workflow_name"])
		doc.states = []
		doc.transitions = []
	else:
		doc = frappe.new_doc("Workflow")
		doc.workflow_name = spec["workflow_name"]
	doc.document_type = spec["document_type"]
	doc.workflow_state_field = "workflow_state"
	doc.is_active = 1
	doc.send_email_alert = 0
	for state, docstatus, roles in spec["states"]:
		for role in roles:
			doc.append("states", {"state": state, "doc_status": str(docstatus), "allow_edit": role})
	for state, action, next_state, roles in spec["transitions"]:
		for role in roles:
			doc.append(
				"transitions",
				{
					"state": state,
					"action": action,
					"next_state": next_state,
					"allowed": role,
					"allow_self_approval": 1,
				},
			)
	doc.flags.ignore_permissions = True
	doc.save()
