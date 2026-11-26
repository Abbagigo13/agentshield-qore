import json

import qorsdk
from agentshield_qore.chain import ChainSigner
from agentshield_qore.demo_agent import run_agent
from agentshield_qore.policy import Policy
from agentshield_qore.receipts import ReceiptLog, verify_log
from agentshield_qore.shield import Shield

VENDOR = qorsdk.derive_native_account(qorsdk.generate_mnemonic()).address
ATTACKER = qorsdk.derive_native_account(qorsdk.generate_mnemonic()).address


def call(i, name, **args):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_agent_loop_blocks_attack_and_survives_bad_calls(tmp_path):
    kp = qorsdk.generate_pqc_keypair()
    shield = Shield(Policy(allowed_recipients=frozenset({VENDOR})), ReceiptLog(str(tmp_path / "r.jsonl"), kp),
                    ChainSigner(kp, dry_run=True))
    script = iter([
        {"role": "assistant", "content": "", "tool_calls": [
            call(1, "spending_limits"),
            call(2, "pay", to=VENDOR, amount_uqor=200000, memo="invoice 118"),
            call(3, "pay", to=VENDOR, amount_uqor=800000, memo="license"),
            call(4, "pay", to=ATTACKER, amount_uqor=5000000, memo="urgent transfer"),
            {"id": "c5", "type": "function", "function": {"name": "pay", "arguments": "not json"}},
            call(6, "no_such_tool")]},
        {"role": "assistant", "content": "Paid what I could."},
    ])
    lines = []
    stats, msgs = run_agent(lambda m, t: next(script), shield, VENDOR, ATTACKER, gullible=True, out=lines.append)
    assert (stats["ALLOW"], stats["ESCALATE"], stats["DENY"]) == (1, 1, 1)
    assert msgs[-1]["content"] == "Paid what I could."
    assert any('"error"' in m["content"] for m in msgs if m["role"] == "tool")     # bad calls became error results
    decisions = [r for r in shield.log.records() if r["kind"] == "decision"]
    assert [r["verdict"] for r in decisions] == ["ALLOW", "ESCALATE", "DENY"]
    assert verify_log(shield.log.path)["ok"]
