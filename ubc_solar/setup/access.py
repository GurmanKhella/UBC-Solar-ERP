"""Who can see and do what: roles, Role Profiles and team positions.

Everything here is starting data. It is created once (install, or a new item in a
later release) and never overwritten, so the team changes access in the ERP itself:

- Team > Positions: each position links a Role Profile and sets its approval and
  team-management scope.
- Role Profile (open it from a position): the roles everyone in that position gets.
- Team Member > Extra Access: more Role Profiles for one person.
- Role Permissions Manager: what each role can read, edit, create or delete.
"""

import frappe

# Functional roles. Doctype permissions and workflows refer to these, never to positions.
ROLES = {
	"Solar Member": "Active team member: view, comment and edit almost everything",
	"Solar Alumni": "Former member: view only",
	"Solar Approver": "Sees Approve / Reject / Send Back on purchases and BOMs (scope comes from the position)",
	"Solar Recruitment": "Recruitment cycles, openings, applicants and interviews",
	"Solar Attendance": "Attendance notes",
	"Solar Manufacturing Editor": "Edits manufacturing packages and stages",
	"Solar Budget Manager": "Edits budgets, budget lines and funding",
	"Solar Team Manager": "Edits team members (position changes are limited by the position's scope)",
	"Solar Car Manager": "Sets up and retires cars; edits subsystems and harness categories",
	"Solar Access Manager": "Edits positions, divisions and subteams; restricts access with User Permissions",
	"Solar Merch Manager": "Runs the merch store: products, orders, payments",
	"Solar Admin": "ERP maintainer: settings and automation log",
}

# ERPNext's own roles that the team's work needs.
WORKING = ["Stock User", "Manufacturing User", "Item Manager", "Quality Manager"]
ORDERING = ["Purchase User", "Purchase Master Manager", "Stock Manager"]

LEADERSHIP = [
	"Solar Member",
	"Solar Approver",
	"Solar Recruitment",
	"Solar Attendance",
	"Solar Manufacturing Editor",
	"Solar Budget Manager",
	"Solar Team Manager",
	"Solar Car Manager",
	"Solar Access Manager",
	"Solar Merch Manager",
]

PROFILES = {
	"Captain Access": [*LEADERSHIP, *WORKING, *ORDERING],
	"Exec Access": [*LEADERSHIP, *WORKING, *ORDERING],
	"Lead Access": [
		"Solar Member",
		"Solar Approver",
		"Solar Attendance",
		"Solar Manufacturing Editor",
		"Solar Team Manager",
		*WORKING,
		*ORDERING,
	],
	"Senior Designer Access": ["Solar Member", "Solar Manufacturing Editor", *WORKING],
	"Member Access": ["Solar Member", *WORKING],
	"Alumni Access": ["Solar Alumni"],
	# Extra access for one person (Team Member > Extra Access)
	"Recruitment Access": ["Solar Recruitment"],
	"Attendance Access": ["Solar Attendance"],
	"Budget Manager Access": ["Solar Budget Manager"],
	"Merch Manager Access": ["Solar Merch Manager"],
	"Manufacturing Editor Access": ["Solar Manufacturing Editor"],
	"Team Manager Access": ["Solar Team Manager"],
	"Approver Access": ["Solar Approver", *ORDERING],
	"ERP Maintainer Access": ["System Manager", "Solar Admin"],
}

# Added automatically, never chosen by hand
APPROVER_PROFILE = "Approver Access"
MAINTAINER_PROFILE = "ERP Maintainer Access"

# The plan's chain of responsibility (5C).
POSITIONS = [
	{
		"position_name": "Captain",
		"role_profile": "Captain Access",
		"approval_scope": "Everything",
		"manage_scope": "Everything",
		"team_wide": 1,
		"assigned_by": ["Captain", "Exec"],
	},
	{
		"position_name": "Exec",
		"role_profile": "Exec Access",
		"approval_scope": "Own division",
		"manage_scope": "Own division",
		"team_wide": 1,
		"needs_division": 1,
		"assigned_by": ["Captain", "Exec"],
	},
	{
		"position_name": "Subteam Lead",
		"role_profile": "Lead Access",
		"approval_scope": "Own subteam",
		"manage_scope": "Own subteam",
		"needs_subteam": 1,
		"assigned_by": ["Captain", "Exec", "Subteam Lead"],
	},
	{
		"position_name": "Senior Design Member",
		"role_profile": "Senior Designer Access",
		"needs_subteam": 1,
		"assigned_by": ["Captain", "Exec", "Subteam Lead"],
	},
	{
		"position_name": "Member",
		"role_profile": "Member Access",
		"needs_subteam": 1,
		"assigned_by": ["Captain", "Exec", "Subteam Lead"],
	},
	{
		"position_name": "Alumni",
		"role_profile": "Alumni Access",
		"is_alumni": 1,
		"assigned_by": [],
	},
]


def create_roles():
	for role, description in ROLES.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{"doctype": "Role", "role_name": role, "desk_access": 1, "description": description}
			).insert(ignore_permissions=True)


def create_role_profiles():
	for name, roles in PROFILES.items():
		if frappe.db.exists("Role Profile", name):
			continue
		frappe.get_doc(
			{"doctype": "Role Profile", "role_profile": name, "roles": [{"role": r} for r in dict.fromkeys(roles)]}
		).insert(ignore_permissions=True)


def create_positions():
	created = []
	for order, spec in enumerate(POSITIONS, start=1):
		if frappe.db.exists("Team Position", spec["position_name"]):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Team Position",
				"sort_order": order,
				**{k: v for k, v in spec.items() if k != "assigned_by"},
			}
		)
		doc.insert(ignore_permissions=True)
		created.append(spec)
	for spec in created:  # second pass: positions refer to each other
		if spec["assigned_by"]:
			doc = frappe.get_doc("Team Position", spec["position_name"])
			doc.set("assigned_by", [{"position": p} for p in spec["assigned_by"] if frappe.db.exists("Team Position", p)])
			doc.save(ignore_permissions=True)


def create_all():
	create_roles()
	create_role_profiles()
	create_positions()
