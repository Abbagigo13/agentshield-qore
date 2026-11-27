# HTTP API

Start: `uvicorn agentshield_qore.gateway:app --port 8080` (single worker). Interactive docs at `/docs` (FastAPI).

## Authentication
| Caller | Header | Source |
|---|---|---|
| Agent | `X-Agent-Key: <secret>` | `AGENT_KEYS="agent-id:secret,..."` |
| Admin | `X-Admin-Token: <token>` | `AGENTSHIELD_ADMIN_TOKEN` (default `change-me`, **change it**) |
| Public | none | `/v1/verify`, `/v1/receipts`, `/v1/onchain` |

The agent identity comes from the key, never from the request body. Wrong or missing credentials return `401`.

## Amounts
Integers in base units. `1 QOR = 1,000,000 uqor`.

## Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/intents` | agent | Submit a payment intent |
| GET | `/v1/pending` | admin | List escalations awaiting a human |
| POST | `/v1/approvals/{seq}` | admin | Approve and execute |
| POST | `/v1/rejections/{seq}` | admin | Reject |
| GET | `/v1/receipts?limit=50&slim=false` | none | Latest receipts (limit 1 to 500). `slim=true` drops the 9 KB signature from each record |
| GET | `/v1/verify` | none | Verify hash chain and every signature |
| POST | `/v1/anchor` | admin | Anchor the log head on-chain |
| GET | `/v1/onchain` | none | Compare on-chain spending rules with gateway policy |
| POST | `/v1/onchain/sync` | admin | Write gateway limits on-chain (direct mode; returns `409` in delegated mode) |
| GET | `/v1/health` | none | Mode, network, owner and signer addresses |
| GET | `/v1/agents` | admin | All known agents with recent denials and quarantine status |
| GET | `/v1/agents/{agent_id}` | admin | Recent denials and whether the agent is quarantined |
| POST | `/v1/agents/{agent_id}/release` | admin | Clear a quarantine after human review |

### POST /v1/intents
Request:
```json
{"to": "qor1...", "amount": 100000, "denom": "uqor", "memo": "invoice 118", "rationale": "vendor payment"}
```
Response `200`:
```json
{"verdict": "ALLOW", "reasons": ["all rules passed"], "decision_seq": 7,
 "execution": {"kind": "execution", "seq": 8, "tx_hash": "…", "dry_run": true, "amount": 100000}}
```
`verdict` is `ALLOW`, `ESCALATE` (execution is `null`, waits for approval) or `DENY` (execution `null`, `reasons` lists
each failed rule, `rule_ids` are in the receipt).

```bash
curl -s localhost:8080/v1/intents -H 'X-Agent-Key: key-alpha' -H 'content-type: application/json' \
  -d '{"to":"qor1...","amount":100000,"memo":"invoice 118"}'
```

### Approvals
```bash
curl -s localhost:8080/v1/pending -H 'X-Admin-Token: change-me'
curl -s -X POST localhost:8080/v1/approvals/3 -H 'X-Admin-Token: change-me'
```
Unknown or already-handled sequence numbers return `404`.

### GET /v1/verify
```json
{"ok": true, "records": 20, "head": {"seq": 20, "hash": "…"}, "errors": []}
```
`errors` names the first broken records, for example `seq 3: record content was modified`.

### GET /v1/onchain
Returns `enforced_on_chain`, `in_sync`, per-field `checks` (`match`, `chain_looser`, `chain_unbounded`, `chain_stricter`,
`differs`), a `summary`, and a `coverage` map of which rules the chain enforces. Requires network access to the testnet.

## Browser access (CORS)
The dashboard calls this API from the browser. Allowed origins come from `AGENTSHIELD_CORS` (comma list; default
`http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000`). Other origins are refused by the browser. CORS is not
authentication: admin routes still need `X-Admin-Token`. `GET /v1/health` also returns the default `policy` limits.

## Rules reference
| ID | Meaning |
|---|---|
| R01 | Valid `qor` bech32 address |
| R02 | Denom allowed |
| R03 | Positive integer amount |
| R04 | Recipient on allowlist (when one is configured) |
| R05 | Amount at or below per-transaction limit |
| R06 | 24 hour spend within daily limit |
| R07 | Within rate limit (default 5 per minute) |
| R08 | No prompt-injection patterns in memo or rationale |
| R09 | Repeated denials: after `max_denials` (default 5) denied requests within `denial_window` (default 10 min) the agent is **quarantined**: a request that would be ALLOW becomes ESCALATE, and DENY stays DENY, until a human releases it |
| E01 | Above the human-approval threshold, so ESCALATE |

## Errors
`401` bad credentials, `404` unknown pending item, `422` invalid request body. Chain errors during execution are
recorded as `execution_failed` receipts and returned in `execution`.

## Not implemented
No pagination cursors, no rate limiting, no TLS (terminate TLS in a reverse proxy), no per-agent admin scopes.
