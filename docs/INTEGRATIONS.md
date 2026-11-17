# Integrations

## 1. HTTP (any agent framework)
Give the agent one function that calls `POST /v1/intents` with its key. Python with `httpx`:
```python
import httpx

def pay(to: str, amount_uqor: int, memo: str = "", rationale: str = "") -> dict:
    """Request a payment through AgentShield. Returns verdict ALLOW, ESCALATE or DENY with reasons."""
    r = httpx.post("http://localhost:8080/v1/intents",
                   headers={"X-Agent-Key": "key-alpha"},
                   json={"to": to, "amount": amount_uqor, "memo": memo, "rationale": rationale}, timeout=30)
    r.raise_for_status()
    return r.json()
```
Register it as a tool in your framework (function-calling, LangChain-style tools, custom loops). The agent gets only
this function; the key lives in your runtime, not in the model's context. Return the verdict and reasons to the model so
it can explain a denial to the user, but do not let it retry the same payment.

## 2. MCP
See `docs/MCP.md`. Best choice for MCP-capable clients.

## 3. QoreChain
Uses the official `qorechain-sdk` (Python, tested with 0.14.0):
| Use | SDK pieces |
|---|---|
| Hybrid transactions | `build_hybrid_tx`, `hybrid_sign_and_broadcast` |
| PQC keys | `generate_pqc_keypair`, `pqc_sign`, `pqc_verify`, `ensure_pqc_registered` |
| Spending rules | `msg.abstractaccount.update_spending_rules`, `fetch_spending_rules`, `validate_spending_rules` |
| Accounts | `derive_native_account`, `generate_mnemonic` |
Not yet used: the chain's AI risk-score helpers (`ai_risk_score`, `simulate_with_risk_score`) for EVM calls. A natural next
integration: pre-flight risk scoring before signing.

## 4. Operators and monitoring
- Poll `GET /v1/pending` to build a Slack or email approval flow, then call `POST /v1/approvals/{seq}`.
- Poll `GET /v1/verify` on a schedule and alert if `ok` is false.
- Call `POST /v1/anchor` hourly or daily so truncation of recent records becomes detectable.
- Call `GET /v1/onchain` to confirm the chain still enforces the limits.

## 5. Website
`web/index.html` is a standalone demo. To make it live, point its data calls at `GET /v1/receipts`, `/v1/verify` and
`/v1/onchain`, and enable CORS in `gateway.py`. Not done yet.

## Compatibility
Python 3.10+; tested on Linux and Windows (Python 3.13). SDK major versions move quickly: pin the version you tested.
