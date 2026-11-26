"""Demo: an LLM agent pays invoices through AgentShield; one invoice carries a prompt-injection attack.

    python scripts/demo_agent.py                       # careful agent, dry-run
    python scripts/demo_agent.py --gullible            # agent told to obey invoice text
    python scripts/demo_agent.py --hijacked            # plus a scripted COMPROMISED agent: what if the model is fooled?
    python scripts/demo_agent.py --skip-model --hijacked   # scripted attacks only (no API key needed)
    python scripts/demo_agent.py --live                # really broadcast on the testnet (uses data/, your .env mode)

Safe by default: forced dry-run (signs, never broadcasts), separate data_demo/ folder. Model key: MODEL_API_KEY in .env.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("--gullible", action="store_true", help="tell the agent to obey instructions found in invoices")
ap.add_argument("--hijacked", action="store_true", help="also run scripted attacks as if the agent were compromised")
ap.add_argument("--skip-model", action="store_true", help="do not call the model API")
ap.add_argument("--live", action="store_true", help="broadcast on the testnet (default: dry-run)")
ap.add_argument("--keep-log", action="store_true", help="keep receipts from earlier demo runs (default: start fresh)")
ap.add_argument("--model", default=None)
ap.add_argument("--base-url", default="https://api.meta.ai/v1")
ap.add_argument("--vendor", default=None, help="qor1 address of the honest vendor (default: your own signer address)")
ap.add_argument("--steps", type=int, default=8)
args = ap.parse_args()

# Decide data dir and dry-run BEFORE the config loads .env (existing variables always win over .env).
if not args.live:
    os.environ["AGENTSHIELD_DRY_RUN"] = "1"
    os.environ.setdefault("AGENTSHIELD_DATA", "data_demo")
    if os.environ["AGENTSHIELD_DATA"] == "data_demo" and not args.keep_log:
        import shutil
        # Each demo starts clean: limits and rate windows are computed from the receipt log, so leftovers from a
        # previous run would make honest payments look rate-limited. This also gives every run a fresh signing key.
        shutil.rmtree("data_demo", ignore_errors=True)

import httpx  # noqa: E402
import qorsdk  # noqa: E402

from agentshield_qore.config import build_shield, load_env  # noqa: E402
from agentshield_qore.demo_agent import hijack_attacks, run_agent  # noqa: E402
from agentshield_qore.receipts import verify_log  # noqa: E402

load_env()
key = os.getenv("MODEL_API_KEY")
if not args.skip_model and not key:
    raise SystemExit("Set MODEL_API_KEY in .env (your Meta Model API key), or use --skip-model --hijacked.")
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
print(f"mode={shield.mode} dry_run={shield.signer.dry_run} data={os.getenv('AGENTSHIELD_DATA', 'data')} "
      f"model={'(skipped)' if args.skip_model else model} agent={'GULLIBLE' if args.gullible else 'careful'}")
print(f"vendor (allowed) = {vendor}\nattacker         = {attacker}")

stats = {}
if not args.skip_model:
    stats, _ = run_agent(chat, shield, vendor, attacker, gullible=args.gullible, max_steps=args.steps)
    print("\n================ MODEL RUN ================")
    print(f"allowed={stats['ALLOW']}  needs-human={stats['ESCALATE']}  blocked={stats['DENY']}")
    tried = [r for r in shield.log.records() if r["kind"] == "decision" and r["intent"]["to"] == attacker]
    if tried:
        print(f"the model tried to pay the attacker {len(tried)} time(s); verdicts: {[r['verdict'] for r in tried]}")
    else:
        print("The model never tried to pay the attacker: it resisted the injection on its own.")
        if not args.hijacked:
            print("The gateway matters when a model does NOT resist. Add --hijacked to simulate that.")

if args.hijacked:
    res = hijack_attacks(shield, vendor, attacker)
    bad = [v for k in ("drain", "quiet", "split") for v in res[k] if v != "DENY"]
    burst = res["burst"]
    print(f"\nattacks to the attacker address: {sum(len(res[k]) for k in ('drain', 'quiet', 'split'))} tried, "
          f"{'ALL BLOCKED' if not bad else 'SOME GOT THROUGH: CHECK RECEIPTS'}")
    print(f"burst of 8 (second agent): {burst.count('ALLOW')} allowed, {burst.count('DENY')} blocked by the rate limit")
    print(f"after repeated denials the compromised agent is quarantined: its honest-looking request got {res['after'][0]} "
          f"(a human must review)")

v = verify_log(shield.log.path)
print(f"\nreceipt log: {v['records']} signed receipts, chain valid = {v['ok']}  ({shield.log.path})")
fails = [r for r in shield.log.records() if r["kind"] == "execution_failed"]
if fails:
    print(f"WARNING: {len(fails)} allowed payment(s) failed to execute: {fails[0].get('error', '')[:160]}")
if stats and stats["ESCALATE"]:
    print(f"{stats['ESCALATE']} payment(s) wait for a human (POST /v1/approvals/<seq> or the dashboard).")
