"""MCP server: lets any MCP-capable agent (Claude, etc.) pay through AgentShield.

Run: python -m agentshield_qore.mcp_server        (needs: pip install -r requirements-mcp.txt)
The agent only gets a `pay` tool. It never sees a key, and every call is policy-checked and receipted.
"""
from __future__ import annotations

import os

from .config import build_shield
from .policy import Intent

AGENT_ID = os.getenv("AGENTSHIELD_MCP_AGENT", "mcp-agent")


def make_tools(shield, agent_id: str | None = None):
    agent = agent_id or AGENT_ID
    def pay(to: str, amount_uqor: int, memo: str = "", rationale: str = "") -> dict:
        """Request a QOR payment. amount_uqor is in base units (1 QOR = 1,000,000 uqor).
        Returns verdict ALLOW (sent), ESCALATE (needs a human) or DENY (blocked) with reasons."""
        r = shield.submit(Intent(agent, to, int(amount_uqor), "uqor", memo, rationale))
        ex = r["execution"] or {}
        return {"verdict": r["verdict"], "reasons": r["reasons"], "receipt_seq": r["decision_seq"],
                "tx_hash": ex.get("tx_hash")}

    def spending_limits() -> dict:
        """Show this agent's current limits so it can plan payments within policy."""
        p = shield.policy_for(agent)
        st = shield.agent_status(agent)
        return {"per_tx_limit_uqor": p.per_tx_limit, "daily_limit_uqor": p.daily_limit,
                "human_approval_above_uqor": p.escalate_above, "max_per_minute": p.max_per_minute,
                "recipient_allowlist": sorted(p.allowed_recipients),
                "denied_requests_recently": st["recent_denials"], "quarantined": st["quarantined"],
                "quarantine_after_denials": st["max_denials"]}

    return pay, spending_limits


def make_server(shield):
    """Works with mcp 1.x (FastMCP) and mcp 2.x (MCPServer)."""
    try:
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:
        from mcp.server.fastmcp import FastMCP as Server
    srv = Server("agentshield-qore")
    pay, limits = make_tools(shield)
    srv.tool()(pay)
    srv.tool()(limits)
    return srv


def main() -> None:
    make_server(build_shield()).run()


if __name__ == "__main__":
    main()
