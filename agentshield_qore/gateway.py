"""HTTP API for agents. Run: uvicorn agentshield_qore.gateway:app --port 8080"""
from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .config import build_shield
from .policy import Intent
from .receipts import verify_log

shield = build_shield()
_log = shield.log
# AGENT_KEYS="agent-id:secret-key,..." -> {secret-key: agent-id}
KEYS = {k: a for a, k in (p.split(":", 1) for p in os.getenv("AGENT_KEYS", "agent-alpha:key-alpha").split(",") if ":" in p)}
ADMIN = os.getenv("AGENTSHIELD_ADMIN_TOKEN", "change-me")

app = FastAPI(title="AgentShield for QoreChain", version="0.2.0")


class IntentIn(BaseModel):
    to: str
    amount: int
    denom: str = "uqor"
    memo: str = ""
    rationale: str = ""


def _admin(tok: str | None):
    if tok != ADMIN:
        raise HTTPException(401, "admin token required")


@app.post("/v1/intents")
def submit(body: IntentIn, x_agent_key: str | None = Header(None)):
    agent = KEYS.get(x_agent_key or "")
    if not agent:
        raise HTTPException(401, "unknown agent key")
    return shield.submit(Intent(agent_id=agent, **body.model_dump()))


@app.get("/v1/pending")
def pending(x_admin_token: str | None = Header(None)):
    _admin(x_admin_token)
    return {str(k): v.__dict__ for k, v in shield.pending.items()}


@app.post("/v1/approvals/{seq}")
def approve(seq: int, x_admin_token: str | None = Header(None)):
    _admin(x_admin_token)
    if seq not in shield.pending:
        raise HTTPException(404, "no such pending request")
    return shield.approve(seq, "admin")


@app.post("/v1/rejections/{seq}")
def reject(seq: int, x_admin_token: str | None = Header(None)):
    _admin(x_admin_token)
    if seq not in shield.pending:
        raise HTTPException(404, "no such pending request")
    return shield.reject(seq, "admin")


@app.get("/v1/receipts")
def receipts(limit: int = 50):
    return list(shield.log.records())[-max(1, min(limit, 500)):]


@app.get("/v1/verify")
def verify():
    return verify_log(_log.path)


@app.post("/v1/anchor")
def anchor(x_admin_token: str | None = Header(None)):
    _admin(x_admin_token)
    return shield.anchor()


@app.get("/v1/onchain")
def onchain_status():
    """Does the chain itself enforce our limits? Compares stored rules with the gateway policy."""
    return shield.onchain_status()


@app.post("/v1/onchain/sync")
def onchain_sync(x_admin_token: str | None = Header(None)):
    _admin(x_admin_token)
    try:
        return shield.sync_onchain()
    except PermissionError as e:
        raise HTTPException(409, str(e))


@app.get("/v1/health")
def health():
    s = shield.signer
    return {"mode": shield.mode, "network": s.network, "chain_id": s.chain_id, "dry_run": s.dry_run,
            "owner": getattr(s, "owner", s.address), "relayer_or_signer": s.address}


@app.get("/v1/agents/{agent_id}")
def agent_status(agent_id: str, x_admin_token: str | None = Header(None)):
    _admin(x_admin_token)
    return shield.agent_status(agent_id)


@app.post("/v1/agents/{agent_id}/release")
def release_agent(agent_id: str, x_admin_token: str | None = Header(None)):
    """Clear an agent's quarantine (R09) after a human has reviewed what it was doing."""
    _admin(x_admin_token)
    return shield.release(agent_id, "admin")
