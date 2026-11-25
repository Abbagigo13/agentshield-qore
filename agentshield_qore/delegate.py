"""Chain-enforced delegation: the gateway signs payments with a LINKED key, not the owner key.

How it works (QoreChain abstract-account "authenticators"):
  * OWNER account holds the funds. It links a delegate key with the `send` permission and a spending rule.
    The chain bounds every payment that key authorizes (per-tx limit, daily cap, allowed denoms).
  * RELAYER account submits the transaction and pays the fee (its own hybrid ML-DSA-87 signature).
  * The delegate key signs a domain-separated digest. That signature is the authorization.
A compromised gateway can then spend at most what the on-chain rule allows. The owner key is never used here.

Direct owner transactions are NOT bounded by these rules (the owner is sovereign), which is why the owner key
must stay out of the gateway in production.
"""
from __future__ import annotations

import time

import qorsdk
import qorsdk.authenticator as auth
from nacl.signing import SigningKey

from . import onchain
from .chain import ChainSigner
from .policy import Policy

SCHEME = "ed25519"


class Delegate:
    """An ed25519 key that acts for the owner within on-chain limits."""

    def __init__(self, seed: bytes):
        if len(seed) != 32:
            raise ValueError("delegate seed must be 32 bytes")
        self.seed = seed
        self._sk = SigningKey(seed)
        self.pubkey = bytes(self._sk.verify_key)

    @classmethod
    def from_mnemonic(cls, mnemonic: str, index: int = 2) -> "Delegate":
        return cls(qorsdk.derive_svm_account(mnemonic, index).secret_key[:32])

    def link_proof(self, chain_id: str, owner: str):
        return auth.link_proof_ed25519(self.seed, chain_id=chain_id, account_address=owner)

    def sign_execute(self, chain_id: str, account: str, to: str, amount: str, nonce: int) -> bytes:
        digest = auth.cosmos_auth_sign_bytes(chain_id, account, self.pubkey, to, amount, nonce)
        return self._sk.sign(digest).signature


def link_msgs(owner: str, chain_id: str, delegate: Delegate, policy: Policy, expiry_unix: int | None = None,
              label: str = "agentshield") -> list:
    """[MsgUpdateSpendingRules, MsgRegisterAuthenticator]: send both in ONE tx signed by the owner."""
    proof = delegate.link_proof(chain_id, owner)
    return qorsdk.link_authenticator_msgs(
        owner=owner, chain_id=chain_id, scheme=SCHEME, pubkey=delegate.pubkey, permissions=["send"],
        expiry_unix=expiry_unix or int(time.time()) + 7 * 86_400, possession_proof=proof.possession_proof,
        label=label, spending_rule=onchain.policy_to_rules(policy))


class DelegatedSigner:
    """Same interface as ChainSigner.send, but payments are authorized by the delegate key via a relayer."""

    def __init__(self, relayer: ChainSigner, owner: str, delegate: Delegate):
        self.relayer, self.owner, self.delegate = relayer, owner, delegate
        self.dry_run = relayer.dry_run
        self.address = relayer.address      # the relayer pays fees and submits anchors
        self.network, self.chain_id, self.rest_url = relayer.network, relayer.chain_id, relayer.rest_url

    def _nonce(self) -> int:
        if self.dry_run:
            return 0
        rest = qorsdk.RestClient(self.rest_url)
        try:
            n = auth.fetch_auth_nonce(rest, self.owner, self.delegate.pubkey)
        finally:
            rest.close()
        return int(getattr(n, "nonce", n))

    def send(self, to: str, amount: int, denom: str = "uqor", memo: str = "") -> dict:
        amt = f"{int(amount)}{denom}"
        nonce = self._nonce()
        sig = self.delegate.sign_execute(self.chain_id, self.owner, to, amt, nonce)
        m = auth.execute_cosmos_msg(relayer=self.relayer.address, account=self.owner, scheme=SCHEME,
                                    pubkey=self.delegate.pubkey, signature=sig, to=to, amount=amt, nonce=nonce)
        out = self.relayer.send_msgs([m], memo, keep_response=True)
        resp = out.pop("tx_response", None)
        if resp is not None:
            auth.require_executions_succeeded(resp)   # a failed execution still leaves the tx at code 0
        out["via"] = "delegate"
        return out

    def anchor(self, memo: str) -> dict:
        return self.relayer.anchor(memo)

    def send_msgs(self, messages, memo="", keep_response=False):
        return self.relayer.send_msgs(messages, memo, keep_response)

    def fetch_onchain_rules(self, address: str | None = None):
        return self.relayer.fetch_onchain_rules(address or self.owner)
