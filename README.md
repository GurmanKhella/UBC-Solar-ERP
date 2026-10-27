# UBC Solar ERP

UBC Solar's operations system: one linked database for parts, BOMs, inventory,
purchasing, budget, sponsors and recruitment. It is a custom app (`ubc_solar`) on
[ERPNext](https://frappe.io/erpnext) version 16 (Frappe Framework v16).

**Status:** built to the plan and running locally. It isn't hosted on a server yet.
See [What's still open](#whats-still-open) for the decisions that come before launch.

The plan this is built from is condensed in [docs/PLAN.md](docs/PLAN.md); how each
part of it maps onto ERPNext is in [docs/DESIGN.md](docs/DESIGN.md).

## The eight sections

| Section | What's in it |
| --- | --- |
| **Cars** | Cars and their status (In Design → Building → Active → Retired), subsystems, projects, part numbers, project BOMs imported from Altium/SolidWorks with review and approval, manufacturing packages and stages, build records with quality checks, harnesses, repairs, competitions and their support BOMs, the vehicle BOM |
| **Inventory** | Stock by location (shelves and bins), QR scan page for phones, recounts, two-bin and reorder cards, perishables with expiry dates, the equipment list with checkout, printable QR labels |
| **Team** | Divisions, subteams, members and positions (which decide roles and approvals), offboarding to Alumni, attendance |
| **Money** | Purchase requests → approval → order (with receipt) → received into stock; the fundraising budget: minimum target, raised, pledged, committed, spent, available |
| **Sponsors** | Sponsor records with contacts and conversation history, money and parts donations, outreach campaigns |
| **Recruitment** | Cycles, openings with technical challenges, the public application form at `/apply`, applicants, interviews, accepting someone straight into the team |
| **Connected Tools** | Slack notifications and the `/erp` lookup command, Google Drive docs, Monday items, the wiki's Current car page and end-of-car snapshots, the automation log |
| **ERP Maintenance** | The maintenance routine, users, permissions, backups |

## Run it locally

You need Linux or macOS with **Python 3.14**, **Node 24** with **yarn**, **MariaDB 10.6+**
(with `utf8mb4` as the server character set) and **Redis**, then
[bench](https://github.com/frappe/bench) (`pip install frappe-bench` or `uv tool install frappe-bench`).
Don't run bench as root.

```bash
bench init frappe-bench --frappe-branch version-16 --python python3.14
cd frappe-bench
bench get-app https://github.com/frappe/erpnext --branch version-16
bench get-app https://github.com/GurmanKhella/UBC-Solar-ERP
bench new-site ubcsolar.localhost --install-app erpnext --admin-password <choose one>
bench --site ubcsolar.localhost install-app ubc_solar
bench use ubcsolar.localhost
bench start
```

Open http://localhost:8000 and log in as `Administrator`. Installing `ubc_solar`
completes ERPNext's setup by itself: the company **UBC Solar** (CAD), the workshop
locations, the three divisions and nine subteams, the six subsystems, harness
categories with their quality checks, the two approval workflows, the roles, and the
cars V4 Cascadia (Active) and V5 (In Design). Change anything that's wrong in the ERP.

If the repo is private, use `bench get-app git@github.com:GurmanKhella/UBC-Solar-ERP.git`
with an SSH key, or clone it into `apps/ubc_solar` and run `bench get-app ubc_solar`.

## First-time setup in the ERP

1. **Team > Members:** add the Captain first (as Administrator), then the Execs, Leads
   and members. Each member gets a login with their personal email, and their position
   sets their access. Tick **ERP Maintainer** for the two Embedded maintainers. The
   Captain should also have a backup admin login.
2. **Sign in with Google** (optional, for Gmail addresses): create an OAuth client in
   Google Cloud with the redirect URI
   `https://<erp address>/api/method/frappe.integrations.oauth2_logins.login_via_google`,
   then add it in the ERP under **Social Login Key** (provider Google). Everyone else
   uses email and password.
3. **Connected Tools > Solar Settings:** check the locations and part-number prefixes,
   and set **ERP Address** once it's hosted (QR labels link to it).
4. **Cars > V5 > Actions > Set Up This Car:** this creates a manufacturing package per
   subsystem and a budget with a line per subteam. Then fill in each subsystem's Leads
   (Cars > Setup > Subsystems) and each budget line's amount (Money > Budgets).
5. **Inventory > Locations:** add shelves and bins under Electrical Storage and
   Mechanical Storage, print their labels (**Print Label** on each location), and add
   two-bin and reorder cards for the consumables.
6. Add projects with owners. Each project gets its part number, and its Drive doc and
   Monday item once those are connected.
7. Do the first full stock count with the scan page: scan each bin and use
   **Count a part into this bin**.

## How the main flows work

- **BOMs.** Export the BOM from Altium or SolidWorks, then use **Import BOM from CAD**
  on the project. The import creates a draft BOM owned by the project owner. The owner
  adds what CAD left out (fabrication, connectors, raw stock, shipping) and uses
  **Actions > Mark Ready for Review**, which @mentions the approvers. An approver
  approves or sends it back. Approving fixes that BOM version and creates an
  already-approved purchase request for the "buy" lines that aren't in stock.
- **Purchases.** Approval goes to the subteam's Lead, the division's Exec or the
  Captain. Whoever approves a purchase owns it:
  - they click **Mark Ordered** with the supplier and receipt;
  - when it arrives they click **Mark Received** and pick the shelf;
  - the parts are added to stock and the requester is pinged.
- **Builds.** **Build Records:** pick the BOM and quantity. The parts and the bins
  they come from fill in automatically; fill in the quality checks and Submit, which
  deducts every part.
- **Scanning.** QR labels open `/scan` on a phone:
  - **bins:** take parts, recount or move them;
  - **equipment:** check it out, return it, or confirm its condition;
  - **reorder cards:** request a reorder, with no duplicates while one is open.
- **Budget.** Money > Budgets shows raised against the minimum target, plus pledged,
  committed, spent and available. Sponsor money goes on the sponsor's record as a
  donation; grants and events go in Funding.
- **Recruitment.** Publish an opening and applicants apply at `/apply`. Execs and the
  Captain review applicants, schedule interviews, and use **Accept and Create Account**.

## Roles

| Position | Can |
| --- | --- |
| Captain | Approve and order any purchase; change any position; see recruitment and attendance; set up and retire cars; restrict access (User Permissions) |
| Exec | Approve and order purchases for their division; change positions in their division; see recruitment and attendance; set up and retire cars; restrict access (User Permissions) |
| Subteam Lead | Approve and order purchases for their subteam; change positions in their subteam; edit manufacturing packages; fill in attendance |
| Senior Design Member | Edit manufacturing packages |
| Member | View, comment on and edit almost everything, including any BOM; request purchases; record builds; scan and recount |
| Alumni | View only |
| ERP Maintainer | Full administrator access (System Manager) |

## Connect the tools

Each tool stays off until it's switched on in **Solar Settings**. Every call is
logged in **Connected Tools > Automation Log**, and failures are posted to the
maintainers' Slack channel.

- **Slack.** Create the app from [docs/slack-app-manifest.yml](docs/slack-app-manifest.yml),
  install it, and paste the bot token and signing secret into Solar Settings > Slack.
  Members are linked to Slack by email automatically.
  - Notifications go to the subteam's channel if it has one (set on the Subteam);
    otherwise to the channel mapped for that event, otherwise the default channel.
  - `/erp part M5 bolt`, `/erp bom BMS`, `/erp budget electrical`, `/erp equipment scope`
    and `/erp project BMS` answer without opening the ERP.
- **Google Drive.** This needs a Google Workspace administrator, once:
  1. Create a service account in Google Cloud.
  2. Enable the Drive and Docs APIs.
  3. Download its JSON key.
  4. Share the Shared Drive with the service account's email.

  Then attach the key in Solar Settings > Google Drive and fill in the folder IDs and
  template doc IDs. Put `{{ERP_LINK}}` in the templates where the ERP link should go.
- **Monday.** Paste an API token and the board ID. Optionally add a Link column for the
  ERP link; without one, the link is posted as an update on the item.
- **Wiki.js.** Create an API key in the wiki's admin area and paste it with the wiki's
  address. The Current car page is refreshed hourly, and the end-of-car snapshot is
  published when a car is retired.

## Maintenance

Embedded maintains the ERP, with two named maintainers each year and the Captain
holding a backup admin login.

| When | What |
| --- | --- |
| Daily (automatic) | `scripts/backup.sh` from cron: database and files copied off the server (see the script header). Backups include the site config, so keep the destination private. |
| Monthly | `bench update --pull` after a backup, then run the tests on a copy; confirm backups are arriving |
| Each term | Offboard members who left (Team Member > **Offboard to Alumni**); review roles; equipment walk-through (Inventory > Equipment Needing Attention) |
| Each summer | Maintainer handover; restore a backup onto a test site; update this README; check https://frappe.io/support-versions; review hosting cost |
| Start of each car | Create the car, then **Set Up This Car** |
| About every 2 years | Major ERPNext upgrade on a staging copy first, testing BOM import, purchasing and approvals, Slack, the lookup bot, the wiki page, and the Drive and Monday connections |

To restore a backup onto a test site:
`bench --site test.localhost restore <database.sql.gz> --with-public-files <files.tar> --with-private-files <private-files.tar>`.

**Upgrade safety.** Never edit ERPNext's or Frappe's code. All customization lives in
this app:
- custom doctypes;
- custom fields and workflows, applied in code on every `bench migrate`;
- extra permissions on ERPNext doctypes, added as Custom DocPerm.

Custom DocPerm means future ERPNext permission changes to Item, BOM, Stock
Reconciliation and similar doctypes won't arrive automatically, so check them after
each major upgrade.

## Development

```
ubc_solar/
  cars/ solar_inventory/ team/ money/ sponsors/ recruitment/   one module per section
  solar_automation/      Slack, Drive, Monday, Wiki.js, notifications, lookup bot
  solar_maintenance/     the ERP Maintenance section
  setup/                 installer, custom fields on ERPNext doctypes, workflows, permissions
  www/                   /scan (phone page) and /apply (application form)
  public/js/             extensions to ERPNext forms (Item, BOM, Material Request, Warehouse)
  tests/                 integration tests
scripts/backup.sh        off-server backups
docs/                    plan, design, Slack app manifest
```

Run the tests on a separate site, never the real one:

```bash
bench new-site test.localhost --install-app erpnext
bench --site test.localhost install-app ubc_solar
bench --site test.localhost set-config allow_tests true
bench --site test.localhost run-tests --app ubc_solar
```

After changing doctypes or fields, run `bench --site <site> migrate`.

## What's still open

These come from the plan's to-do list and are not decided in the code.

- **Hosting.** It runs locally. When it's hosted, set **ERP Address** in Solar Settings
  and schedule `scripts/backup.sh`.
- **Part numbering scheme.** The suggested simple style is in place as a placeholder:
  `M-0042-A` for mechanical, `E-0042-A` for electrical, `A-0042-A` for assemblies, and
  bought parts use their manufacturer part number. Change the prefixes in Solar
  Settings once the team decides.
- **Subsystem leads, projects and manufacturing stages.** These are entered in the ERP.
- **Reimbursement procedure.** Purchase requests have Paid By and reimbursement
  fields; add the team's procedure once it's provided.
- **Where the money sits.** The budget is tracked in the ERP, and no bank or society
  account is connected.
- **Migration.** Existing BOM sheets, the electrical inventory and CRM data aren't
  imported, whether to migrate or start fresh is still to be decided. Inventory gets a
  physical count at launch either way.
