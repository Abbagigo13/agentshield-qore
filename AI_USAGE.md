# AI usage

This project was built with AI assistance. This file records how, for the QoreChain *Build Before Q-Day* "AI-Native" award.

## Tools
- **Claude (Anthropic)**, used in a chat interface with a code sandbox, from November 2026.

## What the AI did
- Proposed the project idea after comparing likely submissions, and chose the problem (agents holding wallet keys).
- Wrote the first versions of the Python package (`policy.py`, `receipts.py`, `chain.py`, `shield.py`, `onchain.py`, `config.py`, `gateway.py`, `mcp_server.py`, `cli.py`) by reading the installed `qorechain-sdk` and its docs.
- Wrote the automated tests in `tests/`.
- Wrote the website in `web/index.html` and the documents in `docs/`, `README.md` and `AGENTS.md`.
- Found and fixed bugs it caused (for example an agent-key parsing bug and an MCP library version break).

## What the human did
- Set the goals, scope and priorities, and rejected ideas other builders were likely to submit.
- Chose the visual direction (neumorphism) and the page structure.
- Installed and ran the project and its tests on a Windows machine and reported errors back.
- Registers the project, controls the repository, and will run and verify the live testnet steps.

## How the output was checked
- 19 automated tests (offline). Run `python -m pytest -q`.
- An offline end-to-end demo: `python -m agentshield_qore.cli demo`.
- The human ran the tests and demo locally.

## Verified on the live testnet
On 24 November 2026 the human ran the live scripts on the QoreChain testnet: hybrid transactions, PQC key registration, anchoring,
on-chain spending rules, and chain-enforced refusal of an over-limit payment by a delegate key. Evidence: `docs/VERIFICATION.md`.
The live run also exposed three bugs in AI-written code (fee too low, account-sequence timing, a self-payment rule), now fixed,
and showed that the first design did not give chain-level protection, which led to delegated mode.

## Not yet verified
On-chain daily cap, delegate expiry and revocation, and the MCP server against a real client.

## Notes
AI-generated code can be wrong in ways that tests do not catch. `docs/SECURITY.md` lists known limits. The project targets the testnet only.
