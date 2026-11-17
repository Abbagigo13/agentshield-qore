"""Configuration: .env loading, per-agent policies, and one place that builds a Shield."""
from __future__ import annotations

import dataclasses
import json
import os

from .chain import ChainSigner, load_or_create_pqc
from .policy import Policy
from .receipts import ReceiptLog
from .shield import Shield


def load_env(path: str = ".env") -> None:
    """Tiny .env reader. Never overrides variables that are already set."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.split(" #")[0].strip() if not line.lstrip().startswith("#") else ""
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def policy_from_dict(d: dict, base: Policy) -> Policy:
    kw = dict(d)
    for key in ("allowed_recipients", "allowed_denoms"):
        if key in kw:
            kw[key] = frozenset(kw[key])
    return dataclasses.replace(base, **kw)


def load_policies(path: str, base: Policy) -> tuple[Policy, dict[str, Policy]]:
    """policies.json: {"default": {...}, "agents": {"agent-id": {...}}}. Agent entries override the default."""
    if not path or not os.path.exists(path):
        return base, {}
    cfg = json.load(open(path, encoding="utf-8"))
    default = policy_from_dict(cfg.get("default", {}), base)
    return default, {a: policy_from_dict(d, default) for a, d in cfg.get("agents", {}).items()}


def build_shield(data_dir: str | None = None) -> Shield:
    load_env()
    data = data_dir or os.getenv("AGENTSHIELD_DATA", "data")
    pqc = load_or_create_pqc(f"{data}/pqc.json")
    log = ReceiptLog(f"{data}/receipts.jsonl", pqc)
    allow = frozenset(x.strip() for x in os.getenv("AGENTSHIELD_RECIPIENTS", "").split(",") if x.strip().startswith("qor1"))
    default, agents = load_policies(os.getenv("AGENTSHIELD_POLICIES", "policies.json"), Policy(allowed_recipients=allow))
    return Shield(default, log, ChainSigner(pqc), agents)
