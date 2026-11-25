"""Step-by-step live testnet check. Run from the project folder with the venv active.

    python scripts/live_check.py --address   # print your wallet address (to fund it), then exit
    python scripts/live_check.py             # full live check (needs AGENTSHIELD_DRY_RUN=0 and a funded wallet)
    python scripts/live_check.py --dry       # same steps offline: sign only, no network

Each step prints OK or FAILED. It stops at the first failure so you can paste that output to get help.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DRY = "--dry" in sys.argv
if DRY:
    os.environ["AGENTSHIELD_DRY_RUN"] = "1"
    os.environ.setdefault("AGENTSHIELD_DATA", "data_livecheck")

import httpx  # noqa: E402
import qorsdk  # noqa: E402

from agentshield_qore.config import build_shield, load_env  # noqa: E402
from agentshield_qore.policy import Intent  # noqa: E402
from agentshield_qore.receipts import verify_log  # noqa: E402

load_env()


FAILED_SOFT = []


def step(name, fn, fatal=True):
    print(f"\n[{name}]")
    try:
        out = fn()
        print("  OK", out if out is not None else "")
        return out
    except Exception as e:  # noqa: BLE001 - we want to show every failure plainly
        print(f"  FAILED: {type(e).__name__}: {e}")
        if fatal:
            raise SystemExit(1)
        FAILED_SOFT.append(name)
        return None


if "--address" in sys.argv:
    m = os.getenv("AGENTSHIELD_MNEMONIC")
    if not m:
        raise SystemExit("Set AGENTSHIELD_MNEMONIC in .env first (a NEW testnet-only wallet).")
    print(qorsdk.derive_native_account(m).address)
    raise SystemExit(0)

shield = build_shield()
signer = shield.signer
addr = signer.address
rest = signer.rest_url
print(f"network={signer.network} chain_id={signer.chain_id} dry_run={signer.dry_run}\naddress={addr}")

if not DRY:
    def reach():
        r = httpx.get(f"{rest}/cosmos/base/tendermint/v1beta1/blocks/latest", timeout=20)
        r.raise_for_status()
        return "latest height " + r.json()["block"]["header"]["height"]
    step("1 reach testnet", reach)

    def balance():
        r = httpx.get(f"{rest}/cosmos/bank/v1beta1/balances/{addr}", timeout=20)
        r.raise_for_status()
        coins = {c["denom"]: int(c["amount"]) for c in r.json().get("balances", [])}
        have = coins.get("uqor", 0)
        if have < 300_000:
            raise RuntimeError(f"balance {have} uqor is too low; fund {addr} from the faucet (need at least 300000 uqor)")
        return f"{have} uqor"
    step("2 balance", balance)

step("3 register PQC key (one time)", signer.ensure_registered)
step("4 hybrid tx: send 1 uqor to self", lambda: signer.send(addr, 1, "uqor", "agentshield live check"))


def gated():
    r = shield.submit(Intent("live-check", addr, 1000, "uqor", "policy-gated test", "live check"))
    if r["verdict"] != "ALLOW":
        raise RuntimeError(f"expected ALLOW, got {r['verdict']}: {r['reasons']}")
    return r["execution"].get("tx_hash")
step("5 policy-gated payment through the shield", gated)
step("6 anchor log head on-chain", shield.anchor)
step("7 write on-chain spending rules", shield.sync_onchain, fatal=False)
if not DRY:
    step("8 read back on-chain rules (drift report)", lambda: shield.onchain_status()["summary"], fatal=False)
v = step("9 verify receipt log", lambda: verify_log(shield.log.path))
if not v["ok"]:
    print("\nLog verification FAILED.")
elif FAILED_SOFT:
    print("\nCore steps passed. These optional steps failed:", ", ".join(FAILED_SOFT))
else:
    print("\nAll steps passed.")
