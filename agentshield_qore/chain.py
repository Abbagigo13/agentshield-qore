"""Chain signer: builds hybrid (secp256k1 + ML-DSA-87) QoreChain transactions.

DRY_RUN builds and signs real hybrid txs offline but never broadcasts, so the demo
works without a funded account. Set AGENTSHIELD_DRY_RUN=0 + a funded testnet mnemonic to go live.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import httpx
import qorsdk
from qorsdk import msg

# The testnet enforces a minimum gas price (it rejected 5000 uqor for 200000 gas; minimum was 20000 uqor).
# Defaults leave a safe margin and cost well under 0.1 QOR per transaction. Override with env vars if needed.
DEFAULT_GAS = 300_000
DEFAULT_GAS_PRICE = 0.15   # uqor per gas unit


def fee() -> dict:
    gas = int(os.getenv("AGENTSHIELD_GAS", DEFAULT_GAS))
    price = float(os.getenv("AGENTSHIELD_GAS_PRICE", DEFAULT_GAS_PRICE))
    return {"amount": [{"denom": "uqor", "amount": str(int(gas * price) + 1)}], "gas": str(gas)}


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
                 mnemonic: str | None = None, dry_run: bool | None = None, account_index: int = 0):
        self.network = network or os.getenv("AGENTSHIELD_NETWORK", "testnet")
        self.dry_run = (os.getenv("AGENTSHIELD_DRY_RUN", "1") == "1") if dry_run is None else dry_run
        mnemonic = mnemonic or os.getenv("AGENTSHIELD_MNEMONIC")
        if not mnemonic:
            if not self.dry_run:
                raise RuntimeError("AGENTSHIELD_MNEMONIC is required when not in dry-run mode")
            mnemonic = qorsdk.generate_mnemonic()          # throwaway, offline only
        self.account = qorsdk.derive_native_account(mnemonic, account_index)
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
                                           account_number=num, rest_url=self.rest_url, fee=fee(), sequence=seq)
        out = {"result": str(res)}
        h = getattr(res, "tx_hash", None) or (res.get("tx_hash") if isinstance(res, dict) else None)
        if h:
            out.update(self._wait_for_tx(h))   # next tx needs the updated account sequence
        return out

    def wait_tx_response(self, tx_hash: str, timeout: float = 60.0) -> dict:
        """Wait until the tx is in a block; return its tx_response. Raises if it failed on-chain.

        Broadcast only proves the node accepted the tx into its mempool. The account sequence does not
        advance, and the tx can still fail, until it is included in a block.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = httpx.get(f"{self.rest_url}/cosmos/tx/v1beta1/txs/{tx_hash}", timeout=20)
                if r.status_code == 200:
                    tr = r.json().get("tx_response", {})
                    if int(tr.get("code", 0)) != 0:
                        raise RuntimeError(f"tx {tx_hash} failed on-chain (code {tr.get('code')}): {tr.get('raw_log')}")
                    return tr
            except httpx.HTTPError:
                pass                              # rate limit or network blip: keep polling
            time.sleep(1.5)
        raise TimeoutError(f"tx {tx_hash} was not included in a block within {timeout:.0f}s")

    def _wait_for_tx(self, tx_hash: str, timeout: float = 60.0) -> dict:
        return {"height": self.wait_tx_response(tx_hash, timeout).get("height")}

    # -- sending --------------------------------------------------------
    def send(self, to: str, amount: int, denom: str = "uqor", memo: str = "") -> dict:
        num, seq = self._account_numbers()
        message = msg.bank.send(from_address=self.address, to_address=to,
                                amount=[{"denom": denom, "amount": str(amount)}])

        def build(version):
            return qorsdk.build_hybrid_tx(account=self.account, pqc_keypair=self.pqc, messages=[message],
                                          fee=fee(), chain_id=self.chain_id, account_number=num, sequence=seq,
                                          memo=memo, sign_bytes_version=version)

        if self.dry_run:
            built = build("v2")
            return {"dry_run": True, "tx_hash": hashlib.sha256(built.tx_raw_bytes).hexdigest().upper(),
                    "tx_bytes": len(built.tx_raw_bytes), "pqc_sig_bytes": len(built.pqc_signature)}
        resp = qorsdk.hybrid_sign_and_broadcast(build, chain_id=self.chain_id, rest_url=self.rest_url)
        tr = resp.get("tx_response", resp)
        if int(tr.get("code", 0)) != 0:
            raise RuntimeError(f"broadcast failed: {tr.get('raw_log')}")
        return {"dry_run": False, "tx_hash": tr["txhash"], **self._wait_for_tx(tr["txhash"])}

    def send_msgs(self, messages: list, memo: str = "", keep_response: bool = False) -> dict:
        """Sign and (unless dry-run) broadcast arbitrary messages as one hybrid transaction."""
        num, seq = self._account_numbers()

        def build(version):
            return qorsdk.build_hybrid_tx(account=self.account, pqc_keypair=self.pqc, messages=messages,
                                          fee=fee(), chain_id=self.chain_id, account_number=num, sequence=seq,
                                          memo=memo, sign_bytes_version=version)

        if self.dry_run:
            built = build("v2")
            return {"dry_run": True, "tx_hash": hashlib.sha256(built.tx_raw_bytes).hexdigest().upper(),
                    "tx_bytes": len(built.tx_raw_bytes)}
        resp = qorsdk.hybrid_sign_and_broadcast(build, chain_id=self.chain_id, rest_url=self.rest_url)
        tr = resp.get("tx_response", resp)
        if int(tr.get("code", 0)) != 0:
            raise RuntimeError(f"broadcast failed: {tr.get('raw_log')}")
        done = self.wait_tx_response(tr["txhash"])
        out = {"dry_run": False, "tx_hash": tr["txhash"], "height": done.get("height")}
        if keep_response:
            out["tx_response"] = done
        return out

    def fetch_onchain_rules(self, address: str | None = None):
        rest = qorsdk.RestClient(self.rest_url)
        try:
            return qorsdk.fetch_spending_rules(rest, address or self.address)
        finally:
            rest.close()

    def anchor(self, memo: str) -> dict:
        """Self-send 1 uqor with the log head in the memo: a public, timestamped commitment."""
        return self.send(self.address, 1, "uqor", memo)
