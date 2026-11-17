# Project implementation

## Status at a glance
| Area | State |
|---|---|
| Policy engine (R01 to R08, E01) | Built, tested |
| Signed, hash-chained receipt log and verifier | Built, tested |
| Hybrid transaction building (offline, dry-run) | Built, tested |
| Live broadcast, PQC key registration, anchoring | Written from SDK docs, **not run on testnet** |
| On-chain spending-rule mirror and drift report | Built, tested offline; **live behaviour unverified** |
| Human approvals, restart-safe | Built, tested |
| Per-agent policies, `.env` loading | Built, tested |
| HTTP gateway | Built, smoke-tested |
| MCP server (`pay`, `spending_limits`) | Built, tool listing tested |
| Website (landing, 7 dashboard pages, docs sections) | Built; runs a browser simulation, not the real gateway |
| Live dashboard against the gateway | Not started |
| Demo agent with a real LLM | Not started |

16 automated tests pass on Linux and on Windows (Python 3.13, `qorechain-sdk` 0.14.0).

## Build order used
1. Policy engine and tests (pure logic first).
2. Signed receipt log and tamper detection.
3. Hybrid transaction building against the SDK, offline.
4. Shield orchestration, CLI demo, HTTP gateway.
5. On-chain spending-rule layer.
6. Hardening: locking, restart-safe approvals, config, per-agent policies.
7. MCP server.
8. Website and documentation.

## Key design decisions
- **Deterministic rules, no model in the decision path.** Predictable, testable, explainable.
- **Log everything, including denials.** Evidence is the product.
- **Hash then sign.** The signature covers the record hash, so verification is one hash and one ML-DSA-87 check.
- **Dry-run default.** The demo and tests never need funds or network.
- **Flat-file storage.** Simple, inspectable, enough for one process (see `docs/DATABASE.md`).
- **Honest coverage.** Only numeric limits mirror on-chain; the rest stays gateway-only and the API says so.

## Known limitations
- Live testnet path unverified. The SDK's `ensure_pqc_registered`, broadcast and spending-rule calls are used as documented.
- Spending rules may bind only abstract accounts or linked keys, not a plain account. To be confirmed.
- The injection scan is a regex list, not a classifier.
- Truncating the last records of a log is not detectable unless a later anchor exists.
- Fee is a fixed constant (`5000 uqor`, gas `200000`), not estimated.
- Single process only.

## Remaining work (to 2 December 2026)
1. Live testnet run: register key, one payment, one anchor, one rule sync. Fix surprises. **Highest priority.**
2. Demo agent: an LLM agent with the `pay` tool facing a poisoned invoice.
3. Live dashboard: point the website at the real gateway (`/v1/receipts`, `/v1/verify`, `/v1/onchain`).
4. Pin tested dependency versions; repository polish and license.
5. Fee estimation and clearer broadcast error reporting.
