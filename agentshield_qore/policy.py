"""Deterministic policy engine. Pure functions, no I/O, easy to audit and test."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import qorsdk

# Text an attacker may plant in memos / rationales / tool outputs the agent read.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules|polic)",
    r"system prompt",
    r"you are now",
    r"disregard .{0,30}(polic|limit|rule|guard)",
    r"override .{0,20}(limit|polic|safety|guard)",
    r"send (all|everything|the entire|my entire)",
    r"\bdrain\b",
    r"do not (tell|inform|notify|alert)",
    r"urgent.{0,25}(transfer|wire|send|payment)",
    r"new (wallet|address) (for|to) (receive|send)",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


@dataclass
class Intent:
    agent_id: str
    to: str
    amount: int            # base units (uqor)
    denom: str = "uqor"
    memo: str = ""
    rationale: str = ""    # why the agent says it wants this payment


@dataclass
class Policy:
    per_tx_limit: int = 1_000_000          # 1 QOR (6 decimals)
    daily_limit: int = 3_000_000
    escalate_above: int = 500_000          # needs human approval above this
    allowed_recipients: frozenset = field(default_factory=frozenset)
    allowed_denoms: frozenset = frozenset({"uqor"})
    max_per_minute: int = 5
    scan_text: bool = True
    max_denials: int = 5                   # R09: this many denials in the window quarantines the agent (0 = off)
    denial_window: int = 600               # seconds


@dataclass
class Decision:
    verdict: str                      # ALLOW | ESCALATE | DENY
    reasons: list[str]
    rule_ids: list[str]


def scan_text(*texts: str) -> list[str]:
    hits = []
    for t in texts:
        for rx in _INJ:
            if t and rx.search(t):
                hits.append(rx.pattern)
    return hits


def evaluate(intent: Intent, policy: Policy, history: list[tuple[float, int]],
             now: float | None = None, recent_denials: int = 0) -> Decision:
    """history = [(timestamp, amount)] of this agent's executed spends."""
    now = time.time() if now is None else now
    reasons: list[str] = []
    ids: list[str] = []

    def deny(rule: str, why: str) -> None:
        ids.append(rule)
        reasons.append(why)

    amount_ok = isinstance(intent.amount, int) and not isinstance(intent.amount, bool) and intent.amount > 0
    if not amount_ok:
        deny("R03", "amount must be a positive integer in base units")
    if not qorsdk.is_valid_bech32(intent.to, "qor"):
        deny("R01", "recipient is not a valid qor bech32 address")
    if intent.denom not in policy.allowed_denoms:
        deny("R02", f"denom {intent.denom!r} is not allowed")
    if policy.allowed_recipients and intent.to not in policy.allowed_recipients:
        deny("R04", "recipient is not on the allowlist")
    if amount_ok and intent.amount > policy.per_tx_limit:
        deny("R05", f"amount {intent.amount} exceeds per-tx limit {policy.per_tx_limit}")

    day = [a for (t, a) in history if now - t < 86_400]
    if amount_ok and sum(day) + intent.amount > policy.daily_limit:
        deny("R06", f"24h spend {sum(day)} + {intent.amount} exceeds daily limit {policy.daily_limit}")
    if sum(1 for (t, _) in history if now - t < 60) >= policy.max_per_minute:
        deny("R07", f"more than {policy.max_per_minute} payments in the last minute")

    if policy.scan_text:
        if scan_text(intent.memo, intent.rationale):
            deny("R08", "possible prompt injection in memo/rationale")

    quarantined = policy.max_denials > 0 and recent_denials >= policy.max_denials
    note = (f"agent quarantined: {recent_denials} denied requests in the last {max(1, policy.denial_window // 60)} "
            f"min; a human must review")
    if ids:
        if quarantined:
            deny("R09", note)
        return Decision("DENY", reasons, ids)
    if quarantined:
        return Decision("ESCALATE", [note], ["R09"])
    if intent.amount > policy.escalate_above:
        return Decision("ESCALATE", [f"amount {intent.amount} above auto-approve threshold {policy.escalate_above}"], ["E01"])
    return Decision("ALLOW", ["all rules passed"], [])
