#!/usr/bin/env python3
"""Comprobaciones contra un nodo Bifrost (mainnet/testnet) por JSON-RPC.

Estaba BLOQUEADO en la auditoria: desde el sandbox no hay salida a los RPC
publicos (`public-01.mainnet.bifrostnetwork.com` -> timeout/000). Este script
deja el procedimiento listo para ejecutar en una maquina con salida a red o
contra el nodo local levantado con los snapshots de bifrost-snapshots.

Uso:
    python3 verify_live.py https://<rpc> [bloque_referencia]

Comprueba, en este orden:
  1. eth_chainId / eth_blockNumber / eth_getBlockByNumber  (identidad de cadena)
  2. ritmo real de bloque: 1000 bloques -> segundos/bloque
  3. eth_getCode en vault / socket / oracle  (existe bytecode? tamano?)
  4. eth_getStorageAt del Sudo key? (no: es storage de Substrate, ver abajo)
  5. state_getStorage de las claves FRAME que fijan los parametros del informe:
     TotalIssuance, Sudo.Key, Blaze.Activation, BtcSocketQueue.Authority,
     BtcSocketQueue.Socket, BtcSocketQueue.MaxFeeRate,
     BtcRegistrationPool.MultiSigRatio, RelayManager.Majority,
     RelayManager.IsHeartbeatOffenceActive, BfcStaking.Total
"""

import json
import sys
import urllib.request

from xxh64 import twox128

# Direcciones del repo `solidity-contract-configs` (config de 2023, sin
# verificar on-chain: el objetivo de este script es justamente verificarlas).
CONTRACTS = {
    "vault": "0xD85EB87caB9041ad00764b95796702b1104F42D7",
    "socket": "0xd551F33Ca8eCb0Be83d8799D9C68a368BA36Dd52",
    "oracle": "0x899aeefda82650EB65FC028a6671ab58Bab76199",
}

STORAGE = [
    ("Balances", "TotalIssuance"),
    ("Sudo", "Key"),
    ("Blaze", "Activation"),
    ("BtcSocketQueue", "Authority"),
    ("BtcSocketQueue", "Socket"),
    ("BtcSocketQueue", "BitcoinSocket"),
    ("BtcSocketQueue", "MaxFeeRate"),
    ("BtcSocketQueue", "MaxSocketMessageBytes"),
    ("BtcRegistrationPool", "MultiSigRatio"),
    ("BtcRegistrationPool", "CurrentRound"),
    ("BtcRegistrationPool", "ServiceState"),
    ("RelayManager", "Majority"),
    ("RelayManager", "IsHeartbeatOffenceActive"),
    ("BfcStaking", "Total"),
]


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if "error" in out:
        return {"error": out["error"]}
    return out.get("result")


def main():
    url = sys.argv[1].rstrip("/")
    chain_id = rpc(url, "eth_chainId", [])
    head = rpc(url, "eth_blockNumber", [])
    print(f"chainId   = {chain_id}  ({int(chain_id, 16) if isinstance(chain_id, str) else '?'})")
    print(f"blockNumber = {head}  ({int(head, 16) if isinstance(head, str) else '?'})")

    if isinstance(head, str):
        b = int(head, 16)
        ref = int(sys.argv[2]) if len(sys.argv) > 2 else b - 1000
        t0, t1 = None, None
        for bn, tag in ((ref, "prev"), (b, "head")):
            blk = rpc(url, "eth_getBlockByNumber", [hex(bn), False])
            ts = int(blk["timestamp"], 16) if blk else None
            print(f"  bloque {bn} timestamp {ts}")
            if tag == "prev":
                t0 = ts
            else:
                t1 = ts
        if t0 and t1:
            print(f"  => {(t1 - t0) / (b - ref):.4f} s/bloque  (el codigo asume "
                  f"MILLISECS_PER_BLOCK = 3000)")

    print("\n# bytecode desplegado")
    for name, addr in CONTRACTS.items():
        code = rpc(url, "eth_getCode", [addr, "latest"])
        n = (len(code) - 2) // 2 if isinstance(code, str) else -1
        print(f"  {name:7s} {addr}  code_bytes={n}  "
              f"{'SIN CODIGO (direccion muerta)' if n == 0 else ''}")

    print("\n# storage FRAME (valor crudo)")
    for pallet, item in STORAGE:
        k = "0x" + (twox128(pallet) + twox128(item)).hex()
        v = rpc(url, "state_getStorage", [k, None])
        print(f"  {pallet}.{item:22s} {k}\n      -> {v}")


if __name__ == "__main__":
    main()
