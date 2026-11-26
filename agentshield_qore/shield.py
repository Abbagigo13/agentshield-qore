"""The gateway core: intent -> policy -> signed receipt -> (maybe) hybrid PQC tx -> signed execution receipt."""
from __future__ import annotations

import threading
import time
from dataclasses import asdict

from . import onchain
from .chain import ChainSigner
from .policy import Decision, Intent, Policy, evaluate
from .receipts import ReceiptLog, anchor_memo


class Shield:
    def __init__(self, policy: Policy, log: ReceiptLog, signer: ChainSigner,
                 agent_policies: dict[str, Policy] | None = None):
        self.policy, self.log, self.signer = policy, log, signer
        self.agent_policies = agent_policies or {}
        self.lock = threading.RLock()          # one decision at a time: the log is a single chain
        self.pending = self._rebuild_pending()  # survives restarts: derived from the signed log

    @property
    def mode(self) -> str:
        return "delegated" if hasattr(self.signer, "owner") else "direct"

    def policy_for(self, agent_id: str) -> Policy:
        return self.agent_policies.get(agent_id, self.policy)

    def _rebuild_pending(self) -> dict[int, Intent]:
        esc, done = {}, set()
        for r in self.log.records():
            if r["kind"] == "decision" and r["verdict"] == "ESCALATE":
                esc[r["seq"]] = Intent(**r["intent"])
            elif r["kind"] in ("approval", "rejection"):
                done.add(r["ref_seq"])
        return {s: i for s, i in esc.items() if s not in done}

    def _recent_denials(self, agent_id: str, now: float) -> int:
        window = self.policy_for(agent_id).denial_window
        return self.log.denial_count(agent_id, max(now - window, self.log.released.get(agent_id, float("-inf"))))

    def agent_status(self, agent_id: str, now: float | None = None) -> dict:
        t = time.time() if now is None else now
        pol = self.policy_for(agent_id)
        n = self._recent_denials(agent_id, t)
        return {"agent_id": agent_id, "recent_denials": n, "max_denials": pol.max_denials,
                "window_s": pol.denial_window, "quarantined": pol.max_denials > 0 and n >= pol.max_denials}

    def release(self, agent_id: str, approver: str, now: float | None = None) -> dict:
        """A human clears an agent's quarantine. Earlier denials stop counting from this moment."""
        with self.lock:
            return self.log.append("release", {"agent_id": agent_id, "approver": approver}, now)

    def submit(self, intent: Intent, now: float | None = None) -> dict:
        with self.lock:
            t = time.time() if now is None else now
            pol = self.policy_for(intent.agent_id)
            d: Decision = evaluate(intent, pol, self.log.history(intent.agent_id), t,
                                   recent_denials=self._recent_denials(intent.agent_id, t))
            rec = self.log.append("decision", {"agent_id": intent.agent_id, "intent": asdict(intent),
                                               "verdict": d.verdict, "reasons": d.reasons, "rule_ids": d.rule_ids}, t)
            if d.verdict == "DENY" and pol.max_denials > 0 and self._recent_denials(intent.agent_id, t) == pol.max_denials:
                self.log.append("quarantine", {"agent_id": intent.agent_id, "after_seq": rec["seq"],
                                               "recent_denials": pol.max_denials, "window_s": pol.denial_window}, t)
            out = {"verdict": d.verdict, "reasons": d.reasons, "decision_seq": rec["seq"], "execution": None}
            if d.verdict == "ALLOW":
                out["execution"] = self._execute(rec["seq"], intent, now)
            elif d.verdict == "ESCALATE":
                self.pending[rec["seq"]] = intent
            return out

    def approve(self, seq: int, approver: str, now: float | None = None) -> dict:
        with self.lock:
            intent = self.pending.pop(seq)
            self.log.append("approval", {"agent_id": intent.agent_id, "ref_seq": seq, "approver": approver}, now)
            return self._execute(seq, intent, now)

    def reject(self, seq: int, approver: str, now: float | None = None) -> dict:
        with self.lock:
            intent = self.pending.pop(seq)
            return self.log.append("rejection", {"agent_id": intent.agent_id, "ref_seq": seq, "approver": approver}, now)

    def _execute(self, ref_seq: int, intent: Intent, now: float | None) -> dict:
        try:
            tx = self.signer.send(intent.to, intent.amount, intent.denom, intent.memo)
            rec = self.log.append("execution", {"agent_id": intent.agent_id, "ref_seq": ref_seq,
                                                "amount": intent.amount, "to": intent.to, **tx}, now)
        except Exception as e:  # signing/broadcast failure is recorded, not hidden
            rec = self.log.append("execution_failed", {"agent_id": intent.agent_id, "ref_seq": ref_seq,
                                                       "error": str(e)}, now)
        return rec

    def anchor(self) -> dict:
        with self.lock:
            head = self.log.head()
            tx = self.signer.anchor(anchor_memo(head))
            self.log.append("anchor", {"agent_id": "_shield", "anchored_seq": head["seq"],
                                       "anchored_hash": head["hash"], **tx})
            return {"head": head, **tx}

    # -- second layer: on-chain spending rules --------------------------
    def sync_onchain(self, account_address: str | None = None) -> dict:
        if self.mode == "delegated":
            raise PermissionError("delegated mode: the owner key is not in the gateway. Run scripts/link_delegate.py "
                                  "with --update-rules on the owner side to change the on-chain limits")
        with self.lock:
            m = onchain.build_update_msg(self.signer.address, account_address or self.signer.address, self.policy)
            tx = self.signer.send_msgs([m], memo="agentshield:spending-rules")
            self.log.append("onchain_rules", {"agent_id": "_shield", "rule_id": onchain.RULE_ID,
                                              "per_tx_limit": self.policy.per_tx_limit,
                                              "daily_limit": self.policy.daily_limit, **tx})
            return tx

    def onchain_status(self, account_address: str | None = None) -> dict:
        chain_rules = self.signer.fetch_onchain_rules(account_address)
        return onchain.drift_report(self.policy, chain_rules)
