#!/usr/bin/env python3
"""Decodifica el genesis de Bifrost (specs/bifrost-mainnet.json) a partir de las
claves de storage crudas, sin nodo.

Uso:
    python3 decode_genesis.py [ruta/al/chain-spec.json]

La clave de un StorageValue en FRAME es:
    twox128(nombre_del_pallet) ++ twox128(nombre_del_item)
por eso el script la calcula en vez de hardcodear hex. Los valores salen del
`genesis.raw.top` del chain spec, es decir: SON EL ESTADO DEL BLOQUE 0, no el
estado actual. Para el estado actual hace falta RPC (ver verify_live.py).
"""

import json
import sys

from xxh64 import twox128

SPEC = "specs/bifrost-mainnet.json"

ITEMS = [
    # (pallet, item, tipo)
    ("Balances", "TotalIssuance", "u128"),
    ("Sudo", "Key", "account"),
    ("BfcStaking", "Total", "u128"),
    ("BfcStaking", "MaxTotalSelected", "u32"),
    ("BfcStaking", "MaxFullSelected", "u32"),
    ("BfcStaking", "MaxBasicSelected", "u32"),
    ("BfcStaking", "MinTotalSelected", "u32"),
    ("BfcStaking", "DefaultFullValidatorCommission", "perbill"),
    ("BfcStaking", "MaxFullValidatorCommission", "perbill"),
    ("BfcStaking", "DefaultBasicValidatorCommission", "perbill"),
    ("BfcStaking", "MaxBasicValidatorCommission", "perbill"),
    ("BfcStaking", "ProductivityPerBlock", "u32"),
    ("BfcStaking", "InflationConfig", "inflation"),
    ("RelayManager", "Majority", "u32"),
    ("RelayManager", "InitialMajority", "u32"),
    ("RelayManager", "Round", "u32"),
    ("RelayManager", "HeartbeatSlashFraction", "perbill"),
    ("RelayManager", "IsHeartbeatOffenceActive", "bool"),
    ("RelayManager", "StorageCacheLifetime", "u32"),
    ("BfcOffences", "IsOffenceActive", "bool"),
    ("BfcOffences", "IsSlashActive", "bool"),
    ("BfcOffences", "FullMaximumOffenceCount", "u32"),
    ("BfcOffences", "BasicMaximumOffenceCount", "u32"),
    ("BfcOffences", "OffenceExpirationInSessions", "u32"),
    ("Democracy", "PublicPropCount", "u32"),
    ("Democracy", "ReferendumCount", "u32"),
    ("Democracy", "LowestUnbaked", "u32"),
    ("BfcUtility", "ProposalIndex", "u32"),
    ("Council", "Members", "vec20"),
    ("TechnicalCommittee", "Members", "vec20"),
]

UNIT = 10 ** 18


def key(pallet, item):
    return "0x" + (twox128(pallet) + twox128(item)).hex()


def dec(raw, kind):
    b = bytes.fromhex(raw[2:])
    if kind == "u32":
        return int.from_bytes(b, "little")
    if kind == "u128":
        return int.from_bytes(b, "little")
    if kind == "bool":
        return bool(b[0])
    if kind == "perbill":
        return int.from_bytes(b[:4], "little") / 1e9
    if kind == "account":
        return "0x" + b.hex()
    if kind == "vec20":
        # Compact<u32> length + N * AccountId(20 bytes)
        assert b[0] & 0b11 == 0, "solo modo compacto de un byte"
        n = b[0] >> 2
        return ["0x" + b[1 + i * 20:1 + (i + 1) * 20].hex() for i in range(n)]
    if kind == "inflation":
        # InflationInfo { expect: Range<Balance>, annual: Range<Perbill>, round: Range<Perbill> }
        u = lambda off: int.from_bytes(b[off:off + 16], "little")
        p = lambda off: int.from_bytes(b[off:off + 4], "little") / 1e9
        return {
            "expect_BFC": [u(0) / UNIT, u(16) / UNIT, u(32) / UNIT],
            "annual": [p(48), p(52), p(56)],
            "round": [p(60), p(64), p(68)],
        }
    raise ValueError(kind)


def main():
    spec = sys.argv[1] if len(sys.argv) > 1 else SPEC
    top = json.load(open(spec))["genesis"]["raw"]["top"]
    print(f"# {spec}  ({len(top)} claves en genesis.raw.top)\n")
    print("| item | valor |")
    print("|---|---|")
    for pallet, item, kind in ITEMS:
        k = key(pallet, item)
        raw = top.get(k)
        if raw is None:
            print(f"| {pallet}.{item} | *(ausente en genesis)* |")
            continue
        v = dec(raw, kind)
        if kind == "u128" and v > 10 ** 12:
            v = f"{v}  (~{v / UNIT:,.2f} BFC)"
        elif isinstance(v, list):
            v = ", ".join(v) if v else "(vacio)"
        elif isinstance(v, dict):
            v = json.dumps(v)
        print(f"| {pallet}.{item} | {v} |")


if __name__ == "__main__":
    main()
