# CLAUDE.md

Context for Claude Code sessions. Claude doesn't remember between sessions, so
this file and `docs/` carry the context.

- What this is: UBC Solar's ERP on ERPNext v16 / Frappe. Read `docs/PLAN.md` first.
- Never modify ERPNext or Frappe source. All customization goes in the custom app
  under `apps/ubc_solar/` (doctypes, custom fields, workflows, exported fixtures).
- Outside services (BOM import, Slack bot, wiki refresh) talk to the ERP over its
  REST API and live in `services/`.
- Prefer ERPNext's built-in doctypes (Item, BOM, Stock Entry, Warehouse, Material
  Request, Purchase Order, Asset, Quality Inspection, Employee, Job Applicant, Lead)
  before inventing new ones.
- Don't put member personal data or secrets in the repo.
