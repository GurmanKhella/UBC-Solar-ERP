# Plan (condensed)

Source: "UBC Solar Operations System: From Today's Workflow to an ERP" (62-page
doc + slides). This is the short version for building against.

## Where things go

- Record you track (part, BOM, purchase, sponsor, applicant) → ERP
- Knowledge you explain → Wiki
- Task or status update → Monday
- File you work on (project docs, procedures, test write-ups) → Google Drive
- Design data → SolidWorks/3DEXPERIENCE, Altium, GitHub
- Conversation → Slack (discussion about one record goes in that record's comments)

## Eight sections

**5A Cars.** Competition → car revision (V3 Brightside, V4 Cascadia, V5 TBD) →
subsystems (Aeroshell, Chassis, Vehicle dynamics, Battery, Power and Signals,
plus Vehicle harnesses) → projects → parts. Each project has one BOM, imported
from Altium/SolidWorks exports, reviewed by its owner, then approved (approval
turns "buy" lines into purchase requests). One home per item. Approved BOMs are
versioned. Manufacturing package per subsystem per car (manufacturing BOM, tools,
quality checks, time; procedure lives in Drive). Harnesses are projects with
From/To projects and a category. Vehicle BOM rolls up everything. Car status:
in design → building → active → retired. Repairs are records against car +
subsystem + project. Competitions hold the car revision, a support BOM, logistics.

**5B Inventory.** Stock is never typed in; it's the sum of transactions
(receipt, issue/QR scan, build, transfer, reconciliation). Location tree mirrors
the workshop. Consumables are only reordered (two-bin or reorder card scan →
purchase request). Perishables carry expiry. Equipment is a separate list with
category, location, condition, and checkout for expensive items.

**5C Team.** Captain → Execs (Electrical, Mechanical, Business) → nine subteams
(Power & Signals, Battery Management, Embedded, Strategy, Aeroshell, Structures,
Dynamics, Battery Mech, Business). Roles: Captain, Exec, Lead, Senior Design
Member, Member, Alumni (view-only), Administrator. Open by default; protected
areas are manufacturing packages, recruitment, attendance. Login by personal
email / Google. Each user linked to Slack. Offboarding checklist.

**5D Money.** Every purchase approved once (BOM approval counts). Approver
orders, attaches receipt, marks received → stock up, requester pinged. Budget
follows fundraising: minimum target, raised, pledged, committed, spent,
available = raised − spent − committed. Rolls up subteam → division → team.

**5E Sponsors.** CRM rebuilt in ERPNext: contacts, history, donations (money and
parts; donated parts go into stock), follow-ups, files, campaigns.

**5F Recruitment.** Cycles → openings (with challenge) → applications → interviews
→ decision; accepted applicant becomes a Member user. Execs and Captain only.

**5G Automation.** Slack notifications (BOM ready, approved/sent back, purchase
to order, parts arrived) with @mentions in channels, plus `/erp part|bom|budget`
lookup bot. New project → Drive doc + Monday item created with the same name and
cross-links. Wiki "current car" page refreshed from the ERP; end-of-car snapshot.
Failure alerts to a maintainers' channel.

**5H Maintenance.** ERPNext v16 (supported to end of 2029), upgraded one major
version at a time via a staging copy. Daily off-server backups. Two Embedded
maintainers plus a Captain backup admin. All custom code in this repo.

## Launch

Decide (hosting, part numbering, subsystem leads/projects) → build + prepare the
workshop in parallel → train → launch everything at once, April or June.
