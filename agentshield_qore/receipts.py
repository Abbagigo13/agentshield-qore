"""Tamper-evident, post-quantum-signed audit log.

Every record is canonical JSON, hash-chained to the previous record and signed with ML-DSA-87.
The head hash can be anchored on-chain, so anyone can check the log was not rewritten later.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import qorsdk

GENESIS = "0" * 64


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _hash(body: dict) -> str:
    return hashlib.sha256(canonical(body)).hexdigest()


class ReceiptLog:
    def __init__(self, path: str, keypair: "qorsdk.PqcKeypair"):
        self.path, self.kp = path, keypair
        self.seq, self.prev = 0, GENESIS
        self.executions: list[tuple[str, float, int]] = []   # (agent, ts, amount)
        self.denials: dict[str, list[float]] = {}            # agent -> timestamps of DENY decisions
        self.released: dict[str, float] = {}                 # agent -> last release timestamp
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        pub = path + ".pub"
        if not os.path.exists(pub):
            open(pub, "w").write(keypair.public_key.hex())
        if os.path.exists(path):
            for line in open(path):
                r = json.loads(line)
                self.seq, self.prev = r["seq"], r["hash"]
                self._index(r)

    def _index(self, r: dict) -> None:
        if r["kind"] == "execution":
            self.executions.append((r["agent_id"], r["ts"], r["amount"]))
        elif r["kind"] == "decision" and r.get("verdict") == "DENY":
            self.denials.setdefault(r["agent_id"], []).append(r["ts"])
        elif r["kind"] == "release":
            self.released[r["agent_id"]] = r["ts"]

    def denial_count(self, agent_id: str, since: float) -> int:
        return sum(1 for t in self.denials.get(agent_id, ()) if t > since)

    def append(self, kind: str, payload: dict, now: float | None = None) -> dict:
        body = {"v": 1, "seq": self.seq + 1, "ts": time.time() if now is None else now,
                "kind": kind, "prev_hash": self.prev, **payload}
        h = _hash(body)
        sig = qorsdk.pqc_sign(self.kp.secret_key, bytes.fromhex(h))
        rec = {**body, "hash": h, "sig": sig.hex()}
        with open(self.path, "a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
        self.seq, self.prev = rec["seq"], h
        self._index(rec)
        return rec

    def history(self, agent_id: str) -> list[tuple[float, int]]:
        return [(t, a) for (ag, t, a) in self.executions if ag == agent_id]

    def records(self):
        if os.path.exists(self.path):
            for line in open(self.path):
                yield json.loads(line)

    def head(self) -> dict:
        return {"seq": self.seq, "hash": self.prev}


def anchor_memo(head: dict) -> str:
    return f"agentshield:v1:{head['seq']}:{head['hash']}"


def verify_log(path: str, pubkey_hex: str | None = None) -> dict:
    """Verify hash chain + every ML-DSA-87 signature. Returns {ok, records, head, errors}."""
    pubkey_hex = pubkey_hex or open(path + ".pub").read().strip()
    pub = bytes.fromhex(pubkey_hex)
    errors, prev, n = [], GENESIS, 0
    for i, line in enumerate(open(path), 1):
        r = json.loads(line)
        n += 1
        body = {k: v for k, v in r.items() if k not in ("hash", "sig")}
        if r["seq"] != i:
            errors.append(f"line {i}: sequence gap (found seq {r['seq']})")
        if r["prev_hash"] != prev:
            errors.append(f"seq {r['seq']}: prev_hash does not match previous record")
        if _hash(body) != r["hash"]:
            errors.append(f"seq {r['seq']}: record content was modified")
        elif not qorsdk.pqc_verify(pub, bytes.fromhex(r["hash"]), bytes.fromhex(r["sig"])):
            errors.append(f"seq {r['seq']}: ML-DSA-87 signature invalid")
        prev = r["hash"]
    return {"ok": not errors, "records": n, "head": {"seq": n, "hash": prev}, "errors": errors}
