import importlib

import qorsdk


def test_gateway_dashboard_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTSHIELD_DATA", str(tmp_path))
    monkeypatch.setenv("AGENTSHIELD_DRY_RUN", "1")
    monkeypatch.setenv("AGENTSHIELD_MODE", "direct")
    monkeypatch.setenv("AGENTSHIELD_POLICIES", str(tmp_path / "none.json"))
    monkeypatch.setenv("AGENTSHIELD_ADMIN_TOKEN", "tok")
    monkeypatch.setenv("AGENT_KEYS", "agent-a:key-a")
    monkeypatch.setenv("AGENTSHIELD_CORS", "http://localhost:5500")
    monkeypatch.delenv("AGENTSHIELD_RECIPIENTS", raising=False)
    import agentshield_qore.gateway as gw
    gw = importlib.reload(gw)
    from fastapi.testclient import TestClient
    c = TestClient(gw.app)
    adm, key = {"X-Admin-Token": "tok"}, {"X-Agent-Key": "key-a"}
    to = qorsdk.derive_native_account(qorsdk.generate_mnemonic()).address

    h = c.get("/v1/health").json()
    assert h["mode"] == "direct" and h["policy"]["per_tx_limit"] == 1_000_000 and h["dry_run"] is True
    assert c.post("/v1/intents", json={"to": to, "amount": 1000}, headers=key).json()["verdict"] == "ALLOW"
    full, slim = c.get("/v1/receipts?limit=5").json(), c.get("/v1/receipts?limit=5&slim=true").json()
    assert "sig" in full[0] and all("sig" not in r for r in slim) and len(slim) == len(full)
    assert c.get("/v1/agents").status_code == 401
    agents = c.get("/v1/agents", headers=adm).json()
    assert agents[0]["agent_id"] == "agent-a" and agents[0]["quarantined"] is False
    pre = c.options("/v1/intents", headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "POST",
                                            "Access-Control-Request-Headers": "x-agent-key"})
    assert pre.headers["access-control-allow-origin"] == "http://localhost:5500"
    bad = c.options("/v1/intents", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
