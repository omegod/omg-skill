#!/usr/bin/env python3
"""OKLCH ramp generator + contrast/chroma validator. Stdlib only.

  ramp  --hue 264 [--chroma 0.16] [--tint 0.006] [--prefix brand]
  check --pair "#5b6b7a" "#ffffff" [4.5] [--pair ...]
  check --tokens tokens.json
  info  "#3b82f6" | "oklch(0.62 0.17 264)"

Exit 1 if any check fails.
"""
import argparse, json, math, sys

# ---- sRGB <-> OKLab (Björn Ottosson) --------------------------------------

def _lin(u):  # gamma-encoded sRGB -> linear
    return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

def _gam(u):  # linear -> gamma-encoded sRGB
    if u <= 0.0031308:
        return 12.92 * u
    return 1.055 * (u ** (1 / 2.4)) - 0.055

def oklch_to_rgb(L, C, h):
    """-> (r,g,b) gamma-encoded, may fall outside [0,1] if out of gamut."""
    hr = math.radians(h)
    a, b = C * math.cos(hr), C * math.sin(hr)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        _gam(+4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
        _gam(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
        _gam(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
    )

def rgb_to_oklch(r, g, b):
    lr, lg, lb = _lin(r), _lin(g), _lin(b)
    l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb
    l_, m_, s_ = [math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s)]
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    A = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    h = math.degrees(math.atan2(B, A)) % 360
    return L, math.hypot(A, B), h
def in_gamut(r, g, b, eps=1e-4):
    return all(-eps <= v <= 1 + eps for v in (r, g, b))

def fit(L, C, h):
    """Reduce chroma until inside sRGB. Returns (L, C_fit, h)."""
    if in_gamut(*oklch_to_rgb(L, C, h)):
        return L, C, h
    lo, hi = 0.0, C
    for _ in range(40):
        mid = (lo + hi) / 2
        if in_gamut(*oklch_to_rgb(L, mid, h)):
            lo = mid
        else:
            hi = mid
    return L, lo, h

def to_hex(L, C, h):
    r, g, b = oklch_to_rgb(*fit(L, C, h))
    return "#" + "".join(f"{round(max(0.0, min(1.0, v)) * 255):02x}" for v in (r, g, b))

# ---- WCAG 2.1 contrast -----------------------------------------------------

def parse(s):
    """'#rgb' | '#rrggbb' | 'oklch(L C H)' -> (r,g,b) in 0..1."""
    s = s.strip()
    if s.lower().startswith("oklch"):
        nums = s[s.index("(") + 1:s.rindex(")")].replace("/", " ").replace(",", " ").split()
        L = float(nums[0].rstrip("%")) / (100 if "%" in nums[0] else 1)
        return oklch_to_rgb(L, float(nums[1]), float(nums[2]))
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"bad color: {s}")
    return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))

def luminance(r, g, b):
    lr, lg, lb = (_lin(max(0.0, min(1.0, v))) for v in (r, g, b))
    return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb

def contrast(c1, c2):
    l1, l2 = luminance(*parse(c1)), luminance(*parse(c2))
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)

# ---- ramp ------------------------------------------------------------------

# L values are perceptual lightness stops shared by every ramp.
STOPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]
NEU_L = [0.985, 0.967, 0.925, 0.871, 0.760, 0.646, 0.551, 0.451, 0.371, 0.283, 0.205]
ACC_L = [0.971, 0.936, 0.885, 0.816, 0.727, 0.646, 0.573, 0.492, 0.418, 0.352, 0.271]
ACC_K = [0.09, 0.16, 0.30, 0.50, 0.72, 0.90, 1.00, 0.94, 0.82, 0.68, 0.52]

def neutral_ramp(hue, tint=0.006):
    """Near-grey ramp tinted toward `hue`. Chroma peaks mid-ramp."""
    out = {}
    for s, L in zip(STOPS, NEU_L):
        c = tint * (0.35 + 0.65 * math.sin(math.pi * min(1.0, max(0.0, L))))
        out[s] = to_hex(L, c, hue)
    return out

