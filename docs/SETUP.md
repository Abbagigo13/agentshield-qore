# Setup

## Requirements
Python 3.10 or newer, pip, git (optional). Windows, Linux or macOS. Testnet funds only for the live path.

## 1. Install
Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt -c requirements.lock
```
Linux or macOS:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -c requirements.lock
```
Optional MCP server: `pip install -r requirements-mcp.txt -c requirements.lock`.
`requirements.lock` pins every package to the versions that passed the tests and the live testnet runs. Without it, a fresh install picks newer transitive versions. Tested on Python 3.12 (Linux) and 3.13 (Windows).

## 2. Verify offline
```bash
python -m pytest -q                    # expect 23 passed
python -m agentshield_qore.cli demo     # attacks blocked, tampered log detected
```
No `.env` and no network are needed for this.

## 3. Configure
Copy `.env.example` to `.env` and edit. Real environment variables override `.env`.
| Variable | Meaning | Default |
|---|---|---|
| `AGENTSHIELD_NETWORK` | `testnet` | `testnet` |
| `AGENTSHIELD_DRY_RUN` | `1` sign only, `0` broadcast | `1` (in code) |
| `AGENTSHIELD_MNEMONIC` | Funded **testnet** wallet words | none |
| `AGENTSHIELD_ADMIN_TOKEN` | Admin API token | `change-me` |
| `AGENT_KEYS` | `agent-id:secret,...` | `agent-alpha:key-alpha` |
| `AGENTSHIELD_RECIPIENTS` | Comma list of allowed `qor1...` addresses | empty (no allowlist) |
| `AGENTSHIELD_POLICIES` | Path to per-agent policy JSON | `policies.json` |
| `AGENTSHIELD_MCP_AGENT` | Agent id for the MCP server | `mcp-agent` |
| `AGENTSHIELD_MODE` | `direct` or `delegated` | `direct` |
| `AGENTSHIELD_OWNER_ADDRESS`, `AGENTSHIELD_RELAYER_MNEMONIC`, `AGENTSHIELD_DELEGATE_SEED` | Delegated mode roles | derived from `AGENTSHIELD_MNEMONIC` |
| `AGENTSHIELD_GAS`, `AGENTSHIELD_GAS_PRICE` | Fee tuning | `300000`, `0.15` |
| `AGENTSHIELD_DATA` | Data directory | `data` |

Note: `.env.example` ships with `AGENTSHIELD_DRY_RUN=0`. Set it to `1` until you intend to broadcast.

Per-agent limits: copy `policies.example.json` to `policies.json`.

## 4. Run the gateway
```bash
uvicorn agentshield_qore.gateway:app --port 8080
```
Use **one** worker. Open `http://localhost:8080/docs`.

## 5. Go live on testnet
1. Create a **new, testnet-only** wallet and fund it from the faucet listed on the Developer Fest site or its community channel.
2. Put the mnemonic in `.env`, set `AGENTSHIELD_DRY_RUN=0`.
3. In Python:
```python
from agentshield_qore.config import load_env; load_env()
from agentshield_qore.chain import ChainSigner, load_or_create_pqc
s = ChainSigner(load_or_create_pqc("data/pqc.json"))
print(s.address)
print(s.ensure_registered())                         # one time
print(s.send(s.address, 1, "uqor", "agentshield test"))
```
4. Start the gateway, then call `POST /v1/anchor` and `POST /v1/onchain/sync` with the admin token; check `GET /v1/onchain`.

### Delegated mode (chain-enforced limits)
1. In `.env` add `AGENTSHIELD_MODE=delegated`. With a single mnemonic: owner is account 0, relayer account 1, delegate key 2 (test only).
2. Fund the relayer with about 0.5 QOR from the owner, register its PQC key, and link the delegate:
   `python scripts/delegation_check.py` does all of this and then proves the chain blocks an over-limit payment.
3. Later, `python scripts/link_delegate.py --update-rules` changes the on-chain limits to match your policy.
4. Start the gateway: `GET /v1/health` shows `"mode": "delegated"`.
Production: set `AGENTSHIELD_OWNER_ADDRESS`, `AGENTSHIELD_RELAYER_MNEMONIC` and `AGENTSHIELD_DELEGATE_SEED`, and keep the owner key off the gateway host.

### Live dashboard
```powershell
# terminal 1: the gateway (dry-run is free and safe for a demo)
$env:AGENTSHIELD_DRY_RUN="1"; python -m uvicorn agentshield_qore.gateway:app --port 8080
# terminal 2: the dashboard
python -m http.server 5500 --directory web
# terminal 3: fill the gateway with activity (use the secret after the colon in AGENT_KEYS)
python scripts/seed_gateway.py --key YOUR_AGENT_KEY
```
Open `http://localhost:5500`, press Enter, and on Overview enter `http://localhost:8080`, your `AGENTSHIELD_ADMIN_TOKEN` and the agent
key. Receipts, Approvals (approve or reject for real), Agents (release a quarantine) and Verify (the gateway checks every hash
link and ML-DSA-87 signature) then use live data. The page must be served from an allowed origin (see CORS in `docs/API.md`).
The preview link of the website cannot reach a local gateway; use the local server above.

### Guided live check
`python scripts/live_check.py --address` prints the wallet address to fund. After funding, `python scripts/live_check.py`
runs: reach testnet, balance, PQC key registration, a hybrid self-send, a policy-gated payment, an anchor, an on-chain
spending-rule write and read-back, and log verification. It stops at the first core failure; the two spending-rule steps are
reported but do not stop the run. `--dry` runs the same steps offline.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Activation script blocked | `Set-ExecutionPolicy -Scope Process Bypass` |
| `AGENTSHIELD_MNEMONIC is required` | Set it, or use dry-run |
| Broadcast fails with insufficient funds | Fund the printed address from the faucet |
| `/v1/onchain` times out | Network or endpoint issue; the offline features are unaffected |
| `mcp.server.fastmcp` not found | Update to the repo's `mcp_server.py` (supports mcp 1.x and 2.x) |
| Chain verification fails after you edited the log | Restore from backup; logs cannot be repaired |
