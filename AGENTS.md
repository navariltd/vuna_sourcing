# AGENTS.md — Vuna Sourcing

Rules for any agent or developer writing code in this repository. They describe how the code is already written. Follow them unless the user explicitly says otherwise for a specific change.

## What this app is

A Frappe v16 / ERPNext app with two front doors:

- **Desk** (staff: Purchase, Sales and Accounts users) extends ERPNext doctypes such as Request for Quotation, Supplier Quotation, Sales Order and Sales Invoice. It also adds the app's own doctypes: Party Onboarding Request, Request for Quotation Award, RFQ Opening Committee, RFQ Bid Log, Credit Note Request and Sourcing Settings.
- **Portal** (`/vuna-sourcing`, a Vue 3 + frappe-ui SPA) lets suppliers and customers apply, bid on RFQs, quote, order, view invoices and statements, and raise credit note requests. Portal users are linked to Supplier and Customer records through the `Portal User` child table, and one user can act for several parties.

## Repository map

| Path | What lives there |
|---|---|
| `vuna_sourcing/hooks.py` | Permission hooks, doc_events, overrides, scheduler. Read it before touching any ERPNext doctype. |
| `vuna_sourcing/api/response.py` | `ApiResponse` envelope (ok, status, message, data). |
| `vuna_sourcing/api/portal.py` | Session, `get_current_user`, `get_linked_parties`, `check_party_access`. |
| `vuna_sourcing/api/permission.py` | Role constants (`DESK_ROLES`, `PORTAL_ROLES`), app permission. |
| `vuna_sourcing/api/transactions/` | Portal endpoints by area: `supplier.py`, `customer.py`, `customer_orders.py`, `credit_requests.py`, `open_bid.py`, `sealed_bid.py`, `award.py`, `bidding.py`. |
| `vuna_sourcing/api/transactions/common.py` | Shared helpers: `party_scope`, `my_parties`, `owned_document`, `find_documents`, `page_of`, `empty_page`, `safe_html`, `as_administrator`, statement helpers. |
| `vuna_sourcing/api/transactions/access.py` | `has_permission` and `permission_query_conditions` used by hooks for portal doctypes. |
| `vuna_sourcing/overrides/server/` | doc_event handlers and dashboard overrides for ERPNext doctypes. |
| `vuna_sourcing/overrides/client/` | Desk form scripts (`doctype_js`). |
| `vuna_sourcing/vuna_sourcing/doctype/` | App doctypes. Controllers hold business rules and desk `@frappe.whitelist()` methods. |
| `vuna_sourcing/vuna_sourcing/custom/` | Custom fields and property setters on ERPNext doctypes (`sync_on_migrate: 1`). |
| `vuna_sourcing/setup/app_setup.py` | `after_install`, the only place for install-time setup. |
| `vuna_sourcing/setup/test_setup.py` | `before_tests`. Mirror any setup tests depend on. |
| `vuna_sourcing/tests/` | Integration tests, `SourcingFixtures`, `make_test_user`. |
| `portal/src/data/` | One file per area: TypeScript types that mirror server payloads, status labels and themes, resources and fetch helpers. |
| `portal/src/pages/`, `portal/src/components/` | Pages and shared components (`PageContainer`, `EmptyState`, `ListFilters`, `LinkSelect`, `PrintButton`, `PortalShell`, …). |
| `portal/src/composables/` | `useIsMobile`, `useRealtime`, `usePartySwitch`, `useCountdown`, `useOrderDraft`. |

## Commands

```bash
# from the bench root (…/v-16); the local site is "sourcing" on port 8001
bench --site sourcing run-tests --app vuna_sourcing
bench --site sourcing run-tests --module vuna_sourcing.tests.test_credit_note_requests
bench --site sourcing migrate           # after editing doctype or custom JSON

# from the app root
pre-commit run --all-files              # ruff, ruff-format, prettier, eslint, json/yaml checks

# from portal/
npm run build                           # vue-tsc type-check + vite build into vuna_sourcing/public/frontend
npm run dev                             # dev server, proxies socket.io to the bench
```

A change is not done until the tests for the area you touched pass and `npm run build` finishes with no type errors.

## Hard rules

