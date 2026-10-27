# Design: how the plan maps onto ERPNext

This is the build reference. `docs/PLAN.md` says *what* the team needs; this
file says *which ERPNext pieces* do it and what the `ubc_solar` app adds.

## Ground rules

- ERPNext v16 on Frappe v16. Never edit ERPNext/Frappe code; everything is in
  this app (doctypes, custom fields, property setters, workflows, hooks).
- Use a built-in ERPNext doctype when it does the job without forcing members to
  fill in fields that mean nothing to a student team. Otherwise add a small
  custom doctype. Each choice is listed below.
- One company, "UBC Solar", currency CAD. Perpetual inventory is **off**: stock
  is tracked with values, but no accounting ledger entries are posted. The
  budget (5D) is tracked in this app's own budget doctypes, which is what the
  plan describes (fundraising-based, not a chart of accounts).
- Integrations (Slack, Google Drive, Monday, Wiki.js) run inside the app as
  background jobs and scheduled jobs (the plan's "small services on the server"),
  configured in **Solar Settings**. Each one is off until its credentials are
  entered, and every failure is logged and posted to the maintainers' Slack channel.
- The plan's eight sections are Frappe modules, each with a workspace (home page with
  live numbers) and a sidebar: Cars, Inventory, Team, Money, Sponsors, Recruitment,
  **Connected Tools** (5G; "Automation" is taken by Frappe) and **ERP Maintenance**
  (5H; "Maintenance" is an ERPNext module). **Merch** was added after the plan.
- Configurable without code: what the code ships (roles, access profiles,
  positions, custom fields, workflows, permissions, starting data) is created only
  when missing, so changes made in the ERP are never overwritten by a migrate. This
  replaces the plan's idea of exporting UI settings into the app (5H): the team's
  configuration lives in the database and is covered by the daily backups.

## Roles

Access is built from three layers, all editable in the ERP:

1. **Functional roles** (`setup/access.py`): Solar Member, Solar Alumni, Solar
   Approver, Solar Recruitment, Solar Attendance, Solar Manufacturing Editor, Solar
   Budget Manager, Solar Team Manager, Solar Car Manager, Solar Access Manager,
   Solar Merch Manager, Solar Admin. Doctype permissions and workflows refer only to
   these, never to positions.
2. **Role Profiles** bundle roles: Captain / Exec / Lead / Senior Designer / Member /
   Alumni Access for positions, and single-purpose ones (Recruitment Access, Merch
   Manager Access, ...) for extra access.
3. **Team Position** (custom doctype): links a Role Profile and sets the approval
   scope and team-management scope (None / Own subteam / Own division / Everything),
   which positions may assign it, and whether it needs a subteam or division.

A user's roles are the union of their position's profile, the **Extra Access**
profiles on their Team Member record, Approver Access when their position has an
approval scope or they have **Also Approves For** subteams, and ERP Maintainer Access
when ticked.
Frappe's own `User.role_profiles` holds them, so editing a Role Profile updates
every user that has it.

Scope rules that roles can't express (a Lead approves only for their own subteam,
an Exec only for their division) are enforced in server code (`team/scope.py`),
reading the scopes from the positions.

Changing access is itself limited: Solar Access Manager (Captain, Execs) can edit
Role Profiles and positions, and Leads can edit their subteam's members, but only
with roles they hold themselves (`scope.check_can_grant`,
`team_member.check_role_profile_change`), never on their own record, and "Also
Approves For" only for subteams they approve for. Role Profile is overridden
(`team/role_profile.py`) to apply edits to users immediately instead of Frappe's
queued, document-locking job.

| Starting position | Profile roles | Approves | Changes positions in |
| --- | --- | --- | --- |
| Captain | Member, Approver, Recruitment, Attendance, Manufacturing Editor, Budget/Team/Car/Access Manager + ERPNext working and ordering roles | Everything | Everything |
| Exec | Same as Captain | Own division | Own division |
| Subteam Lead | Member, Approver, Attendance, Manufacturing Editor, Team Manager + working and ordering roles | Own subteam | Own subteam |
| Senior Design Member | Member, Manufacturing Editor + working roles | — | — |
| Member | Member + working roles | — | — |
| Alumni | Alumni (read-only) | — | — |

"Working roles" = Stock User, Manufacturing User, Item Manager, Quality Manager;
"ordering roles" = Purchase User, Purchase Master Manager, Stock Manager.

## 5A Cars

