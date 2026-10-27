# CLAUDE.md

Context for Claude Code sessions. Claude doesn't remember between sessions, so
this file, `README.md` and `docs/` carry the context.

- What this is: UBC Solar's ERP, a Frappe custom app (`ubc_solar`) on ERPNext v16.
  Read `docs/PLAN.md` (what the team needs) and `docs/DESIGN.md` (how it maps onto
  ERPNext) first.
- The repo root is the Frappe app (`bench get-app` installs it). Modules, one per
  section: `cars`, `solar_inventory`, `team`, `money`, `sponsors`, `recruitment`,
  `solar_automation` (Connected Tools), `solar_maintenance` (ERP Maintenance).
- Never modify ERPNext or Frappe source. Fields on ERPNext doctypes live in
  `ubc_solar/setup/custom_fields.py`; workflows in `setup/workflows.py`; extra
  permissions on ERPNext doctypes in `setup/permissions.py`. All are applied on
  install and every migrate.
- Doctype, workspace, sidebar, number card, report and print format JSON files are
  the source of truth. After changing one, bump its `modified` timestamp or
  `bench migrate` won't re-import it.
- Integrations run inside the app as background/scheduled jobs and are off until
  configured in Solar Settings. Wrap outside calls in `solar_automation.log.tracked`
  (background jobs only: it rolls back on failure).
- Prefer ERPNext's built-in doctypes when they fit a student team; the reasons for
  each custom doctype are in `docs/DESIGN.md`.
- Tests: `bench --site test.localhost run-tests --app ubc_solar` on a separate test
  site. Add tests for new flows under `ubc_solar/tests/`.
- Don't put member personal data or secrets in the repo.
