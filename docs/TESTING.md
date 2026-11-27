# Testing

## Run
```bash
pip install -r requirements.txt
python -m pytest -q          # 23 tests, offline, about 10 seconds
```
No network, wallet or funds are used. Transactions are built and signed in dry-run mode.

## Reproducible install
`pip install -r requirements-mcp.txt -c requirements.lock` then `python -m pytest -q`. A clean Linux (Python 3.12) environment built this way
passed the suite, and `.github/workflows/tests.yml` runs it on Ubuntu and Windows with Python 3.12 and 3.13 on every push.

## Suite
| File | Tests | Covers |
|---|---|---|
| `tests/test_core.py` | 6 | Allow, every deny rule, daily and rate limits, escalate then approve, log verification, tamper and deletion detection |
| `tests/test_onchain.py` | 4 | Rule generation and validation, update message, drift report cases, dry-run sync receipt |
| `tests/test_demo_agent.py` | 2 | Agent loop with a scripted model (ALLOW, ESCALATE, DENY, bad tool calls survive); hijack scenario ends in quarantine |
| `tests/test_gateway.py` | 1 | Dashboard endpoints: health policy, slim receipts, agents list (admin only), CORS allow and refuse |
| `tests/test_hardening.py` | 10 | Pending approvals after restart, per-agent policy, 20 concurrent submissions, `.env` and policy file loading, MCP tools, MCP tool listing, waiting for tx inclusion, delegate signing and link messages, delegated mode from config, R09 quarantine, release, restart and window |

## Dashboard test (optional, needs Node)
`tests/browser/dashboard_live.js` drives `web/index.html` in a simulated browser (jsdom) against a running, seeded gateway and
checks: connect, live receipts, gateway-side verification, approvals, quarantine and release, the playground, and that hostile
recipient text is escaped. Run: start a gateway on port 8080 with `AGENT_KEYS=agent-a:key-a`, `AGENTSHIELD_ADMIN_TOKEN=tok` and
`AGENTSHIELD_DRY_RUN=1`; seed it once with `python scripts/seed_gateway.py --key key-a --yes` (it creates pending approvals and a quarantined agent, which the test expects);
`npm install jsdom`; `node tests/browser/dashboard_live.js`. It is not part of `pytest`.

## Manual checks
```bash
python -m agentshield_qore.cli demo     # exit code 0 when attacks are blocked and tampering is caught
python -m agentshield_qore.cli rules
uvicorn agentshield_qore.gateway:app --port 8080
curl -s localhost:8080/v1/verify
```

## Writing tests
- Use `tmp_path` for the log and `ChainSigner(kp, dry_run=True)`; never touch the real `data/` folder.
- Pass `now=` for deterministic time.
- Test both the pass and the fail path of every rule.
- For anything that edits a log, assert `verify_log(...)["ok"]` is false afterwards.
- Gateway tests: `fastapi.testclient.TestClient` with `AGENTSHIELD_DATA` set to a temp directory before importing the app.

## Not covered (yet)
- Live testnet is covered by scripts, not pytest: `live_check.py`, `enforcement_check.py`, `delegation_check.py` (results in `docs/VERIFICATION.md`). Not yet live: on-chain daily cap, expiry, revocation.
- MCP over a real client connection.
- API authentication failure matrix and CORS.
- Browser behaviour of the website (verify/tamper, mobile layout) beyond manual checks.
- Load and long-running behaviour.

## Live test plan (testnet)
Automated: `python scripts/live_check.py` covers steps 1 to 5 below. Manual checks follow.
1. Register the PQC key. 2. Send 1 uqor to self. 3. Submit an ALLOW intent with `DRY_RUN=0` and confirm the hash on an explorer.
4. Anchor, then confirm the memo on-chain. 5. Sync rules; `GET /v1/onchain` shows `in_sync`. 6. Try a payment above the
on-chain limit directly and confirm the chain refuses it. Record results in `docs/IMPLEMENTATION.md`.

## Release checklist
- [ ] `pytest -q` green on a clean virtualenv
- [ ] Demo exits 0
- [ ] Live test plan done and recorded
- [ ] Dependencies pinned to tested versions
- [ ] Secrets absent from the repository