def accent_ramp(hue, chroma=0.16):
    return {s: to_hex(L, chroma * k, hue) for s, L, k in zip(STOPS, ACC_L, ACC_K)}
# Max chroma by painted area. Big areas must stay near-neutral or the UI
# reads as "toy". Small areas carry the saturation.
BUDGET = {"page": 0.012, "surface": 0.020, "block": 0.060, "control": 0.190, "detail": 0.300}

SEMANTIC_HUE = {"success": 150, "warning": 70, "danger": 27, "info": 245}


def cmd_ramp(a):
    out = {"neutral": neutral_ramp(a.hue, a.tint), a.prefix: accent_ramp(a.hue, a.chroma)}
    for name, h in SEMANTIC_HUE.items():
        out[name] = accent_ramp(h, min(a.chroma + 0.02, 0.18))
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    for name, ramp in out.items():
        print(f"\n{name}")
        for s, hexv in ramp.items():
            L, C, h = rgb_to_oklch(*parse(hexv))
            print(f"  {name}-{s:<4} {hexv}  oklch({L:.3f} {C:.3f} {h:.1f})")
    return 0


def cmd_info(a):
    for c in a.colors:
        r, g, b = parse(c)
        L, C, h = rgb_to_oklch(r, g, b)
        gam = "in-gamut" if in_gamut(r, g, b) else "OUT-OF-GAMUT"
        onw, onb = contrast(c, "#ffffff"), contrast(c, "#000000")
        print(f"{c:<26} {to_hex(L, C, h)}  oklch({L:.3f} {C:.3f} {h:.1f})  {gam}")
        print(f"{'':<26} vs white {onw:5.2f}:1   vs black {onb:5.2f}:1")
    return 0


def cmd_check(a):
    fails = 0
    pairs = []
    if a.tokens:
        spec = json.loads(open(a.tokens, encoding="utf-8").read())
        for p in spec.get("pairs", []):
            pairs.append((p["fg"], p["bg"], float(p.get("min", 4.5)), p.get("label", "")))
        for item in spec.get("areas", []):
            role, color = item["role"], item["color"]
            cap = BUDGET.get(role)
            if cap is None:
                print(f"?? unknown area role '{role}' (use {'/'.join(BUDGET)})")
                fails += 1
                continue
            _, C, _ = rgb_to_oklch(*parse(color))
            ok = C <= cap + 1e-9
            fails += not ok
            print(f"{'ok  ' if ok else 'FAIL'} chroma {color} role={role:<8} C={C:.3f} cap={cap:.3f}")
    for p in a.pair or []:
        pairs.append((p[0], p[1], float(p[2]) if len(p) > 2 else 4.5, ""))

    for fg, bg, need, label in pairs:
        got = contrast(fg, bg)
        ok = got >= need - 1e-9
        fails += not ok
        tag = f" {label}" if label else ""
        print(f"{'ok  ' if ok else 'FAIL'} contrast {fg} on {bg} = {got:5.2f}:1 (need {need}){tag}")

    if not pairs and not a.tokens:
        print("nothing to check; pass --pair or --tokens", file=sys.stderr)
        return 2
    print(f"\n{'FAILED' if fails else 'PASS'}: {fails} problem(s)")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("ramp", help="generate neutral+accent+semantic ramps")
    r.add_argument("--hue", type=float, required=True)
    r.add_argument("--chroma", type=float, default=0.16)
    r.add_argument("--tint", type=float, default=0.006, help="neutral tint toward hue (0.002 austere .. 0.012 warm)")
    r.add_argument("--prefix", default="accent")
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_ramp)

    c = sub.add_parser("check", help="validate contrast + chroma budget")
    c.add_argument("--pair", nargs="+", action="append", metavar="FG BG [MIN]")
    c.add_argument("--tokens", help='JSON: {"pairs":[{"fg","bg","min","label"}],"areas":[{"role","color"}]}')
    c.set_defaults(fn=cmd_check)

    i = sub.add_parser("info", help="inspect colors")
    i.add_argument("colors", nargs="+")
    i.set_defaults(fn=cmd_info)

    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