| Plan concept | Implementation |
| --- | --- |
| Car (V4 Cascadia, V5…) and its status | **Car** (custom). Status In Design → Building → Active → Retired. Retired cars and everything linked to them become read-only. Each car gets a vehicle Item. |
| Car revision raced at a competition | A version of the car's **vehicle BOM** (BOM-…-001, -002). Competitions link the BOM version they raced. |
| Subsystem | **Subsystem** (custom master: Aeroshell, Chassis, Vehicle dynamics, Battery, Power and Signals, Vehicle harnesses). Add/rename without code. |
| Project (a designed thing) | **Solar Project** (custom; ERPNext's "Project" name is taken). Belongs to a car, a subsystem and a subteam; has an owner, its part (Item), design revision, links to 3DEXPERIENCE/Altium 365, the Drive doc and the Monday item. A matching ERPNext **Project** is created with the same name (Projects module set up but hidden, as the plan says). |
| Part / part number | ERPNext **Item** + custom fields (make or buy, discipline, manufacturer, MPN, material, vendor, revision, home project). Bought parts use their MPN as the item code; designed parts get a generated team number (default simple style `M-0042-A`, prefixes configurable in Solar Settings). "New revision" makes `-B` from `-A`. |
| Project BOM, versions, revert | ERPNext **BOM**. Draft = not submitted; approved = submitted, fixed version. "Make this version active" button reverts. Field-level change tracking on. |
| BOM review | Workflow **BOM Review**: Draft → Ready for Review → Approved / Sent Back. Approving checks the approver's scope and creates purchase requests for "buy" lines short in stock. |
| CAD import | **BOM Import** (custom): upload an Altium or SolidWorks/3DEXPERIENCE export (CSV/XLSX); it creates missing Items and a draft BOM (multi-level for SolidWorks assemblies) owned by the project owner. |
| Manufacturing package | **Manufacturing Package** (one per car + subsystem) and **Manufacturing Stage** (manufacturing BOM, tools from the equipment list, quality inspection template, step time/people, procedure doc link). Editable by Leads, Execs, Senior Design Members; others read and comment. |
| Quality checks | ERPNext **Quality Inspection Template** (criteria) and **Quality Inspection** (results per build). |
| Recording a build | **Build Record** (custom, simple form) → submits an ERPNext **Stock Entry (Manufacture)** from the BOM. Optional serial numbers. Also used for "car built" against the vehicle BOM. |
| Harness | A Solar Project of type Harness with category, From project and To project. Subsystem is set automatically: same subsystem → that subsystem, different → Vehicle harnesses. "All Harnesses" report. |
| Repair | **Car Repair** (custom): car, subsystem, project, what/why, status, fixed by, parts used (deducted on Fixed), linked purchases. |
| Retire a car | Action on Car: salvage parts back to stock, mark Retired, publish wiki snapshot. |
| Competition | **Competition** (custom): car + BOM version raced, dates, support BOM (spares, tools, chargers, safety, pit/trailer; packing checkboxes; copy from a past competition), travel and planning notes and files. |

## 5B Inventory

| Plan concept | Implementation |
| --- | --- |
| Location tree | ERPNext **Warehouse** tree: Workshop > Electrical Storage / Mechanical Storage > shelves > bins, plus Receiving and Competition Spares. |
| Stock transactions | ERPNext Purchase Receipt (received), Stock Entry (Material Issue / Transfer / Receipt / Manufacture), Stock Reconciliation (recount). Stock is never typed in. |
| QR scanning | `/scan` mobile page. Location QR → items there, Take (issue), Recount (reconciliation), Move. Equipment QR → check out/return/condition. Reorder QR → purchase request. |
| Two-bin and reorder cards | **Reorder Point** (custom): item, method, location, quantity, budget line. Scan creates one purchase request (no duplicates while one is open). |
| Item types | Custom field Inventory Type: Component/Material, Expensive/Long-lead, Small Part, Shop Consumable (non-stock, never counted), Build Material, Perishable. |
| Expensive items counted before reorder | Approving a purchase request with an expensive item warns if it hasn't been recounted recently. |
| Perishables | ERPNext Batch with expiry date, entered once on receipt. Daily job flags batches expiring soon. |
| Low stock flags | ERPNext reorder levels on Item; "Low Stock" report. No scheduled auto-ordering. |
| Equipment | **Equipment** (custom; ERPNext Asset needs purchase accounting and depreciation the team doesn't track) with category, location, condition, tracking level, checkout; **Equipment Checkout** log; "Equipment Needing Attention" report. |
| Recounts by anyone | Team members get create/submit on Stock Reconciliation (normally Stock Manager only). |
| Reorder cards across seasons | A card's budget line is used only while its budget is active; otherwise the active budget's shop supplies line. |
| Labels | Print formats with QR codes for locations, equipment, reorder cards (each QR links to `/scan`). |

## 5C Team

**Division**, **Subteam**, **Team Position**, **Team Member** (custom). ERPNext Employee is not used:
it requires date of birth, gender, joining date and HR setup the team doesn't
need. **Attendance Note** (custom) for absences, visible to Leads, Execs,
Captain. Offboarding is an action on Team Member.

## 5D Money

| Plan concept | Implementation |
| --- | --- |
| Purchase request | ERPNext **Material Request** (type Purchase) + custom fields (project, subteam, budget line, car, competition, repair, source, approver). Workflow **Purchase Approval**: Draft → Pending Approval → Approved / Rejected; then Ordered / Received set automatically. |
| One approval | BOM-generated requests are created already approved by the BOM approver. Others need a Lead (subteam), Exec (division) or Captain. |
| Approver orders | "Mark Ordered" (receipt attachment required) creates and submits the ERPNext **Purchase Order**. Only the approver (or Exec/Captain) can do it. |
| Received | "Mark Received" creates the ERPNext **Purchase Receipt** into each item's shelf, records batch expiry, pings the requester. |
| Budget | **Solar Budget** (season/car, minimum target = sum of lines), **Budget Line** (subteam, amount, must-have/nice-to-have, owner), **Funding Entry** (grants, events, merch sales, other; pledged, received or refunded). The lines a new car's budget starts with are set in Solar Settings > New car. Sponsor money comes from Sponsor Donations. Committed = approved, not ordered; Spent = ordered; Available = raised − spent − committed. |
| Reimbursements | Fields on the purchase request (paid by member, reimbursement status). |

## 5E Sponsors

**Sponsor** (custom; ERPNext Customer/Lead are sales concepts) with contacts
(built-in Contact, linked), interaction log, follow-up date and owner,
attachments. **Sponsor Donation** (money/parts/service, pledged/received; parts
go into stock linked to the donation). **Outreach Campaign** with materials.

## 5F Recruitment

**Recruitment Cycle**, **Recruitment Opening** (challenge instructions and
files; copy from a previous opening), **Applicant**, **Applicant Interview**
(notes, rating). Applicants apply at `/apply`, a small custom page rather than a
generic Web Form, so only published openings are listed and résumés are stored as
private files (guest uploads stay switched off site-wide). The form shows the data
disclosure and requires consent. Accepting an applicant creates their user and Team
Member. Execs and Captain only. (HRMS is not installed; its job applicant flow
assumes employees and payroll setup.)

## 5G Automation

Slack notifications (channel + @mentions, never DMs; also shown in the ERP's
notification bell), `/erp` slash command, Drive doc creation and rename sync,
Monday item creation and rename sync, Wiki.js "current car" page (hourly) and
end-of-car snapshot, daily escalation of approvals waiting too long, failure
alerts. All in `ubc_solar/solar_automation/`.

## 5H Maintenance

`scripts/backup.sh` (daily backup copied off the server), the ERP Maintenance
section and README for the routine, upgrades via a staging copy, and starting a
new car (Car > Actions > Set Up This Car creates the subsystem packages and the
budget).

## Merch (added after the plan)

**Merch Product** (custom): price, optional team price, who can buy (everyone or
team only), pre-orders, a per-order limit, and options (sizes/colours). Each option
is its own ERPNext stock **Item** in the Merch item group, kept in the Merch Stock
location, so restocking is a normal purchase request and counts use the scan page.
**Merch Order** (custom): Placed → Paid → Ready for Pickup → Fulfilled, or
Cancelled. Paying creates a **Funding Entry** (Merch Sales) on the active budget;
handing over posts a Material Issue from the merch location; cancelling marks the
funding Refunded and cancels the stock issue if there was one. The public store is
`/merch` (a custom page like `/apply`): prices come from the server, and the team
price only applies to a logged-in team member or alumni, never from a typed email.
**Merch Settings** (single) holds the store's open/closed switch and texts so merch
managers don't need Solar Settings, which holds the integration secrets. ERPNext's
Selling module (Sales Order, Sales Invoice, POS) isn't used: it needs customers,
price lists and accounting the team doesn't run.
