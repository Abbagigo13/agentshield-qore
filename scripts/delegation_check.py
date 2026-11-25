"""Prove CHAIN-ENFORCED delegation on the live testnet. Run after live_check.py has passed.

Roles (all derived from your one testnet mnemonic: fine for a test, NOT for production):
  owner    = account 0   your funded wallet, holds the funds
  relayer  = account 1   submits transactions and pays fees (gets a small top-up from the owner)
  delegate = ed25519 key 2, linked to the owner with the `send` permission and the on-chain spending rule

Steps: fund relayer -> register relayer PQC key -> link delegate (+ spending rule) -> read back ->
       pay 0.5 QOR via the delegate (inside the limit) -> pay 1.5 QOR via the delegate (above the limit).
Expected: the first succeeds and the second is BLOCKED BY THE CHAIN. Payments go to your own relayer account
(the chain refuses a payment from an account to itself), so only network fees are spent.

Run:  python scripts/delegation_check.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
import qorsdk  # noqa: E402

from agentshield_qore.chain import ChainSigner, load_or_create_pqc  # noqa: E402
from agentshield_qore.config import load_env  # noqa: E402
from agentshield_qore.delegate import DelegatedSigner, Delegate, link_msgs  # noqa: E402
from agentshield_qore.policy import Policy  # noqa: E402

load_env()
mnemonic = os.getenv("AGENTSHIELD_MNEMONIC")
if not mnemonic or os.getenv("AGENTSHIELD_DRY_RUN", "1") == "1":
    raise SystemExit("Needs the live setup: AGENTSHIELD_MNEMONIC set and AGENTSHIELD_DRY_RUN=0 in .env")
data = os.getenv("AGENTSHIELD_DATA", "data")

owner = ChainSigner(load_or_create_pqc(f"{data}/pqc.json"), mnemonic=mnemonic, dry_run=False, account_index=0)
relayer = ChainSigner(load_or_create_pqc(f"{data}/pqc_relayer.json"), mnemonic=mnemonic, dry_run=False, account_index=1)
delegate = Delegate.from_mnemonic(mnemonic, 2)
policy = Policy()
print(f"owner   ={owner.address}\nrelayer ={relayer.address}\ndelegate pubkey={delegate.pubkey.hex()}")
print(f"on-chain limit to be set: {policy.per_tx_limit} uqor per payment, {policy.daily_limit} uqor per day")


def step(name, fn):
    print(f"\n[{name}]")
    try:
        out = fn()
        print("  OK", out if out is not None else "")
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  FAILED: {type(e).__name__}: {e}")
        raise SystemExit(1)


def balance(addr):
    r = httpx.get(f"{owner.rest_url}/cosmos/bank/v1beta1/balances/{addr}", timeout=20)
    if r.status_code != 200:
        return 0
    return {c["denom"]: int(c["amount"]) for c in r.json().get("balances", [])}.get("uqor", 0)


def fund():
    have = balance(relayer.address)
    if have >= 300_000:
        return f"relayer already has {have} uqor"
    return owner.send(relayer.address, 500_000, "uqor", "fund relayer")


step("1 owner balance", lambda: f"{balance(owner.address)} uqor")
step("2 fund the relayer with 0.5 QOR for fees", fund)
step("3 register the relayer's PQC key", relayer.ensure_registered)
def linked_views():
    rest = qorsdk.RestClient(owner.rest_url)
    try:
        res = qorsdk.fetch_authenticators(rest, owner.address)
    finally:
        rest.close()
    return list(getattr(res, "authenticators", res))


def link():
    for a in linked_views():
        if a.pubkey_hex.lower().endswith(delegate.pubkey.hex()) and not a.revoked:
            return "delegate already linked, skipping"
    return owner.send_msgs(link_msgs(owner.address, owner.chain_id, delegate, policy), "agentshield link delegate")


step("4 link the delegate key to the owner (+ on-chain spending rule)", link)


def readback():
    return [(a.scheme, list(a.permissions), "spend_rule=" + str(a.has_spend_rule), "revoked=" + str(a.revoked))
            for a in linked_views()]


step("5 read back linked keys", readback)

via = DelegatedSigner(relayer, owner.address, delegate)
step("6 CONTROL: pay 0.5 QOR through the delegate (inside the limit)",
     lambda: via.send(relayer.address, policy.per_tx_limit // 2, "uqor", "delegate control"))

over = policy.per_tx_limit + policy.per_tx_limit // 2
print(f"\n[7 TEST: pay {over / 1e6} QOR through the delegate (ABOVE the limit)]")
try:
    r = via.send(relayer.address, over, "uqor", "delegate over limit")
    print("  ACCEPTED:", r)
    print("\nRESULT: NOT blocked. The chain did not enforce the limit on the delegate. Paste this output.")
except Exception as e:  # noqa: BLE001
    print(f"  BLOCKED: {type(e).__name__}: {e}")
    print("\nRESULT: the chain blocked the over-limit payment. Read the reason above for the rule it names.")
