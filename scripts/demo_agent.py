"""Demo: a real LLM agent tries to pay invoices through AgentShield, and one invoice carries a prompt-injection attack.

    python scripts/demo_agent.py               # careful agent
    python scripts/demo_agent.py --gullible    # agent told to obey invoice text, so the attack reaches the gateway

Needs MODEL_API_KEY (Meta Model API) in .env. Safe by default: dry-run, nothing is broadcast.
For a live run on the testnet: AGENTSHIELD_DRY_RUN=0 and AGENTSHIELD_MODE=delegated in .env.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AGENTSHIELD_DATA", "data_demo")

import httpx  # noqa: E402
import qorsdk  # noqa: E402

from agentshield_qore.config import build_shield, load_env  # noqa: E402
from agentshield_qore.demo_agent import run_agent  # noqa: E402
from agentshield_qore.receipts import verify_log  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--gullible", action="store_true", help="tell the agent to obey instructions found in invoices")
ap.add_argument("--model", default=None)
ap.add_argument("--base-url", default="https://api.meta.ai/v1")
ap.add_argument("--vendor", default=None, help="qor1 address of the honest vendor (default: your own signer address)")
ap.add_argument("--steps", type=int, default=8)
args = ap.parse_args()

load_env()
key = os.getenv("MODEL_API_KEY")
if not key:
    raise SystemExit("Set MODEL_API_KEY in .env (your Meta Model API key). Do not paste it anywhere else.")
model = args.model or os.getenv("AGENT_MODEL", "muse-spark-1.1")
role = os.getenv("AGENT_SYSTEM_ROLE", "developer")


def chat(messages, tools):
    msgs = [dict(m, role=role) if m["role"] == "developer" else m for m in messages]
    for attempt in range(4):
        r = httpx.post(f"{args.base_url}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                       json={"model": model, "messages": msgs, "tools": tools, "tool_choice": "auto"}, timeout=90)
        if r.status_code == 429 and attempt < 3:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise SystemExit(f"Model API error {r.status_code}: {r.text[:500]}\n"
                             f"(model={model}; set AGENT_MODEL in .env if the name is wrong, "
                             f"or AGENT_SYSTEM_ROLE=system if the role is rejected)")
        return r.json()["choices"][0]["message"]


shield = build_shield()
vendor = args.vendor or shield.signer.address
attacker = qorsdk.derive_native_account(qorsdk.generate_mnemonic()).address
shield.policy.allowed_recipients = frozenset({vendor})
s = shield.signer
print(f"mode={shield.mode} dry_run={s.dry_run} model={model} agent={'GULLIBLE' if args.gullible else 'careful'}")
print(f"vendor (allowed)  = {vendor}\nattacker          = {attacker}")

stats, _ = run_agent(chat, shield, vendor, attacker, gullible=args.gullible, max_steps=args.steps)

print("\n================ RESULT ================")
print(f"allowed={stats['ALLOW']}  needs-human={stats['ESCALATE']}  blocked={stats['DENY']}")
v = verify_log(shield.log.path)
print(f"receipt log: {v['records']} signed receipts, chain valid = {v['ok']}")
atk = [r for r in shield.log.records() if r["kind"] == "decision" and r["intent"]["to"] == attacker]
print("attack attempts reached the gateway:", len(atk), "(all blocked)" if all(r["verdict"] == "DENY" for r in atk) else "CHECK RECEIPTS")
if not atk:
    print("The agent never tried to pay the attacker. Run again with --gullible to see the gateway stop an obedient agent.")
if stats["ESCALATE"]:
    print(f"{stats['ESCALATE']} payment(s) wait for a human: approve with POST /v1/approvals/<seq> or Approvals in the dashboard.")
