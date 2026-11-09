"""XXH64 / twox128 en Python puro (sin dependencias).

twox128(x) = xxh64(x, seed=0).to_le_bytes(8) || xxh64(x, seed=1).to_le_bytes(8)
que es exactamente como FRAME deriva el prefijo de storage de un pallet y el
sufijo de un storage item (StorageValue/StorageMap).
"""

M64 = (1 << 64) - 1
P1 = 11400714785074694791
P2 = 14029467366897019727
P3 = 1609587929392839161
P4 = 9650029242287828579
P5 = 2870177450012600261


def _rotl(x, r):
    return ((x << r) | (x >> (64 - r))) & M64


def _round(acc, inp):
    acc = (acc + inp * P2) & M64
    acc = _rotl(acc, 31)
    return (acc * P1) & M64


def _merge(acc, val):
    val = _round(0, val)
    acc ^= val
    return (acc * P1 + P4) & M64


def _read64(b, i):
    return int.from_bytes(b[i:i + 8], "little")


def xxh64(data: bytes, seed: int = 0) -> int:
    n = len(data)
    i = 0
    if n >= 32:
        v1 = (seed + P1 + P2) & M64
        v2 = (seed + P2) & M64
        v3 = seed & M64
        v4 = (seed - P1) & M64
        while i <= n - 32:
            v1 = _round(v1, _read64(data, i)); i += 8
            v2 = _round(v2, _read64(data, i)); i += 8
            v3 = _round(v3, _read64(data, i)); i += 8
            v4 = _round(v4, _read64(data, i)); i += 8
        h = (_rotl(v1, 1) + _rotl(v2, 7) + _rotl(v3, 12) + _rotl(v4, 18)) & M64
        h = _merge(h, v1)
        h = _merge(h, v2)
        h = _merge(h, v3)
        h = _merge(h, v4)
    else:
        h = (seed + P5) & M64

    h = (h + n) & M64

    while i <= n - 8:
        k = _round(0, _read64(data, i))
        h ^= k
        h = (_rotl(h, 27) * P1 + P4) & M64
        i += 8
    if i <= n - 4:
        h ^= (int.from_bytes(data[i:i + 4], "little") * P1) & M64
        h = (_rotl(h, 23) * P2 + P3) & M64
        i += 4
    while i < n:
        h ^= (data[i] * P5) & M64
        h = (_rotl(h, 11) * P1) & M64
        i += 1

    h ^= h >> 33
    h = (h * P2) & M64
    h ^= h >> 29
    h = (h * P3) & M64
    h ^= h >> 32
    return h


def twox128(name: str) -> bytes:
    b = name.encode()
    return xxh64(b, 0).to_bytes(8, "little") + xxh64(b, 1).to_bytes(8, "little")


if __name__ == "__main__":
    # autotest contra la implementacion de referencia si esta disponible
    try:
        import xxhash
    except ImportError:
        print("xxhash no instalado: autotest omitido; twox128('System') =", twox128("System").hex())
    else:
        ok = True
        for ln in range(0, 40):
            data = bytes(range(ln))
            ok &= xxh64(data, 0) == xxhash.xxh64(data, seed=0).intdigest()
            ok &= xxh64(data, 1) == xxhash.xxh64(data, seed=1).intdigest()
        print("autotest xxh64 0..39 bytes:", "OK" if ok else "FALLA")
        print("twox128('System') =", twox128("System").hex(),
              "(esperado 26aa394eea5630e07c48ae0c9558cef7)")
