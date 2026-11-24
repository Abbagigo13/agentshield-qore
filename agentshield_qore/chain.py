"""Chain signer: builds hybrid (secp256k1 + ML-DSA-87) QoreChain transactions.

DRY_RUN builds and signs real hybrid txs offline but never broadcasts, so the demo
works without a funded account. Set AGENTSHIELD_DRY_RUN=0 + a funded testnet mnemonic to go live.
"""
from __future__ import annotations

import hashlib
import json
import os

import httpx
import qorsdk
from qorsdk import msg

FEE = {"amount": [{"denom": "uqor", "amount": "5000"}], "gas": "200000"}


def load_or_create_pqc(path: str) -> "qorsdk.PqcKeypair":
    if os.path.exists(path):
        d = json.load(open(path))
        return qorsdk.PqcKeypair(public_key=bytes.fromhex(d["public_key"]), secret_key=bytes.fromhex(d["secret_key"]))
    kp = qorsdk.generate_pqc_keypair()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    json.dump({"public_key": kp.public_key.hex(), "secret_key": kp.secret_key.hex()}, open(path, "w"))
    os.chmod(path, 0o600)
    return kp


class ChainSigner:
    def __init__(self, pqc: "qorsdk.PqcKeypair", network: str | None = None,
                 mnemonic: str | None = None, dry_run: bool | None = None):
        self.network = network or os.getenv("AGENTSHIELD_NETWORK", "testnet")
        self.dry_run = (os.getenv("AGENTSHIELD_DRY_RUN", "1") == "1") if dry_run is None else dry_run
        mnemonic = mnemonic or os.getenv("AGENTSHIELD_MNEMONIC")
        if not mnemonic:
            if not self.dry_run:
                raise RuntimeError("AGENTSHIELD_MNEMONIC is required when not in dry-run mode")
            mnemonic = qorsdk.generate_mnemonic()          # throwaway, offline only
        self.account = qorsdk.derive_native_account(mnemonic)
        self.pqc = pqc
        self.rest_url = qorsdk.PUBLIC_ENDPOINTS[self.network]["rest"]
        self.chain_id = qorsdk.create_client(self.network).network.chain_id or "qorechain-diana"
        self.address = self.account.address

    # -- account state -------------------------------------------------
    def _account_numbers(self) -> tuple[int, int]:
        if self.dry_run:
            return 0, 0
        r = httpx.get(f"{self.rest_url}/cosmos/auth/v1beta1/accounts/{self.address}", timeout=20)
        r.raise_for_status()
        acc = r.json()["account"]
        acc = acc.get("base_account", acc)
        return int(acc["account_number"]), int(acc["sequence"])

    def ensure_registered(self) -> dict:
        """Register the PQC key on-chain once (idempotent). Needs a funded testnet account."""
        if self.dry_run:
            return {"dry_run": True}
        num, seq = self._account_numbers()
        res = qorsdk.ensure_pqc_registered(account=self.account, pqc_keypair=self.pqc, chain_id=self.chain_id,
                                           account_number=num, rest_url=self.rest_url, fee=FEE, sequence=seq)
        return {"result": str(res)}

    # -- sending --------------------------------------------------------
    def send(self, to: str, amount: int, denom: str = "uqor", memo: str = "") -> dict:
        num, seq = self._account_numbers()
        message = msg.bank.send(from_address=self.address, to_address=to,
                                amount=[{"denom": denom, "amount": str(amount)}])

        def build(version):
            return qorsdk.build_hybrid_tx(account=self.account, pqc_keypair=self.pqc, messages=[message],
                                          fee=FEE, chain_id=self.chain_id, account_number=num, sequence=seq,
                                          memo=memo, sign_bytes_version=version)

        if self.dry_run:
            built = build("v2")
            return {"dry_run": True, "tx_hash": hashlib.sha256(built.tx_raw_bytes).hexdigest().upper(),
                    "tx_bytes": len(built.tx_raw_bytes), "pqc_sig_bytes": len(built.pqc_signature)}
        resp = qorsdk.hybrid_sign_and_broadcast(build, chain_id=self.chain_id, rest_url=self.rest_url)
        tr = resp.get("tx_response", resp)
        if int(tr.get("code", 0)) != 0:
            raise RuntimeError(f"broadcast failed: {tr.get('raw_log')}")
        return {"dry_run": False, "tx_hash": tr["txhash"]}

    def send_msgs(self, messages: list, memo: str = "") -> dict:
        """Sign and (unless dry-run) broadcast arbitrary messages as one hybrid transaction."""
        num, seq = self._account_numbers()

        def build(version):
            return qorsdk.build_hybrid_tx(account=self.account, pqc_keypair=self.pqc, messages=messages,
                                          fee=FEE, chain_id=self.chain_id, account_number=num, sequence=seq,
                                          memo=memo, sign_bytes_version=version)

        if self.dry_run:
            built = build("v2")
            return {"dry_run": True, "tx_hash": hashlib.sha256(built.tx_raw_bytes).hexdigest().upper(),
                    "tx_bytes": len(built.tx_raw_bytes)}
        resp = qorsdk.hybrid_sign_and_broadcast(build, chain_id=self.chain_id, rest_url=self.rest_url)
        tr = resp.get("tx_response", resp)
        if int(tr.get("code", 0)) != 0:
            raise RuntimeError(f"broadcast failed: {tr.get('raw_log')}")
        return {"dry_run": False, "tx_hash": tr["txhash"]}

    def fetch_onchain_rules(self, address: str | None = None):
        rest = qorsdk.RestClient(self.rest_url)
        try:
            return qorsdk.fetch_spending_rules(rest, address or self.address)
        finally:
            rest.close()

    def anchor(self, memo: str) -> dict:
        """Self-send 1 uqor with the log head in the memo: a public, timestamped commitment."""
        return self.send(self.address, 1, "uqor", memo)
