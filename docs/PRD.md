# Product Requirements: AgentShield for QoreChain

## 1. Summary
AgentShield is a gateway that lets AI agents spend crypto safely. The agent submits payment intents. AgentShield checks
them against policy, signs only the allowed ones with a hybrid post-quantum transaction, and records every decision as
a tamper-evident, post-quantum signed receipt.

## 2. Problem
- Agents that hold keys can be manipulated by prompt injection (a poisoned invoice, memo, web page or tool output).
- A stolen or misled agent can move funds immediately and irreversibly.
- Teams cannot later prove what an agent was allowed to do, and logs signed with classical keys will not stay trustworthy
  once quantum computers can break those keys (the "Q-Day" the Developer Fest is named for).

## 3. Users
| User | Need |
|---|---|
| Agent developer | Give an agent spending ability without handing it a key |
| Operator / finance owner | Set limits, approve large payments, see everything the agent tried |
| Auditor / security reviewer | Verify the record is complete and unaltered, now and in future |

## 4. Goals
1. Keys never reach the agent.
2. Every intent gets a deterministic decision (ALLOW, ESCALATE, DENY) with human-readable reasons.
3. Every decision and execution is recorded in a log whose tampering is detectable and whose signatures are post-quantum.
4. A second, chain-enforced limit exists in case the gateway is compromised.
5. Integration takes minutes: HTTP API and MCP server.

## 5. Non-goals
- Not a general-purpose wallet or custody product.
- Not a model-based fraud detector; decisions are deterministic rules. The injection scan is a heuristic.
- No mainnet support in this release.
- No multi-node or high-availability deployment.

## 6. Functional requirements
| ID | Requirement | Status |
|---|---|---|
| F1 | Accept payment intents over HTTP and MCP | Done |
| F2 | Evaluate rules R01 to R08 and E01; return verdict and reasons | Done |
| F3 | Sign allowed payments as hybrid secp256k1 + ML-DSA-87 transactions | Done; verified on testnet |
| F4 | Hold large payments for human approval; survive restart | Done |
| F5 | Write hash-chained, ML-DSA-87 signed receipts for every outcome | Done |
| F6 | Verify the full chain from the CLI and the API | Done |
| F7 | Anchor the log head on-chain | Done; verified on testnet |
| F8 | Mirror numeric limits into on-chain spending rules; report drift | Done; verified (rule stored and read back) |
| F12 | Delegated mode: chain refuses payments above the limit | Done; verified on testnet |
| F9 | Per-agent policies from a JSON file | Done |
| F10 | Website: landing, dashboard, attack playground, verify/tamper demo | Done (browser simulation) |
| F11 | Live dashboard backed by the real gateway | Not started |

## 7. Non-functional requirements
- **Integrity:** altering or removing any record except trailing ones must fail verification.
- **Safety by default:** dry-run unless explicitly switched off; testnet only.
- **Auditability:** denials are recorded, not just approvals.
- **Portability:** runs on Windows, Linux, macOS with Python 3.10+.
- **Testability:** the core runs fully offline.

## 8. Success metrics (hackathon)
- A reviewer can run the offline demo in under two minutes.
- A real testnet payment and a real anchor transaction exist with public hashes.
- All listed attack classes in the demo are blocked and recorded.
- 16+ automated tests pass.

## 9. Risks
| Risk | Mitigation |
|---|---|
| Live testnet behaviour differs from the SDK docs | Run the live path early; keep dry-run default |
| On-chain rules may not bind a plain account | Verify; fall back to an abstract account |
| Injection scan misses novel phrasing | Treat it as one layer; limits and approval still apply |
| Truncating trailing receipts is undetectable without an anchor | Anchor regularly; document the limit |
| Fast-moving SDK versions | Pin tested versions before submission |

## 10. Timeline
Submission closes **2 December 2026, 23:59 UTC**. Remaining work: live testnet verification, live dashboard, demo agent,
hardening, documentation, submission package.
