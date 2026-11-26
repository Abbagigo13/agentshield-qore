# Data model and storage

**There is no SQL database.** State lives in three files under the data directory (`AGENTSHIELD_DATA`, default `data/`).
Everything else is rebuilt from them at startup.

## Files
| File | Content | Sensitivity |
|---|---|---|
| `receipts.jsonl` | Append-only receipt log, one JSON object per line | Contains payment details and memos. Not secret keys |
| `receipts.jsonl.pub` | Hex ML-DSA-87 public key used to verify the log | Public |
| `pqc.json` | `{"public_key": hex, "secret_key": hex}` | **Secret.** Back up securely, never commit |

The wallet mnemonic is not stored on disk by AgentShield; it comes from the environment.

## Receipt record
Common fields on every record:
| Field | Type | Meaning |
|---|---|---|
| `v` | int | Schema version, currently 1 |
| `seq` | int | 1-based, contiguous |
| `ts` | float | Unix seconds |
| `kind` | string | See below |
| `prev_hash` | hex64 | `hash` of the previous record; 64 zeros for the first |
| `hash` | hex64 | SHA-256 of the canonical body |
| `sig` | hex | ML-DSA-87 signature over the hash bytes |

## Kinds and their fields
| Kind | Extra fields |
|---|---|
| `decision` | `agent_id`, `intent{agent_id,to,amount,denom,memo,rationale}`, `verdict`, `reasons[]`, `rule_ids[]` |
| `execution` | `agent_id`, `ref_seq`, `amount`, `to`, `dry_run`, `tx_hash`, `height` (live), `via` (`delegate` in delegated mode) |
| `execution_failed` | `agent_id`, `ref_seq`, `error` |
| `approval` / `rejection` | `agent_id`, `ref_seq`, `approver` |
| `quarantine` | `agent_id`, `after_seq`, `recent_denials`, `window_s` (written when an agent crosses the R09 threshold) |
| `release` | `agent_id`, `approver` (a human cleared the quarantine; earlier denials stop counting) |
| `anchor` | `agent_id` (`_shield`), `anchored_seq`, `anchored_hash`, `dry_run`, `tx_hash` |
| `onchain_rules` | `agent_id` (`_shield`), `rule_id`, `per_tx_limit`, `daily_limit`, `dry_run`, `tx_hash` |

Amounts are integers in base units (`uqor`, 1 QOR = 1,000,000 uqor).

## Derived state (not stored)
- **Spend history** for limits: built from `execution` records.
- **Recent denials and quarantine (R09):** `decision` records with verdict `DENY` per agent inside the window, ignoring any before the agent's last `release`.
- **Pending approvals:** `decision` with verdict `ESCALATE` and no later `approval`/`rejection` with the same `ref_seq`.

## Anchor memo
`agentshield:v1:<seq>:<hash>` in a self-send transaction of 1 `uqor`.

## Browser demo
The website keeps the same record shape in memory and loses it on reload. Its signatures are not computed.

## Operations
- **Backup:** copy the whole data directory while the gateway is stopped. Treat `pqc.json` as a secret.
- **Never edit `receipts.jsonl`.** Any edit breaks verification from that record onward. Never rotate or delete it without
  starting a new data directory.
- **Verification:** `python -m agentshield_qore.cli verify data/receipts.jsonl`.

## Limits and migration
A flat file suits one process and thousands of records. The log is read fully at startup. If volume grows, move records
to SQLite or Postgres with `seq` as the primary key and keep the same hashing; the verification code would not change.
