# CLAUDE.md — Vuna Sourcing

@AGENTS.md

The file imported above is the full rulebook for this repo: architecture, authorization, concurrency, queries, UI and tests. Everything below is extra workflow for Claude Code.

## Before writing code

- Read `vuna_sourcing/hooks.py` and the area's existing module (for example `api/transactions/credit_requests.py` together with `portal/src/data/creditRequests.ts`). Copy their shape. `credit_requests.py` is the most recent and most complete example of an endpoint module.
- Search `api/transactions/common.py`, `api/portal.py` and `portal/src/components/` for an existing helper before writing a new one.
- If a request conflicts with a hard rule in AGENTS.md (for example it needs a migration patch, or a Link to another app's doctype), say so and propose the allowed alternative. Don't follow the rule silently or break it silently.

## While writing code

- Match the surrounding code: tabs in Python and Vue, the existing naming style (`own_request`, `requesting_customer`, `ensure_enabled`), and no comments.
- For each whitelisted method you add or change, go through the authorization steps in AGENTS.md one by one, and say in your reply which checks it performs.
- For each write that depends on current state, say where the row lock is taken.
- For each list endpoint, check the query count doesn't grow with the number of rows.

## Verifying UI changes

Render every desk or portal UI change in a real browser before reporting it done:

- The bench serves the `sourcing` site on port 8001 and is usually already running.
- Use playwright-core from the scratchpad with `/usr/bin/google-chrome` and `--host-resolver-rules=MAP sourcing 127.0.0.1`. Log in by calling `fetch('/api/method/login')` inside the page, because Node-side requests can't resolve the host.
- Take screenshots at desktop width and at 375px, with a large-data case (60+ suppliers, 12+ items) as well as the empty state.
- Seed clearly prefixed test data and temporary users with generic business names and Jane or John Doe logins, then delete them afterwards.

## Reporting

- Name which tests you ran and paste the failures if any failed. Say plainly if `npm run build` or the UI check was skipped.
- When a change only takes effect on reinstall (install-time setup), say so.
- Commit or push only when asked.
