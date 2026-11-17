# Authentication and security

AgentShield is hackathon software for **testnet**. Treat this document as the honest list of what it protects and what it does not.

## What it protects against
- **A manipulated agent:** the agent has no key; every payment is checked by deterministic rules.
- **Over-spending:** per-transaction, daily and rate limits; human approval above a threshold.
- **Log tampering:** edits and mid-log deletions fail verification. Signatures are ML-DSA-87, so the record stays provable if classical signatures later fall.
- **A compromised gateway (partly):** on-chain spending rules bound the numeric limits independently.

## Authentication
| Caller | Mechanism | Notes |
|---|---|---|
| Agent | `X-Agent-Key` static secret mapped to an agent id | Identity comes from the key; the body cannot choose it |
| Admin | `X-Admin-Token` | Controls approvals, anchoring, rule sync |
| Public | none | `/v1/verify`, `/v1/receipts`, `/v1/onchain` expose payment details and memos |

Before sharing a deployment: change `AGENTSHIELD_ADMIN_TOKEN` from `change-me`, use long random agent keys, and put the
gateway behind TLS. Consider protecting the public read routes too, because receipts contain recipients and memos.

## Secrets
| Secret | Where | Handling |
|---|---|---|
| Wallet mnemonic | Environment or `.env` | Testnet only. `.env` must never be committed |
| ML-DSA-87 secret key | `data/pqc.json` | Plain JSON. Mode 600 applies on Linux/macOS, **not** enforced on Windows |
| Admin token, agent keys | Environment | Static bearer secrets |

Add `.env`, `data/` and `*.key` to `.gitignore`.

## Threat model
| Threat | Status |
|---|---|
| Prompt injection to pay an attacker | Mitigated: allowlist, limits, injection scan, approval. Scan is heuristic |
| Agent splitting a payment into small ones | Mitigated by the daily cap and rate limit |
| Agent changing recipient to dodge the allowlist | Blocked by R04; attempts are logged |
| Editing or removing a record mid-log | Detected by `verify` |
| **Removing the last N records** | **Not detected** unless a later on-chain anchor exists. Anchor regularly |
| Replaying an intent | Each submission is a new decision; there is no idempotency key yet |
| Stolen admin token | Attacker can approve pending payments within policy and anchor; cannot exceed limits |
| Stolen gateway host | Attacker holds the mnemonic and PQC key: limited by on-chain rules only if they are active |
| Denial of service | No API rate limiting |
| Multiple workers | Corrupt the chain. Run one |

## Known limitations
- No TLS, CORS policy, API rate limiting, key rotation, HSM/KMS support or encryption of the log at rest.
- Constant-time comparison is not used for tokens (dictionary lookup, simple equality).
- Injection patterns can be evaded by novel phrasing; they are one layer.
- On-chain rules cannot express the allowlist, rate limit, scan or approval.
- Live chain behaviour (registration, broadcast, rule enforcement on this account type) is unverified.
- Not independently audited.

## Safe operating checklist
- [ ] Testnet-only wallet with minimal funds
- [ ] Admin token and agent keys changed
- [ ] `.env` and `data/` excluded from git
- [ ] TLS in front of the gateway
- [ ] One worker process
- [ ] Policy limits set low; allowlist configured
- [ ] Anchor run on a schedule; on-chain rules synced and `GET /v1/onchain` shows `in_sync`
- [ ] Backups of `data/` stored securely

## Reporting issues
Open a private issue with the repository owner. Do not post real keys or mnemonics.
