# Open questions

## Needed before the prototype

1. **Prototype scope.** Full eight-section ERP, or a first slice? Suggested
   slice: Inventory (locations, "where is X", stock moves, equipment) + Parts +
   one subsystem's project BOMs imported from real Altium exports + purchase
   request → approve → receive.
2. **Where the prototype runs.** Local Docker (only the builder can use it) or a
   cheap shared host / Frappe Cloud trial so teammates can click through before DR1.
3. **Real data.** Master electrical inventory sheet, an Altium BOM export (and
   the existing BOM export script), bay layout (shelves, crates, bins), equipment
   list, a SolidWorks BOM export.
4. **Part numbering for the prototype.** Use the suggested simple style
   (`M-0042-A` mechanical, `E-0042-A` electrical, auto-generated) as a
   placeholder until the team decides?
5. **People.** Real roster (names, subteams, roles) or placeholder people?
6. **Integrations in the prototype.** Slack bot / notifications, Drive, Monday:
   include or stub? Slack needs a workspace admin to install an app; Drive needs
   a Google service account.
7. **Urgent-purchase path.** How should "buy it now" work: buy first, record and
   approve after, with a dollar cap?
8. **DR1 date.**

## Blocking the real build (from the plan)

- Hosting: Frappe Cloud vs rented VPS
- Part numbering scheme (with the team)
- Each subsystem's lead, projects, manufacturing stages
- Launch date: April or June
- Two Embedded maintainers

## Can default during implementation

Notification → channel mapping, budget structure, must-have vs nice-to-have,
attendance details, label printing, extra bot commands, migration vs fresh start.
