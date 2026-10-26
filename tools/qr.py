"""Tiny QR encoder (byte mode, version 3, ECC M) that emits a static inline SVG.
Usage: python3 tools/qr.py <url>  -> prints SVG path markup."""
import sys

def gf_tables():
    exp = [0] * 512; log = [0] * 256; x = 1
    for i in range(255):
        exp[i] = x; log[x] = i; x <<= 1
        if x & 0x100: x ^= 0x11D
    for i in range(255, 512): exp[i] = exp[i - 255]
    return exp, log
EXP, LOG = gf_tables()
def mul(a, b): return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]

def rs_ec(data, n):
    gen = [1]
    for i in range(n):
        nxt = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            nxt[j] ^= c; nxt[j + 1] ^= mul(c, EXP[i])
        gen = nxt
    rem = [0] * n
    for b in data:
        f = b ^ rem[0]; rem = rem[1:] + [0]
        for i in range(n): rem[i] ^= mul(gen[i + 1], f)
    return rem

N = 29; DATA_CW = 44; EC_CW = 26  # v3-M

def encode(text):
    d = text.encode()
    assert len(d) <= 42
    bits = "0100" + format(len(d), "08b") + "".join(format(b, "08b") for b in d)
    bits += "0" * min(4, DATA_CW * 8 - len(bits))
    bits += "0" * (-len(bits) % 8)
    cw = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    while len(cw) < DATA_CW: cw.append(pad[(len(cw) - len(bits) // 8) % 2])
    cw += rs_ec(cw, EC_CW)
    return "".join(format(b, "08b") for b in cw)

def build(text, mask):
    m = [[None] * N for _ in range(N)]; fn = [[False] * N for _ in range(N)]
    def put(r, c, v, f=True):
        m[r][c] = v
        if f: fn[r][c] = True
    def finder(r0, c0):
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = r0 + r, c0 + c
                if 0 <= rr < N and 0 <= cc < N:
                    v = 0 <= r <= 6 and 0 <= c <= 6 and (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                    put(rr, cc, v)
    finder(0, 0); finder(0, N - 7); finder(N - 7, 0)
    for r in range(-2, 3):
        for c in range(-2, 3):
            put(22 + r, 22 + c, max(abs(r), abs(c)) != 1)
    for i in range(8, N - 8):
        put(6, i, i % 2 == 0); put(i, 6, i % 2 == 0)
    put(N - 8, 8, True)
    for i in range(9):
        if not fn[8][i]: put(8, i, False)
        if not fn[i][8]: put(i, 8, False)
    for i in range(8):
        put(8, N - 1 - i, False); put(N - 1 - i, 8, False)
    bits = encode(text); k = 0; up = True; c = N - 1
    while c > 0:
        if c == 6: c -= 1
        for i in range(N):
            r = N - 1 - i if up else i
            for cc in (c, c - 1):
                if not fn[r][cc]:
                    b = int(bits[k]) if k < len(bits) else 0; k += 1
                    cond = [(r + cc) % 2 == 0, r % 2 == 0, cc % 3 == 0, (r + cc) % 3 == 0,
                            (r // 2 + cc // 3) % 2 == 0, (r * cc) % 2 + (r * cc) % 3 == 0,
                            ((r * cc) % 2 + (r * cc) % 3) % 2 == 0, ((r + cc) % 2 + (r * cc) % 3) % 2 == 0][mask]
                    m[r][cc] = bool(b ^ cond)
        up = not up; c -= 2
    # format info, ECC M = 00
    data = (0b00 << 3) | mask; rem = data << 10
    for i in range(14, 9, -1):
        if rem >> i & 1: rem ^= 0x537 << (i - 10)
    f = ((data << 10) | rem) ^ 0x5412
    fb = [(f >> i) & 1 for i in range(15)]
    for i in range(15):
        r1, c1 = (i, 8) if i < 6 else (7, 8) if i == 6 else (8, 8) if i == 7 else (8, 14 - i)
        r2, c2 = (8, N - 1 - i) if i < 8 else (N - 15 + i, 8)
        m[r1][c1] = bool(fb[i]); m[r2][c2] = bool(fb[i])
    return m

def penalty(m):
    p = 0
    for g in (m, list(map(list, zip(*m)))):
        for row in g:
            run = 1
            for i in range(1, N):
                if row[i] == row[i - 1]:
                    run += 1
                    if run == 5: p += 3
                    elif run > 5: p += 1
                else: run = 1
    for r in range(N - 1):
        for c in range(N - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]: p += 3
    pat = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    for g in (m, list(map(list, zip(*m)))):
        for row in g:
            for i in range(N - 10):
                w = [int(x) for x in row[i:i + 11]]
                if w == pat or w == pat[::-1]: p += 40
    dark = sum(sum(map(int, r)) for r in m)
    p += abs(dark * 100 // (N * N) - 50) // 5 * 10
    return p

def qr(text):
    return min((build(text, k) for k in range(8)), key=penalty)

def svg(text, quiet=2):
    m = qr(text); s = N + quiet * 2
    d = "".join(f"M{c + quiet} {r + quiet}h1v1h-1z" for r in range(N) for c in range(N) if m[r][c])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" shape-rendering="crispEdges" role="img" '
            f'aria-label="QR code for {text}"><rect width="{s}" height="{s}" fill="#fff"/><path fill="#1B1A33" d="{d}"/></svg>')

if __name__ == "__main__":
    print(svg(sys.argv[1]))