1. **No code comments.** No `#` or `//` notes, JSDoc, docstrings on helpers or HTML comments in `.vue` templates. Put the explanation in names and structure, and put the reasoning in the commit message. The one exception is test classes and test methods: each gets a one-line docstring, because Frappe prints it as the test description.
2. **No migration patches.** Never add to `patches.txt` or `vuna_sourcing/patches/`. Install-time work goes in `setup/app_setup.py:after_install`, mirrored in `setup/test_setup.py:before_tests` when tests need it. The app is pre-release, so sites are reinstalled rather than migrated. If a change won't reach existing sites until reinstall, say so.
3. **Every portal endpoint returns `ApiResponse`.** Use `ApiResponse.success(message, data)` or `ApiResponse.error(message, data)` and annotate the return type (`-> ApiResponse[dict]`). Use `ApiResponse.error` for an expected business outcome the UI should show inline. Use `frappe.throw(...)` for bad input, and `frappe.throw(..., frappe.PermissionError)` for access failures. Some older endpoints (`get_session`, `get_party`) still return bare dicts. Don't copy them.
4. **Constants, not string literals,** for doctype names, field names and statuses. Define them once at the top of the owning module (`DOCTYPE = "Credit Note Request"`, `RETURNED = "Returned for Correction"`) and import them.
5. **Demo and test data use generic businesses and placeholder people** ("Greenfield Traders Ltd", "Prime Supplies Ltd", Jane Doe or John Doe), never real customer accounts or real people's emails.
6. **Custom fields may link only to doctypes that exist on every site where this app is installed:** Frappe, ERPNext or this app. Install validates every Link on the target doctype. A Link to another app's doctype fails on a fresh site with "Options must be a valid DocType".

## Authorization: check on every access

The portal runs as low-privilege website users. Every whitelisted method is a public endpoint. Assume the caller has edited the request, and check access on the server in every function, every time. The UI hiding a button is not a check.

### The checks, in order

1. **Signed in.** `get_current_user()` (from `api/portal.py`) throws for Guest. Use `allow_guest=True` only for signup and the dev-mode context endpoint.
2. **Feature enabled.** If Sourcing Settings gates the feature, call the area's `ensure_enabled()` first, before any read or write. Do it in GET endpoints that build forms too, not only in submit. Model it on `credit_requests.ensure_enabled`, which throws `frappe.PermissionError` with a plain message. Read settings with `frappe.db.get_single_value` or `frappe.get_cached_doc("Sourcing Settings")`.
3. **Party scope.** Never trust a `customer` or `supplier` argument. Pass it through `party_scope(party_type, party)`, which calls `check_party_access`, or through `check_party_access` directly. When no party is given, `party_scope` returns all the user's parties of that type. Handle an empty list with `empty_page(...)` or an empty result, never with an unfiltered query.
4. **Role.** Portal roles are `Supplier`, `Customer` and `Sourcing Portal User`, gated per party type through `PARTY_ROLE`. Desk actions use `frappe.only_for(ROLES, message=True)` plus `doc.check_permission("submit" | "write" | ...)`, as `CreditNoteRequest.check_reviewer` does.
5. **Ownership in the query itself.** Load a record by filtering on both its name and the caller's parties in one query, then load the doc: `owned_document(doctype, name, filters)`, `own_request(name, customers)`, `own_invoice(name, customer)`. Don't load by name and compare afterwards. A record that doesn't exist and one that belongs to someone else must give the same error ("This document does not belong to you.") so the response doesn't reveal that other parties' records exist.
6. **State.** Check the document's current status before acting ("Only a request we sent back for changes can be resubmitted."), after taking the lock described under Concurrency.
7. **Disabled records.** Parties carry `disabled`. A disabled party may read its history but must not start new transactions. Check this when you add any create or submit endpoint. Users are filtered by `enabled` in Frappe itself, so don't add separate session checks for that.

### Using elevated access

- Use `doc.flags.ignore_permissions = True` or `.insert(ignore_permissions=True)` only after steps 1–6 have passed in the same function, and only on the document you just verified.
- `as_administrator()` exists only for ERPNext reports that refuse portal users (the receivables statement). Keep the `with` block as small as possible, pass already-scoped `parties`, and never return unfiltered rows from inside it.
- Desk `@frappe.whitelist()` methods on controllers still check permission: `frappe.has_permission(DOCTYPE, "read", doc=name, throw=True)` or `doc.check_permission(...)`.

