# Live testnet verification

Everything below ran on **qorechain-diana** (QoreChain testnet) on 24 November 2026 with a testnet-only wallet.
Any transaction can be looked up on the public REST endpoint: `/cosmos/tx/v1beta1/txs/<hash>`.

## What was proven
| Claim | Result | Evidence |
|---|---|---|
| Hybrid secp256k1 + ML-DSA-87 transactions are accepted | Verified | Transactions below |
| PQC key registration with proof of possession | Verified | Owner and relayer keys both registered, `key_verified: True` |
| Policy-gated payment signed and broadcast | Verified | `scripts/live_check.py` step 5 |
| Receipt-log head anchored on-chain | Verified | Anchor tx below |
| On-chain spending rule written and read back | Verified | `GET /v1/onchain` reports "Chain rules match the gateway policy" |
| **The rule bounds the account owner's own payments** | **No (by design)** | A 1.5 QOR owner payment above the 1 QOR rule was accepted |
| **The rule bounds a linked delegate key** | **Verified** | A 1.5 QOR delegate payment was refused by the chain: `per-tx limit 1000000uqor exceeded (attempted 1500000): spending limit exceeded` |

## The finding that shaped the design
Spending rules limit linked keys, not the account owner. A gateway that signs as the owner is never bounded by the chain.
So the chain-level second layer only exists in **delegated mode**: the owner links a delegate key with the `send`
permission, a separate relayer account submits transactions and pays fees, and the chain bounds the delegate.
The owner key must stay out of the gateway.

## Transactions
| Step | Tx hash | Height |
|---|---|---|
| PQC key registration (owner) | `6F14BB5DFB5E48D93377A7299B28E049827C751C3710A832EE8228F2C36DF766` | n/a |
| Hybrid self-send | `64A4A897D0A6369481C1BDF5ECD1658388750671DDE33AE7A2E65840EA2637A4` | 10668046 |
| Receipt-log anchor | `60E84342EC2A733C9DE663FC1027F98A8BD11D7DFC6EE1A9A45A4CA88CF5542D` | 10668053 |
| Spending-rule write | `40F9D381A9F9A5FE6ED8C649830E1755C4B9AD2F53B39E1124B4DEFFD0F8CFA7` | 10668057 |
| Direct mode, 0.5 QOR (inside limit) | `75715CCF672E361A7A20D055E5943C8B64749D08937491DCB6BD295DDB60353A` | 10668287 |
| Direct mode, 1.5 QOR (above limit) **accepted** | `F7ECB2EBC32B786812246CB8C398667F42644D41EB987F9E67BB86848EA7F687` | 10668291 |
| Fund relayer | `3741598387B3A0AEB36DEDE340AFD16F0489CA8D9517412EC2FA658314B61FE2` | 10668713 |
| PQC key registration (relayer) | `9BB51D726A98FF0E642AA24358CEB8C885F2D7F4639C859D93B38136783CDF01` | 10668724 |
| Link delegate key + spending rule | `4115FDB599550E9E37EBE6A9A7E37560CEB3BC674E7465F25F707397ABBED0BE` | 10668730 |
| Delegate payment, 0.5 QOR (inside limit) | `B69EDC5A7BEE45D4D816D1DD08231A5265623CCF405BDDF4E2DF0F046373322E` | 10668829 |
| Delegate payment, 1.5 QOR (above limit) | **refused by the chain, no payment** | n/a |

## Addresses
Owner `qor1q4r70zaahl8qw0z76npht6e9wmce45g7flul48`, relayer `qor1tefp25jk3jw6kxwzsa3jcvztz5cusyjpyzcste`.

## Bugs the live run found and fixed
1. Fee too low (5000 uqor): the node requires at least 20000 uqor. Fee is now computed from gas and gas price.
2. Account-sequence mismatch: broadcast returns before inclusion. The signer now waits for the block and checks the result.
3. A delegate cannot pay its own owner ("recipient must differ from the account"): test payments go to the relayer.

## Reproduce
```bash
python scripts/live_check.py          # direct mode: 9 steps
python scripts/enforcement_check.py   # shows the owner is NOT bounded
python scripts/delegation_check.py    # shows the delegate IS bounded
```

## Not verified
Daily-cap enforcement on-chain, delegate key expiry and revocation, long-running delegated gateway operation,
and the MCP server against a real client.
