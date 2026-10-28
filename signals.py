"""신호 판별. 테스트 페이지에 있던 로직을 그대로 옮겼습니다.
bars: {"t":[시작시각 ms], "o":[], "h":[], "l":[], "c":[], "v":[]}  (오래된 것 → 최신 순)"""
import math
import config as C


def rsi(c, p=C.RSI_LEN):
    r = [None] * len(c)
    if len(c) <= p:
        return r
    g = l = 0.0
    for i in range(1, p + 1):
        d = c[i] - c[i - 1]
        g += max(d, 0); l += max(-d, 0)
    g /= p; l /= p
    r[p] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    for i in range(p + 1, len(c)):
        d = c[i] - c[i - 1]
        g = (g * (p - 1) + max(d, 0)) / p
        l = (l * (p - 1) + max(-d, 0)) / p
        r[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return r


def pivot_lows(low, L, R):
    out = []
    for i in range(L, len(low) - R):
        if all(low[i - k] > low[i] for k in range(1, L + 1)) and all(low[i + k] >= low[i] for k in range(1, R + 1)):
            out.append(i)
    return out


def _rmin(r, i):
    vals = [r[k] for k in (i - 1, i, i + 1) if 0 <= k < len(r) and r[k] is not None]
    return min(vals) if vals else math.inf


def bull_div(b, r, cfg):
    """RSI 상승 다이버전스: 가격 저점은 낮아지고 RSI 저점은 높아짐"""
    low, n = b["l"], len(b["l"])
    pv = [i for i in pivot_lows(low, 3, cfg["R"]) if r[i] is not None]
    if not pv:
        return None
    p2 = pv[-1]
    if n - 1 - p2 > cfg["fresh"]:
        return None
    if any(low[i] < low[p2] for i in range(p2 + 1, n)):
        return None
    best = None
    for p1 in reversed(pv[:-1]):
        gap = p2 - p1
        if gap < cfg["min_gap"]:
            continue
        if gap > cfg["max_gap"]:
            break
        a1, a2 = _rmin(r, p1), _rmin(r, p2)
        if low[p2] < low[p1] and a2 > a1 + C.DIV_RSI_DIFF and a1 < C.DIV_RSI_MAX:
            s = a2 - a1
            if best is None or s > best["s"]:
                best = {"p1": p1, "p2": p2, "s": s, "r1": a1, "r2": a2}
    return best


def cap_fvg(d):
    """바닥 거래량 급증 + 상승 FVG 생성 후 그 구간까지 되돌림 (일봉)"""
    n = len(d["c"])
    for i in range(n - 1, max(24, n - C.FVG_LOOKBACK_DAYS) - 1, -1):
        a_h, c_l = d["h"][i - 2], d["l"][i]
        if c_l <= a_h or (c_l - a_h) / a_h < C.FVG_MIN_GAP:
            continue
        bl = min(d["l"][i - 2], d["l"][i - 1])
        mn = min(d["l"][max(0, i - C.FVG_BOTTOM_DAYS): i + 1])
        if bl > mn * 1.001:
            continue
        av = sum(d["v"][i - 23: i - 3]) / 20
        if av <= 0:
            continue
        mv, mi = max((d["v"][k], k) for k in range(i - 3, i + 1))
        if mv < av * C.FVG_VOL_MULT:
            continue
        after = d["l"][i + 1:]
        if not after or min(after) > c_l:
            continue
        if d["c"][-1] < a_h * 0.97:
            continue
        return {"a": i - 2, "c": i, "lo": a_h, "hi": c_l, "vx": mv / av, "vi": mi}
    return None


def consolidation(d, days_per_week):
    """고점 → 하락 → 최근 N주 박스권 횡보 (일봉)"""
    n = len(d["c"])
    hi, lo, L = -math.inf, math.inf, 0
    for k in range(n - 1, -1, -1):
        h, l = max(hi, d["h"][k]), min(lo, d["l"][k])
        if (h - l) / l > C.BOX_MAX_RANGE:
            break
        hi, lo, L = h, l, L + 1
    if L < days_per_week * C.BOX_MIN_WEEKS:
        return None
    st = n - L
    seg = range(max(0, st - C.BOX_PEAK_LOOKBACK), st)
    if not seg:
        return None
    pk, pi = max((d["h"][k], k) for k in seg)
    if pk < hi * C.BOX_PEAK_ABOVE:
        return None
    return {"st": st, "L": L, "wk": L / days_per_week, "hi": hi, "lo": lo, "pk": pk, "pi": pi, "dd": (pk - lo) / pk}


def analyze(bars, days_per_week):
    """bars = {"h4": ..., "d": ..., "w": ...} (h4는 없을 수 있음)"""
    R, div = {}, {}
    for tf in ("h4", "d", "w"):
        b = bars.get(tf)
        if not b or len(b["c"]) < 30:
            R[tf], div[tf] = None, None
            continue
        R[tf] = rsi(b["c"])
        div[tf] = bull_div(b, R[tf], C.DIV[tf])
    d = bars["d"]
    fvg = cap_fvg(d) if len(d["c"]) >= 60 else None
    box = consolidation(d, days_per_week) if len(d["c"]) >= 60 else None
    wmin, wi = math.inf, -1
    if R.get("w"):
        rw = R["w"]
        for i in range(max(0, len(rw) - C.WEEKLY_RSI_LOOKBACK), len(rw)):
            if rw[i] is not None and rw[i] < wmin:
                wmin, wi = rw[i], i
    s = {
        "div3": bool(div["w"] and div["d"] and div["h4"]),
        "div2": bool(div["d"] and div["h4"]),
        "fvg": bool(fvg), "box": bool(box),
        "w20": wmin <= C.WEEKLY_RSI_IMPORTANT,
    }
    return {"R": R, "div": div, "fvg": fvg, "box": box, "wrsi": {"v": wmin, "i": wi}, "s": s}


def score(a, pop):
    S, dv, s = C.SCORE, a["div"], a["s"]
    any_div = bool(dv["w"] or dv["d"] or dv["h4"])
    groups = int(any_div) + int(s["fvg"]) + int(s["box"]) + int(s["w20"])
    if not groups:
        return 0, 0
    sc = (S["w"] if dv["w"] else 0) + (S["d"] if dv["d"] else 0) + (S["h4"] if dv["h4"] else 0)
    sc += S["triple"] if s["div3"] else (S["dh4"] if s["div2"] else 0)
    sc += (S["fvg"] if s["fvg"] else 0) + (S["box"] if s["box"] else 0) + (S["w20"] if s["w20"] else 0)
    sc += max(0, groups - 1) * S["overlap"] + pop * S["pop"]
    return round(sc), groups