### Permission hooks

- `hooks.py` sends every doctype in `PORTAL_DOCTYPES` through `access.is_own_document` and `access.own_documents_condition`. When the portal starts exposing a new ERPNext doctype, add it to both tuples (in `hooks.py` and `access.py`) and to `party_filters`. Staff detection (`is_staff`) is based on the user's DocPerms, not role names. Keep it that way.
- SQL built for `permission_query_conditions` must quote values with `frappe.db.escape` and backtick table and column names, as `visible_quotes_condition` does. Never put user input into these strings.

### Input handling

- Mutating endpoints use `@frappe.whitelist(methods=["POST"])`.
- Type-annotate every parameter. Frappe v16 validates them.
- Parse JSON arguments defensively: check the type, cap list lengths (`MAX_LINES`), reject duplicates, use `math.isfinite` and range-check numbers, and trim strings with a length cap (`DETAILS_LENGTH`). See `credit_requests.requested_lines`.
- Compute derived values (amounts, percentages, totals) on the server. Never store a total the client sent.
- Sanitize HTML that leaves the server with `safe_html` (`common.py`). Escape user text placed inside email or notification bodies with `escape_html`.

## Concurrency and race conditions

Two portal users for the same party, a supplier double-clicking "Place bid", or a reviewer approving while the customer withdraws are all normal traffic here.

- **Lock before you check state and change it.** Load mutable records with `frappe.get_doc(DOCTYPE, name, for_update=True)` after the ownership check, then check state on the locked copy. `customer_orders.locked_portal_order` and `locked_draft` show the pattern. A status check on an unlocked doc followed by a write is a race.
- **"Only one X per Y" rules** (one open credit request per invoice, one draft credit note per request, one quote per supplier per RFQ) are check-then-insert races. Lock the parent row (`frappe.get_doc(PARENT, name, for_update=True)` or `frappe.db.get_value(PARENT, name, "name", for_update=True)`) before the existence check. Where the data model allows it, back the rule with a unique index.
- **State transitions** (approve, reject, return, withdraw, resubmit, award, open) take the lock, re-check the status they expect and then write. The status checks in `validate_review_state` are only safe after a lock.
- **Never `frappe.db.commit()` in request code.** Frappe commits at the end of the request, so one failure rolls everything back. Commits belong only in setup and test fixtures (marked `# nosemgrep`).
- **Side effects run after commit:** `frappe.publish_realtime(..., after_commit=True)` (as `RFQBidLog.after_insert` does), `frappe.enqueue(..., enqueue_after_commit=True)` and email through `frappe.sendmail` (queued). Wrap notification failures in `try/except` with `self.log_error(...)` so a mail problem can't roll back a business action.
- **Immutable logs** (`RFQ Bid Log`) throw in `validate` when they aren't new and in `on_trash`. Keep audit records append-only.
- **Scheduler jobs** (`award.refresh_pending_selection`) must be idempotent and lock each document they change, because they can overlap with user actions.
- **Prefer `doc.save()` to `db_set`** so validation and the `modified` timestamp check run. Use `db_set` only for status or audit fields after submit, as `record_review` does.
- **The client also guards against double submits:** disable the button while its request runs (`:loading` on frappe-ui `Button`). This is UX only. The server lock is the real protection.

## Queries and the N+1 problem

