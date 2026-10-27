# UBC Solar ERP

UBC Solar's operations system: one linked database for parts, BOMs, inventory,
purchasing, budget, sponsors, and recruitment, built on
[ERPNext](https://frappe.io/erpnext) (Frappe Framework, version 16).

**Status:** pre-prototype. The plan was presented to the Captain and Electrical
Exec on 2026-10-26; the feedback was "show us a prototype." Next milestone is a
working prototype for DR1.

## Docs

| File | What it is |
| --- | --- |
| [docs/PLAN.md](docs/PLAN.md) | Condensed version of the full operations-system plan |
| [docs/FEEDBACK-2026-10-26.md](docs/FEEDBACK-2026-10-26.md) | What the walkthrough meeting asked for |
| [docs/OPEN-QUESTIONS.md](docs/OPEN-QUESTIONS.md) | Decisions needed before and during the build |
| [CLAUDE.md](CLAUDE.md) | Context for Claude Code sessions working on this repo |

## Planned layout

```
apps/ubc_solar/      Frappe custom app: custom doctypes, fields, workflows, fixtures
services/            Things that run alongside the ERP (BOM import, Slack bot, wiki refresh)
deploy/              Docker Compose for local prototype and hosting config
docs/                Plan, decisions, how-tos
```

Rule from the plan: never edit ERPNext's own code. Every customization lives in
the custom app so upgrades stay clean.
