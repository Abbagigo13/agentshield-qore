# Testing

## Run
```bash
pip install -r requirements.txt
python -m pytest -q          # 16 tests, offline, about 10 seconds
```
No network, wallet or funds are used. Transactions are built and signed in dry-run mode.

## Suite
| File | Tests | Covers |
|---|---|---|
| `tests/test_core.py` | 6 | Allow, every deny rule, daily and rate limits, escalate then approve, log verification, tamper and deletion detection |
| `tests/test_onchain.py` | 4 | Rule generation and validation, update message, drift report cases, dry-run sync receipt |
| `tests/test_hardening.py` | 6 | Pending approvals after restart, per-agent policy, 20 concurrent submissions, `.env` and policy file loading, MCP tools, MCP tool listing |

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
- **Live testnet:** broadcast, key registration, anchoring, spending-rule sync and enforcement.
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