- **No queries inside loops over rows.** Collect names and fetch children or related rows once with `("in", names)`, then group them in a dict. `credit_requests.get_creditable_invoices` is the model: invoices, then all their items in one query, then credited quantities in one query, then open requests in one query. `RFQBidLog.bidder_users` and `common.payments_against` follow the same shape.
- **No `frappe.get_doc` in a loop** for lists or summaries. Use `frappe.get_all` with an explicit `fields` list. Load a full document only for one record you will validate or change.
- **Never let `frappe.get_all` default to `fields=["*"]`.** Request the columns you return. Use `pluck=` for single columns, `as_list=True` plus `dict(...)` for key-value maps, and `distinct=True` when joining child rows.
- **Masters and settings come from cache:** `frappe.get_cached_value("Company", company, "default_currency")` and `frappe.get_cached_doc("Sourcing Settings")`. Don't cache transactional rows.
- **Look for hidden per-row queries.** Helpers like `common.item_description` fall back to a DB read when a field is empty. When you map many rows, prefetch what the fallback needs.
- **Paginate in SQL for anything unbounded.** Existing lists use `find_documents` plus `page_of`, which loads every matching row and slices in Python. That's acceptable only for per-party lists that stay small. For lists that can grow without limit (bid logs, statement lines, all RFQs for a large supplier), pass `limit_start` and `limit_page_length` to `frappe.get_all` and get the total with `frappe.db.count`. Always keep the response shape `{rows, total, start, limit, counts}`.
- **Joins and aggregates** use `frappe.qb` (see `get_linked_parties`) or `frappe.get_all` with child-table fields. Use raw `frappe.db.sql` only when neither works, and always with `%(name)s` parameters, never f-strings.
- **Filter on indexed columns** (`name`, `parent`, link fields, `docstatus`, `customer`, `supplier`). When adding a field you will filter on, set `search_index: 1` in its JSON.
- Before handing over an endpoint that returns a list, count its queries. With 50 rows it should run about the same number of queries as with 5.

## Portal UI (frappe-ui)

The portal should look and behave like one product. Build from what already exists before writing anything new.

### Components

- Use frappe-ui first: `Button`, `Badge`, `FormControl`, `Dialog`, `Alert`, `Spinner`, `TabButtons`, `Dropdown`, `Combobox`, `Tooltip`, `Breadcrumbs`, `FileUploader`, `ErrorMessage`, `toast`, and `ListView` from `frappe-ui/experimental` for tables.
- Then the app's shared components: every page sits in `PageContainer` (title, breadcrumbs, `look`, copy button). Use `EmptyState` for empty lists, `ListFilters` for search and status filters with counts, `LinkSelect` for link pickers and `PrintButton` for printable documents.
- Raw `<button>`, `<input>`, `<select>` or `<table>` only when frappe-ui has no equivalent (for example a whole clickable card). It still needs focus styles, `type="button"` and an accessible label.

### Styling

- Use only frappe-ui's semantic tokens: `text-ink-gray-*`, `bg-surface-*`, `border-outline-*`, and radii such as `rounded-6`. No raw Tailwind palette colors (`text-gray-500`, `bg-blue-100`) and no hex values, so theming and dark mode keep working.
- Use the existing `.card`, `.card-muted` and `.row-interactive` classes from `src/style.css`, and the accent maps in `src/data/accents.ts` (`ACCENTS`, `LOOKS`) for per-document color.
- Icons are Lucide classes (`<i class="lucide-inbox size-5" aria-hidden="true" />`).
- Keep status colors in a `*_STATUS_THEME` map and customer-facing wording in a `*_STATUS_LABEL` map inside the area's `src/data/*.ts` file, then render with `Badge`. A server status like "Returned for Correction" is shown to a customer as "Needs changes".

### Data layer

- Each area has a `src/data/<area>.ts` with an API path constant (`const CREDIT_REQUESTS = "vuna_sourcing.api.transactions.credit_requests"`), TypeScript interfaces that match the server dicts field for field, and `createResource` instances or small `fetchX` and `post` helpers that return `Promise<ApiResponse<T>>`.
- Pages read the envelope's payload: `resource.data?.data`. Branch on `isOk(response)` from `src/types/api.ts`, and show `response.message` from the server rather than writing new error text on the client.
- No `any`. Add the type to the data file when the server shape changes, in the same change.
- The active party comes from `usePortalStore().activeParty`. Pass it as the `customer` or `supplier` argument, and refetch when it changes (`watch([customer, filters], load, { immediate: true })`).
- Live updates go through `useRealtime(event, handler, onReconnect)`. Refetch on reconnect.

### UX standards

