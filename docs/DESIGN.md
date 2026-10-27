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
  background jobs and scheduled jobs, configured in **Solar Settings**. Each one
  is off until its credentials are entered, and every failure is logged and
  posted to the maintainers' Slack channel.

## Roles

Positions live on **Team Member**; saving a member sets the user's roles.

| Position | Frappe roles given |
| --- | --- |
| Captain | Solar Captain + Solar Member + ERPNext working roles |
| Exec | Solar Exec + Solar Member + ERPNext working roles |
| Subteam Lead | Solar Lead + Solar Member + ERPNext working roles |
| Senior Design Member | Solar Senior Designer + Solar Member + ERPNext working roles |
| Member | Solar Member + ERPNext working roles |
| Alumni | Solar Alumni (read-only) |
| Administrator (maintainers) | System Manager + Solar Admin (in addition to their position) |

"ERPNext working roles" = Stock User, Manufacturing User, Purchase User, Item
Manager, Quality Manager, so the open-by-default rule holds for built-in
doctypes. Scope rules that roles can't express (a Lead approves only for their
own subteam, an Exec only for their division) are enforced in server code.

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
| Labels | Print formats with QR codes for locations, equipment, reorder cards. |

## 5C Team

**Division**, **Subteam**, **Team Member** (custom). ERPNext Employee is not used:
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
| Budget | **Solar Budget** (season/car, minimum target = sum of lines), **Budget Line** (subteam, amount, must-have/nice-to-have, owner), **Funding Entry** (grants, events, other; pledged or received). Sponsor money comes from Sponsor Donations. Committed = approved, not ordered; Spent = ordered; Available = raised − spent − committed. |
| Reimbursements | Fields on the purchase request (paid by member, reimbursement status). |

## 5E Sponsors

**Sponsor** (custom; ERPNext Customer/Lead are sales concepts) with contacts
(built-in Contact, linked), interaction log, follow-up date and owner,
attachments. **Sponsor Donation** (money/parts/service, pledged/received; parts
go into stock linked to the donation). **Outreach Campaign** with materials.

## 5F Recruitment

**Recruitment Cycle**, **Recruitment Opening** (challenge instructions and
files; copy from a previous opening), **Applicant** (public web form with data
disclosure), **Applicant Interview** (notes, rating). Accepting an applicant
creates their user and Team Member. Execs and Captain only. (HRMS is not
installed; its job applicant flow assumes employees and payroll setup.)

## 5G Automation

Slack notifications (channel + @mentions), `/erp` slash command, Drive doc
creation and rename sync, Monday item creation and rename sync, Wiki.js
"current car" page and end-of-car snapshot, escalation of stale approvals,
failure alerts. All in `ubc_solar/integrations/`.

## 5H Maintenance

`scripts/backup.sh` (daily backup copied off the server), README sections for
the maintenance routine, upgrades via a staging copy, and starting a new car
("Start new car" sets up subsystem packages and the budget).
