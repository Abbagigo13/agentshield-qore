# AgentShield for QoreChain

**A policy firewall for AI agents that hold a wallet, with post-quantum signed receipts.**

Built for the QoreChain *Build Before Q-Day* Developer Fest (Advanced, Track A: AI agents).
Target network: **QoreChain testnet only.**

An AI agent that can move money is one prompt injection away from draining its wallet. AgentShield sits between
the agent and the chain. The agent never holds a key. It submits an *intent*; AgentShield decides, signs, and records.

```
agent --intent--> [policy engine] --ALLOW--> [hybrid secp256k1 + ML-DSA-87 tx] --> QoreChain testnet
                       |  ESCALATE --> human approval                |
                       |  DENY                                        v
                       +--------> [ML-DSA-87 signed, hash-chained receipt log] --anchor--> on-chain memo
                                                                      |
                                    [on-chain spending rules: second layer if the gateway is compromised]
```

## Features
- **Policy engine:** nine deterministic rules (address, denom, amount, allowlist, per-tx limit, daily cap, rate limit, prompt-injection scan, human-approval threshold). No model in the decision path.
- **Hybrid post-quantum transactions:** secp256k1 + ML-DSA-87 through the official `qorechain-sdk`.
- **Signed receipts:** every decision and execution is a hash-chained, ML-DSA-87 signed record. Edits and deletions in the middle are detected.
- **On-chain anchor:** commit the log head in a transaction memo.
- **Chain-enforced limits (delegated mode):** the gateway signs with a linked delegate key and a relayer submits, so the chain itself refuses payments above the on-chain limit. Verified on the testnet; see [docs/VERIFICATION.md](docs/VERIFICATION.md).
- **Human approval:** large payments wait for a person; pending approvals survive restarts.
- **Per-agent policies**, an **HTTP API**, an **MCP server**, a **CLI**, and a **dashboard website**.

## Quickstart
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                    # 19 passed
python -m agentshield_qore.cli demo    # offline demo, no keys needed
uvicorn agentshield_qore.gateway:app --port 8080
```
Full instructions, including going live on testnet: [docs/SETUP.md](docs/SETUP.md).

## Documentation
| Document | What it covers |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Problem, users, goals, requirements, scope |
| [docs/DESIGN.md](docs/DESIGN.md) | Visual design system and UX of the website |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, request lifecycle, trust boundaries |
| [docs/DATABASE.md](docs/DATABASE.md) | Data model and storage (there is no SQL database) |
| [docs/API.md](docs/API.md) | HTTP endpoints, auth, examples |
| [AGENTS.md](AGENTS.md) | Rules for AI coding agents working in this repo, and for agents using AgentShield |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | What is built, what is verified, what remains |
| [docs/SETUP.md](docs/SETUP.md) | Install, configure, go live |
| [docs/FEATURE_DEVELOPMENT.md](docs/FEATURE_DEVELOPMENT.md) | How to add rules, receipts, endpoints, pages |
| [docs/SECURITY.md](docs/SECURITY.md) | Authentication, threat model, known limits |
| [docs/MCP.md](docs/MCP.md) | Connecting MCP agents |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | HTTP clients, agent frameworks, QoreChain |
| [docs/TESTING.md](docs/TESTING.md) | Test suite and how to extend it |
| [docs/VERIFICATION.md](docs/VERIFICATION.md) | What was proven on the live testnet, with transaction hashes |

## Layout
```
agentshield_qore/   policy.py receipts.py chain.py shield.py onchain.py delegate.py config.py gateway.py mcp_server.py cli.py
scripts/            live_check.py enforcement_check.py delegation_check.py link_delegate.py
tests/              test_core.py test_onchain.py test_hardening.py
web/index.html      landing page and dashboard (self-contained)
docs/               the documents above
```

## Status
Verified on the QoreChain testnet (24 Nov 2026): hybrid transactions, PQC key registration, policy-gated payments, on-chain
anchoring, spending-rule write and read-back, and **chain-enforced refusal of an over-limit payment by a delegate key**.
Finding: the on-chain rule does **not** bind the account owner's own payments, so the chain-level layer needs delegated mode.
Details and transaction hashes: [docs/VERIFICATION.md](docs/VERIFICATION.md). Not yet verified: on-chain daily cap, key expiry
and revocation, the MCP server against a real client. See [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md).

## Security
Testnet only. Never use a mnemonic that holds real funds. Read [docs/SECURITY.md](docs/SECURITY.md) before deploying.

## License
MIT. See [LICENSE](LICENSE). AI assistance is documented in [AI_USAGE.md](AI_USAGE.md).