- **Every page has four states:** loading (`Spinner` or skeleton), empty (`EmptyState` with a next step), error (`Alert` or `ErrorMessage` with the server message) and data.
- **Mobile is first-class.** Use `useIsMobile()` to show fewer columns (two or three key columns on a phone), stack forms and keep tap targets large. No horizontal page scroll at 375px.
- **Design for scale,** not the happy path. Check how a screen looks with 60+ suppliers, 12+ items, long names and no data at all. Avoid layouts with one column per supplier.
- **Write copy for a non-technical supplier or customer.** Say what happened and what to do next ("Request sent. Our accounts team will review it."). No doctype names, field names or stack traces.
- **Actions:** the primary action is a solid `Button`, and destructive actions ask for confirmation in a `Dialog`. Disable the button while its request runs, and confirm success with `toast` or the returned `message`.
- **Explain unfamiliar features in place.** See `CREDIT_REQUEST_EXPLAINER`.
- Money goes through `money()` and dates through `shortDate()` from `src/data/purchase.ts`.

## Desk UI

- Form scripts live in `overrides/client/<doctype>.js` and are registered in `hooks.py` `doctype_js`. App doctypes keep their JS next to the JSON.
- Call the server with `frappe.call({ method, args })` and read `message.data` from the envelope.
- Use standard Frappe UI: `frm.add_custom_button` grouped under a label, `frappe.ui.Dialog` for inputs, `frm.dashboard.set_headline` and indicators for status, and `frappe.msgprint` / `frappe.show_alert` for feedback. Don't inject custom HTML when a standard control exists.
- Workspace, sidebar and number cards live under `vuna_sourcing/vuna_sourcing/workspace|sidebar|number_card`. A queue a staff member has to act on ("Credit requests to review") gets a number card.

## Doctypes and ERPNext extensions

- Create and edit doctypes as JSON plus controller under `vuna_sourcing/vuna_sourcing/doctype/`. Controllers keep the generated type-annotation block (`export_python_type_annotations = True`).
- Put business rules in the controller (`validate`, `before_submit`, `on_cancel`) so desk and portal enforce the same rules. API modules handle access, input shape and response formatting, then call the controller.
- To extend an ERPNext doctype, add a `doc_events` handler in `overrides/server/` and register it in `hooks.py`. Never edit ERPNext code. New fields go in `vuna_sourcing/vuna_sourcing/custom/<doctype>.json` with `module: "Vuna Sourcing"`.
- Messages are translatable: `_("...").format(...)` with positional `{0}`, `frappe.bold` for emphasis, and `title=` on `frappe.throw` for desk dialogs.

## Tests

- Integration tests live in `vuna_sourcing/tests/test_<area>.py`. The class extends `SourcingFixtures, IntegrationTestCase`, and test users come from `make_test_user([roles], first_name=...)`.
- Name tests as sentences describing behavior (`test_another_customers_invoice_cannot_be_adjusted`) and give each a one-line docstring.
- Every new endpoint gets at least:
  - a test for the main successful path
  - a denial test where another party's user calls it on your record (`frappe.PermissionError`)
  - a test with the feature turned off in Sourcing Settings, if the feature is gated
  - a state test where the action runs on a record in the wrong status
- Run as the portal user with `frappe.set_user(user)` and reset it in `tearDown`. Calling endpoints as Administrator tests nothing about access.
- Fixtures use the `_Test` prefix and generated emails (`@example.com`).

## Git

- Branch from `develop` as `feat/<topic>` or `fix/<topic>`, and open PRs against `develop`.
- Commit subject: `feat(sourcing): <what changed for the user>`, or `fix(sourcing): …`. Put the reasoning in the commit body, since the code carries no comments.

## Checklist before you call a change done

- [ ] Every new or changed whitelisted method: signed-in check, `ensure_enabled` if gated, party scope, ownership in the query, role and state checks, POST for writes, `ApiResponse` return.
- [ ] Writes that depend on current state lock the row (`for_update=True`) before the check.
- [ ] No queries inside row loops, explicit `fields`, cached masters, and SQL-level pagination for unbounded lists.
- [ ] Portal: frappe-ui components and semantic tokens, all four page states, works at 375px and with large data, types updated in `src/data`.
- [ ] Tests cover success, denial for another party, feature-off and wrong-state cases, and they pass.
- [ ] `pre-commit run --all-files` and `npm run build` are clean.
- [ ] No comments, no patches, no real people's data.
