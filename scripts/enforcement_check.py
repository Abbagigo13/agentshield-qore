"""Does the CHAIN itself enforce the on-chain spending rule? Run after live_check.py has passed.

It sends QOR to YOURSELF directly, bypassing the gateway policy, so only the chain can stop it:
  1. control: 0.5 QOR (below the on-chain per-tx limit of 1 QOR) -> should succeed
  2. test:    1.5 QOR (above the limit)                          -> see below

  Chain REJECTS step 2  -> the rule is enforced for this account: the second layer works.
  Chain ACCEPTS step 2  -> the rule is stored but does not bind this account type (a plain account).

Cost: network fees only. The QOR comes back to you because you are the recipient.
Run:  python scripts/enforcement_check.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentshield_qore.config import build_shield  # noqa: E402

shield = build_shield()
signer = shield.signer
addr = signer.address
print(f"address={addr} dry_run={signer.dry_run}")
if signer.dry_run:
    raise SystemExit("Dry-run mode: nothing is sent. Set AGENTSHIELD_DRY_RUN=0 to run this check.")

print("on-chain rule status:", shield.onchain_status()["summary"])
limit = shield.policy.per_tx_limit
print(f"on-chain per-tx limit: {limit} uqor ({limit / 1e6} QOR)")

print("\n[control] send 0.5 QOR to self (below the limit)")
try:
    print("  OK", signer.send(addr, limit // 2, "uqor", "enforcement control"))
except Exception as e:  # noqa: BLE001
    print(f"  FAILED: {type(e).__name__}: {e}")
    raise SystemExit("The control payment failed, so the next result would not be meaningful. Paste this output.")

over = limit + limit // 2
print(f"\n[test] send {over / 1e6} QOR to self (ABOVE the limit), bypassing the gateway")
try:
    r = signer.send(addr, over, "uqor", "enforcement test")
    print("  ACCEPTED by the chain:", r)
    print("\nRESULT: the chain did NOT block it. The rule is stored on-chain but does not bind this plain account.")
    print("The gateway still enforces the limit; the chain-level second layer needs an abstract account (see docs).")
except Exception as e:  # noqa: BLE001
    print(f"  REJECTED: {type(e).__name__}: {e}")
    print("\nRESULT: the chain blocked it. Read the reason above to confirm it mentions the spending rule or limit.")
