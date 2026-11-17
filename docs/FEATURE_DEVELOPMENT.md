# Feature development

## Workflow
1. Write the behaviour down: which module, which invariant (see `AGENTS.md`).
2. Add a failing test first.
3. Implement. Keep `policy.py` pure and keep network code in `chain.py`.
4. Run `python -m pytest -q` and `python -m agentshield_qore.cli demo`.
5. Update the docs that mention the change (table below).
6. Small commits, one feature each.

## Definition of done
- Tests pass offline, including a negative case.
- No secret can reach logs, receipts, API responses or MCP output.
- Docs updated; limits and unverified parts stated honestly.
- The demo still runs.

## Add a policy rule
1. Pick the next id (R09...). In `policy.evaluate`, call `deny("R09", "plain reason")`.
2. If it needs state (history, counters), pass it in as an argument; do not read files or the clock inside `evaluate`.
3. Add cases to `tests/test_core.py` for pass and fail.
4. Add the rule to `docs/API.md` and the Policies page rule table in `web/index.html`; mirror logic in the page's `evalI` if the playground should show it.
5. If it is numeric and the chain can hold it, extend `onchain.policy_to_rules`, `drift_report` and `COVERAGE`.

## Add a receipt kind
1. Append with `shield.log.append("my_kind", {...})`. Include `agent_id` (use `_shield` for system events).
2. Never include secrets. Amounts are integers.
3. Document fields in `docs/DATABASE.md`.
4. If the kind changes derived state (spend history, pending), update `ReceiptLog.__init__` or `Shield._rebuild_pending` and test a restart.

## Add an HTTP endpoint
1. Add it in `gateway.py`; use `_admin(token)` for anything that moves money or changes state.
2. Return plain JSON; no secrets.
3. Add it to `docs/API.md` and a test using `fastapi.testclient.TestClient`.

## Add an MCP tool
1. Add a function inside `make_tools` in `mcp_server.py` with a clear docstring (agents read it).
2. Register it in `make_server`.
3. Test it through `make_tools(shield)`; update the tool list assertion in `tests/test_hardening.py`.
4. Document it in `docs/MCP.md`.

## Add a dashboard page
1. In `web/index.html`, add an entry to `PAGES` and a function in the `T` object that returns HTML.
2. Page names are hash routes: ASCII letters, digits, hyphens only. Avoid `settings`, `sidebar`, `customize`, `upgrade`, `downloads`, `comment-*`.
3. Use the existing tokens (`--bg`, `--d`, `--l`, `--pu`, `--or`) and classes (`raise`, `inset`); support both color schemes.
4. Check the phone layout (bottom tab bar).

## Which docs to update
| Change | Docs |
|---|---|
| Rule | API, SECURITY (if it changes the threat model), website |
| Receipt kind or field | DATABASE |
| Endpoint | API |
| MCP tool | MCP |
| Config variable | SETUP, `.env.example` |
| Behaviour or limits | IMPLEMENTATION |
