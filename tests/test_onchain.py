import qorsdk
from agentshield_qore import onchain
from agentshield_qore.chain import ChainSigner
from agentshield_qore.policy import Policy
from agentshield_qore.receipts import ReceiptLog
from agentshield_qore.shield import Shield


def chain(rule=None):
    return qorsdk.SpendingRules(rules=(rule,) if rule else (), authenticator_rules=())


def test_rules_valid_and_bounded():
    r = onchain.policy_to_rules(Policy())[0]
    assert r["per_tx_limit"] == 1_000_000 and r["denom_limits"][0]["denom"] == "uqor"


def test_update_msg_builds():
    a = qorsdk.derive_native_account(qorsdk.generate_mnemonic()).address
    m = onchain.build_update_msg(a, a, Policy())
    assert m.type_url.endswith("MsgUpdateSpendingRules")


def test_drift_none_match_and_gaps():
    p = Policy()
    assert not onchain.drift_report(p, chain())["enforced_on_chain"]
    rule = onchain.policy_to_rules(p)[0]
    assert onchain.drift_report(p, chain(rule))["in_sync"]
    loose = {**rule, "per_tx_limit": 9_000_000}
    rep = onchain.drift_report(p, chain(loose))
    assert not rep["in_sync"] and rep["checks"][0]["status"] == "chain_looser"
    assert onchain.drift_report(p, chain({**rule, "daily_limit": 0}))["checks"][1]["status"] == "chain_unbounded"


def test_sync_dry_run_logs_receipt(tmp_path):
    kp = qorsdk.generate_pqc_keypair()
    s = Shield(Policy(), ReceiptLog(str(tmp_path / "r.jsonl"), kp), ChainSigner(kp, dry_run=True))
    tx = s.sync_onchain()
    assert tx["dry_run"] and s.log.seq == 1
