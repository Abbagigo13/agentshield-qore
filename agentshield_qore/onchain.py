"""Second layer: mirror the gateway policy into QoreChain's on-chain spending rules.

If the gateway is ever compromised, the chain itself still refuses payments outside these bounds.
Only the numeric rules can live on-chain (per-tx limit, daily cap, allowed denoms). The allowlist,
rate limit, injection scan and human approval remain gateway-only, and the drift report says so.
"""
from __future__ import annotations

import qorsdk
from qorsdk import msg

from .policy import Policy

RULE_ID = "agentshield-v1"

# What each rule is enforced by. Honest coverage map, shown in the API and the dashboard.
COVERAGE = {
    "R01 valid address": "chain + gateway", "R02 allowed denom": "chain + gateway",
    "R03 positive amount": "chain + gateway", "R05 per-tx limit": "chain + gateway",
    "R06 daily cap": "chain + gateway", "R04 recipient allowlist": "gateway only",
    "R07 rate limit": "gateway only", "R08 injection scan": "gateway only",
    "E01 human approval": "gateway only",
}


def policy_to_rules(policy: Policy) -> list[dict]:
    denoms = sorted(policy.allowed_denoms)
    rule = {
        "id": RULE_ID, "enabled": True,
        "per_tx_limit": int(policy.per_tx_limit), "daily_limit": int(policy.daily_limit),
        "allowed_denoms": denoms,
        # Per-denom entries replace the rule-level limits for that denom, so set them explicitly.
        "denom_limits": [{"denom": d, "per_tx_limit": str(policy.per_tx_limit),
                          "daily_limit": str(policy.daily_limit)} for d in denoms],
    }
    qorsdk.validate_spending_rules([rule])
    if not qorsdk.rules_cover_value_permissions([rule]):
        raise ValueError("rule does not bound every denom; the chain would refuse a value-permission key")
    return [rule]


def build_update_msg(owner: str, account_address: str, policy: Policy):
    return msg.abstractaccount.update_spending_rules(
        owner=owner, account_address=account_address, rules=policy_to_rules(policy))


def drift_report(policy: Policy, chain_rules) -> dict:
    """Compare the gateway policy with what the chain actually has stored (qorsdk.SpendingRules)."""
    rules = list(getattr(chain_rules, "rules", ()) or ())
    first = next((r for r in rules if r.get("enabled")), None)   # the chain applies the FIRST enabled rule
    checks = []
    if first is None:
        return {"in_sync": False, "enforced_on_chain": False, "checks": [],
                "summary": "No enabled spending rule on-chain: the chain is not limiting this account.",
                "coverage": COVERAGE}

    def num(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    for name, mine, theirs in (("per_tx_limit", policy.per_tx_limit, num(first.get("per_tx_limit"))),
                               ("daily_limit", policy.daily_limit, num(first.get("daily_limit")))):
        if theirs == mine:
            status = "match"
        elif theirs == 0:
            status = "chain_unbounded"        # 0 means no cap on-chain
        elif theirs > mine:
            status = "chain_looser"           # gateway stricter: fine normally, but chain protects less
        else:
            status = "chain_stricter"         # chain will refuse payments the gateway allows
        checks.append({"field": name, "gateway": mine, "chain": theirs, "status": status})
    denoms = sorted(first.get("allowed_denoms") or [])
    checks.append({"field": "allowed_denoms", "gateway": sorted(policy.allowed_denoms), "chain": denoms,
                   "status": "match" if denoms == sorted(policy.allowed_denoms) else "differs"})
    in_sync = all(c["status"] == "match" for c in checks)
    return {"in_sync": in_sync, "enforced_on_chain": True, "rule_id": first.get("id"), "checks": checks,
            "summary": "Chain rules match the gateway policy." if in_sync
            else "Chain rules differ from the gateway policy. Run sync.", "coverage": COVERAGE}
