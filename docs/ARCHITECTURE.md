# Architecture

## Components
| Module | Responsibility |
|---|---|
| `policy.py` | Pure decision logic. `Intent`, `Policy`, `Decision`, `evaluate()`. No I/O |
| `receipts.py` | Append-only signed log: `ReceiptLog`, `verify_log()`, `anchor_memo()` |
| `chain.py` | `ChainSigner`: builds and signs hybrid transactions, broadcasts, fetches on-chain rules. Dry-run mode |
| `shield.py` | `Shield`: orchestrates policy, log, signer; approvals; anchoring; on-chain sync. Holds the lock |
| `onchain.py` | Maps `Policy` to on-chain spending rules and reports drift |
| `config.py` | `.env` loading, `policies.json`, `build_shield()` |
| `gateway.py` | FastAPI HTTP API |
| `mcp_server.py` | MCP tools `pay` and `spending_limits` |
| `cli.py` | `demo`, `rules`, `verify` |

## Request lifecycle
1. An agent submits an intent (HTTP with `X-Agent-Key`, or MCP `pay`).
2. `Shield.submit` takes the lock, loads that agent's execution history, and calls `evaluate()` with the agent's policy.
3. A **decision receipt** is appended (hash-chained, ML-DSA-87 signed), whatever the verdict.
4. **ALLOW:** `ChainSigner.send` builds a hybrid transaction, broadcasts it (or only signs in dry-run), and an
   **execution receipt** records the transaction hash. A failure becomes an `execution_failed` receipt.
5. **ESCALATE:** the intent waits in `pending` until an admin approves (approval receipt, then execution) or rejects.
6. **DENY:** nothing is signed; the denial is the evidence.
7. The response returns verdict, reasons, decision sequence number and execution.

## Trust boundaries
- **Agent:** untrusted. Holds only an agent key and can only submit intents.
- **Gateway process:** trusted. Holds the wallet mnemonic and the ML-DSA-87 key.
- **Chain:** independent verifier. Enforces on-chain spending rules and holds anchors.
- **Auditor:** needs only the log and the public key (`receipts.jsonl.pub`).

## Defense in depth
| Layer | Enforces | If it fails |
|---|---|---|
| Gateway policy | All rules R01 to R08, E01 | Chain limits still apply to numeric rules |
| On-chain spending rules | Per-tx, daily, denom | Gateway still blocks; log still records |
| Receipt log | Evidence of every decision | Anchor proves the head existed at a given time |

Gateway-only rules: allowlist (R04), rate limit (R07), injection scan (R08), human approval (E01). The on-chain rule
format has no recipient list, so those cannot be mirrored.

## Receipt integrity
`hash = SHA-256(canonical JSON of the record without hash and sig)`; `sig = ML-DSA-87(secret key, hash bytes)`;
each record stores `prev_hash`. Canonical JSON means sorted keys, no spaces, UTF-8. The browser demo and the Python
code use the same canonicalization.

## Concurrency
One `RLock` serializes decisions so the chain stays linear. **Run a single worker process.** Multiple uvicorn workers
would each hold their own lock and corrupt the chain.

## Failure behaviour
- Signing or broadcast error: logged as `execution_failed`; no silent loss.
- Gateway crash: pending approvals are rebuilt from the log on start.
- Missing mnemonic outside dry-run: startup refuses.

## Out of scope
Horizontal scaling, key rotation, HSM or KMS integration, multi-signature approval.
