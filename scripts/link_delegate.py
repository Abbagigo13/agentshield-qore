"""OWNER-SIDE setup for delegated mode: link the gateway's delegate key and set the on-chain spending rule.

    python scripts/link_delegate.py                 # link the delegate (skips if already linked)
    python scripts/link_delegate.py --update-rules  # change the on-chain limits to match your current policy

Uses the OWNER key (AGENTSHIELD_OWNER_MNEMONIC, else AGENTSHIELD_MNEMONIC account 0). In production run this on a
machine that is NOT the gateway, then keep the owner key offline.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qorsdk  # noqa: E402

from agentshield_qore import onchain  # noqa: E402
from agentshield_qore.chain import ChainSigner, load_or_create_pqc  # noqa: E402
from agentshield_qore.config import delegate_from_env, load_env, load_policies  # noqa: E402
from agentshield_qore.delegate import link_msgs  # noqa: E402
from agentshield_qore.policy import Policy  # noqa: E402

load_env()
main = os.getenv("AGENTSHIELD_MNEMONIC")
owner_mn = os.getenv("AGENTSHIELD_OWNER_MNEMONIC") or main
if not owner_mn or os.getenv("AGENTSHIELD_DRY_RUN", "1") == "1":
    raise SystemExit("Needs the live setup: a mnemonic in .env and AGENTSHIELD_DRY_RUN=0")
data = os.getenv("AGENTSHIELD_DATA", "data")
owner = ChainSigner(load_or_create_pqc(os.getenv("AGENTSHIELD_OWNER_PQC", f"{data}/pqc.json")),
                    mnemonic=owner_mn, dry_run=False, account_index=0)
delegate = delegate_from_env(main)
policy, _ = load_policies(os.getenv("AGENTSHIELD_POLICIES", "policies.json"), Policy())
print(f"owner={owner.address}\nlimits: {policy.per_tx_limit} uqor per payment, {policy.daily_limit} uqor per day")

if "--update-rules" in sys.argv:
    print(owner.send_msgs([onchain.build_update_msg(owner.address, owner.address, policy)], "agentshield update rules"))
    raise SystemExit(0)

rest = qorsdk.RestClient(owner.rest_url)
try:
    res = qorsdk.fetch_authenticators(rest, owner.address)
finally:
    rest.close()
for a in getattr(res, "authenticators", res):
    if a.pubkey_hex.lower().endswith(delegate.pubkey.hex()) and not a.revoked:
        raise SystemExit("Delegate already linked. Use --update-rules to change limits.")
print(owner.send_msgs(link_msgs(owner.address, owner.chain_id, delegate, policy), "agentshield link delegate"))
print("Linked. Start the gateway with AGENTSHIELD_MODE=delegated.")
