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

- 16 automated tests (offline). Run `python -m pytest -q`.
- An offline end-to-end demo: `python -m agentshield_qore.cli demo`.
- The human ran the tests and demo locally.

## Not yet verified

Live testnet behaviour (key registration, broadcast, anchoring, on-chain spending rules) has not been run. This file will be updated when it has.

## Notes

AI-generated code can be wrong in ways that tests do not catch. `docs/SECURITY.md` lists known limits. The project targets the testnet only.
