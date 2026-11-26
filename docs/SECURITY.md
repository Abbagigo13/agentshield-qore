# Authentication and security

AgentShield is hackathon software for **testnet**. Treat this document as the honest list of what it protects and what it does not.

## What it protects against
- **A manipulated agent:** the agent has no key; every payment is checked by deterministic rules.
- **Over-spending:** per-transaction, daily and rate limits; human approval above a threshold.
- **Log tampering:** edits and mid-log deletions fail verification. Signatures are ML-DSA-87, so the record stays provable if classical signatures later fall.
- **A compromised gateway (in delegated mode):** the gateway holds only a delegate key that the chain bounds with on-chain spending rules. Verified: the chain refused a 1.5 QOR payment above a 1 QOR rule.

## Delegated mode: what the chain enforces
Verified on the testnet (see `docs/VERIFICATION.md`). Spending rules limit **linked delegate keys, not the account owner**:
a payment signed by the owner's own key above the on-chain limit was accepted. So:
- Run the gateway with `AGENTSHIELD_MODE=delegated`. The owner links a delegate key (`scripts/link_delegate.py`), a separate relayer
  pays fees, and the delegate signs payments. The chain refuses anything above the rule.
- Keep the **owner key out of the gateway**. In the demo one mnemonic derives all three roles; that defeats the protection.
- Funds sit in the owner account. A stolen gateway can drain at most the on-chain per-tx and daily limits, per delegate key.
- The allowlist, rate limit, injection scan and human approval remain gateway-only.

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
| Agent probing with retries and reworded requests | Mitigated by R09: quarantine after repeated denials, human release |
| Agent changing recipient to dodge the allowlist | Blocked by R04; attempts are logged |
| Editing or removing a record mid-log | Detected by `verify` |
| **Removing the last N records** | **Not detected** unless a later on-chain anchor exists. Anchor regularly |
| Replaying an intent | Each submission is a new decision; there is no idempotency key yet |
| Stolen admin token | Attacker can approve pending payments within policy and anchor; cannot exceed limits |
| Stolen gateway host | **Direct mode:** attacker holds the signing mnemonic and is not bounded by the chain. **Delegated mode:** attacker holds only the delegate key, bounded by on-chain limits (verified) |
| Denial of service | No API rate limiting |
| Multiple workers | Corrupt the chain. Run one |

## Known limitations
- No TLS, CORS policy, API rate limiting, key rotation, HSM/KMS support or encryption of the log at rest.
- Constant-time comparison is not used for tokens (dictionary lookup, simple equality).
- Injection patterns can be evaded by novel phrasing; they are one layer. They can also flag an honest agent that merely quotes an attack in its rationale (seen once in the demo).
- An agent that is denied can retry with reworded memos. R09 quarantines it after repeated denials (default 5 in 10 minutes), so further requests need a human. Rate-limit denials count too, so a buggy honest agent can quarantine itself; a human releases it.
- On-chain rules cannot express the allowlist, rate limit, scan or approval.
- Not yet verified live: on-chain daily cap, delegate expiry and revocation.
- Not independently audited.

## Safe operating checklist
- [ ] Testnet-only wallet with minimal funds
- [ ] Delegated mode on; owner key not on the gateway host
- [ ] Admin token and agent keys changed
- [ ] `.env` and `data/` excluded from git
- [ ] TLS in front of the gateway
- [ ] One worker process
- [ ] Policy limits set low; allowlist configured
- [ ] Anchor run on a schedule; on-chain rules synced and `GET /v1/onchain` shows `in_sync`
- [ ] Backups of `data/` stored securely

## Reporting issues
Open a private issue with the repository owner. Do not post real keys or mnemonics.
