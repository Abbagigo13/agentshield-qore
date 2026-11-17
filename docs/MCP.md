# MCP connection

The MCP server gives any MCP-capable agent two tools and no keys.

## Install and run
```bash
pip install -r requirements-mcp.txt       # works with mcp 1.x and 2.x
python -m agentshield_qore.mcp_server      # stdio transport
```
It builds the same shield as the HTTP gateway (same `.env`, policies, data directory). Run the MCP server **or** the
HTTP gateway against one data directory at a time; two processes would each hold their own lock and corrupt the chain.

## Tools
### `pay(to, amount_uqor, memo="", rationale="")`
Request a payment. `amount_uqor` is an integer in base units (1 QOR = 1,000,000 uqor). Returns:
```json
{"verdict": "ALLOW|ESCALATE|DENY", "reasons": ["…"], "receipt_seq": 12, "tx_hash": "…or null"}
```
### `spending_limits()`
Returns `per_tx_limit_uqor`, `daily_limit_uqor`, `human_approval_above_uqor`, `max_per_minute`, `recipient_allowlist`
for the agent this server represents.

## Agent identity
One MCP server process represents one agent: `AGENTSHIELD_MCP_AGENT` (default `mcp-agent`). Its limits come from
`policies.json` if that id is listed, otherwise the default policy. For several agents, run one server per agent with
separate data directories, or use the HTTP gateway, which maps keys to ids.

## Client configuration (example for a desktop MCP client)
```json
{
  "mcpServers": {
    "agentshield": {
      "command": "C:\\path\\to\\agentshield-qore\\.venv\\Scripts\\python.exe",
      "args": ["-m", "agentshield_qore.mcp_server"],
      "cwd": "C:\\path\\to\\agentshield-qore",
      "env": {"AGENTSHIELD_DRY_RUN": "1", "AGENTSHIELD_MCP_AGENT": "claude-agent"}
    }
  }
}
```
Use the venv's Python so the packages are found. Config file locations differ per client; check its documentation.
Keep `AGENTSHIELD_DRY_RUN=1` until the live testnet path has been verified.

## Behaviour agents should follow
See "If you are an AI agent using AgentShield" in `AGENTS.md`: call `spending_limits` first, treat `DENY` as final,
wait for humans on `ESCALATE`, never copy untrusted text into `memo` or `rationale`.

## Testing
`pytest -q` checks that `make_server` lists exactly `pay` and `spending_limits`, and that `pay` returns ALLOW and DENY correctly.
The MCP wire protocol against a real client has **not** been exercised yet.

## Limits
stdio transport only; no per-call authentication (trust is the local process boundary); approvals are done through the
HTTP gateway or code, not through MCP.
