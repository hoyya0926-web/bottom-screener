"""인터넷 없이 전체 흐름을 점검하는 가상 데이터 (python run.py --demo).
종목명은 실제지만 가격·거래량·신호는 모두 만들어낸 값입니다."""
import math
from datetime import datetime, timedelta, timezone

H4PD = 6  # 하루 4시간봉 6개


def _i32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _imul(a, b):
    return _i32((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF))


def rng(seed):
    st = [_i32(seed)]

    def f():
        a = _i32(st[0] + 0x6D2B79F5)
        st[0] = a
        t = _imul(a ^ ((a & 0xFFFFFFFF) >> 15), 1 | a)
        t = _i32(t + _imul(t ^ ((t & 0xFFFFFFFF) >> 7), 61 | t)) ^ t
        return ((t ^ ((t & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF) / 4294967296
    return f


def hstr(s):
    h = _i32(2166136261)
    for ch in s:
        h = _imul(h ^ ord(ch), 16777619)
    return h & 0xFFFFFFFF


def gs(r):
    u = v = 0.0
    while not u:
        u = r()
    while not v:
        v = r()
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)


def templates(W):
    D = H4PD
    T = lambda b: [(26, b + .085), (20, b + .09), (12, b + .022), (9, b + .05), (3, b + .017), (0, b + .032)]
    return {
        "triple": {"p": [(W*40, .10), (W*26, -.30), (W*18, -.10), (D*26, -.18), (D*20, -.31), (D*14, -.24), (D*6, -.36)] + T(-.357)},
        "dh4": {"p": [(W*40, -.20), (W*8, .25), (D*26, .18), (D*20, .05), (D*14, .12), (D*6, .02)] + T(.023)},
        "consol": {"p": [(W*40, 0), (D*72, .42), (D*66, .45), (D*46, .11), (D*38, .15), (D*28, .105), (D*16, .145), (D*6, .11), (0, .13)]},
        "consolDh4": {"p": [(W*40, 0), (D*72, .42), (D*66, .45), (D*46, .12), (D*36, .15), (D*26, .148), (D*20, .10), (D*14, .15), (D*6, .085)] + T(.088)},
        "wrsi": {"p": [(W*60, .30), (W*32, .40), (W*2, -.42), (D*6, -.45), (0, -.43)], "o": .01},
        "wrsiDh4": {"p": [(W*60, .30), (W*32, .40), (D*26, -.30), (D*20, -.42), (D*14, -.36), (D*6, -.47)] + T(-.467), "o": .01},
        "cap": {"p": [(W*30, .15), (D*40, -.02), (D*14, -.07), (48, -.12), (42, -.20), (36, -.08), (30, -.03), (12, -.10), (0, -.09)],
                "v": [(47, 42, 5), (41, 36, 3), (35, 30, 1.6)]},
        "capH4": {"p": [(W*30, .15), (D*40, -.02), (D*14, -.07), (48, -.12), (42, -.20), (36, -.08), (30, -.03)] + T(-.117),
                  "v": [(47, 42, 5), (41, 36, 3), (35, 30, 1.6)]},
        "wdivCap": {"p": [(W*40, .10), (W*26, -.30), (W*18, -.10), (D*14, -.20), (48, -.25), (42, -.37), (36, -.22), (30, -.18)] + T(-.254),
                    "v": [(47, 42, 5.5), (41, 36, 3), (35, 30, 1.6)]},
    }


def gen_h4(s, m, t, px, seed=0, vb=1e6):
    dpw = 7 if m == "CR" else 5
    W = H4PD * dpw
    r = rng(hstr(f"{s}#{seed}"))
    tp = templates(W).get(t)
    if not tp:
        pts, lv = [], 0.0
        for i in range(7, -1, -1):
            pts.append((round(i * W * 8), lv))
            lv += (r() - .5) * .34
        tp = {"p": pts}
    pts = sorted(tp["p"], key=lambda p: -p[0])
    unit = H4PD * dpw
    N = math.ceil(max(pts[0][0] + W * 8, 330 * H4PD) / unit) * unit
    pre = [(N - 1, pts[0][1] + (r() - .5) * .3)]
    cur = pts[0][0] + W * 6
    while cur < N - 1:
        pre.insert(0, (cur, pts[0][1] + (r() - .5) * .35))
        cur += W * 6
    pre.sort(key=lambda p: -p[0])
    allp = pre + [p for p in pts if p[0] < pre[-1][0]]
    lvl = [0.0] * N
    for j in range(len(allp) - 1):
        a0, l0 = allp[j]
        a1, l1 = allp[j + 1]
        for ba in range(a0, a1 - 1, -1):
            f = (a0 - ba) / ((a0 - a1) or 1)
            lvl[N - 1 - ba] = l0 + (l1 - l0) * f
    vm = [1.0] * N
    for f_, t_, mm in tp.get("v", []):
        for ba in range(f_, t_ - 1, -1):
            vm[N - 1 - ba] = mm
    base = px / math.exp(allp[-1][1])
    oa = tp.get("o", .03)
    ph = r() * 6.28
    per = W * (2.2 + r())
    ou = 0.0
    prev = base * math.exp(lvl[0])
    o_, h_, l_, c_, v_ = [], [], [], [], []
    for i in range(N):
        ou = ou * .85 + gs(r) * .002
        ba = N - 1 - i
        osc = oa * math.sin(6.2832 * i / per + ph) * min(1, max(0, (ba - H4PD * 28) / (H4PD * 10)))
        c = base * math.exp(lvl[i] + ou + osc)
        o = prev
        w1 = abs(gs(r)) * .0022
        w2 = abs(gs(r)) * .0022
        v = vb * vm[i] * math.exp(gs(r) * .35) * (1 + abs(lvl[i] - (lvl[i - 1] if i else lvl[i])) * 40)
        o_.append(o); c_.append(c); h_.append(max(o, c) * (1 + w1)); l_.append(min(o, c) * (1 - w2)); v_.append(v)
        prev = c
    return {"o": o_, "h": h_, "l": l_, "c": c_, "v": v_}, dpw


def _agg(b, k, t_src):
    out = {"t": [], "lt": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    for i in range(0, len(b["c"]) - k + 1, k):
        out["t"].append(t_src["t"][i]); out["lt"].append(t_src["lt"][i])
        out["o"].append(b["o"][i]); out["c"].append(b["c"][i + k - 1])
        out["h"].append(max(b["h"][i:i + k])); out["l"].append(min(b["l"][i:i + k])); out["v"].append(sum(b["v"][i:i + k]))
    return out


def _split(b, parts, step_s, r, n_parent):
    """마지막 n_parent개 봉을 parts개로 쪼개 하위 타임프레임 생성"""
    out = {"t": [], "lt": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    n = len(b["c"])
    for i in range(max(0, n - n_parent), n):
        o, c, H, L = b["o"][i], b["c"][i], b["h"][i], b["l"][i]
        pts, x = [o], o
        for k in range(1, parts):
            x = x * math.exp(gs(r) * .0015)
            pts.append(x)
        pts.append(c)
        drift = [(c - pts[-2]) * k / (parts) for k in range(parts + 1)]
        pts = [min(H, max(L, p + d)) for p, d in zip(pts, drift)]
        pts[-1] = c
        ws = [math.exp(gs(r) * .4) for _ in range(parts)]
        sw = sum(ws)
        sub = []
        for k in range(parts):
            so, sc = pts[k], pts[k + 1]
            sh = min(H, max(so, sc) * (1 + abs(gs(r)) * .0008))
            sl = max(L, min(so, sc) * (1 - abs(gs(r)) * .0008))
            sub.append([so, sh, sl, sc, b["v"][i] * ws[k] / sw])
        hi_k = max(range(parts), key=lambda k: sub[k][1]); sub[hi_k][1] = H
        lo_k = min(range(parts), key=lambda k: sub[k][2]); sub[lo_k][2] = L
        for k, (so, sh, sl, sc, sv) in enumerate(sub):
            out["t"].append(b["t"][i] + k * step_s * 1000); out["lt"].append(b["lt"][i] + k * step_s)
            out["o"].append(so); out["h"].append(sh); out["l"].append(sl); out["c"].append(sc); out["v"].append(sv)
    return out


# 종목, 이름, 시장, 시총(US·CR: $B / KR: 조원), 가격, 패턴, 시드, 거래소
UNIVERSE = [
    ("NVDA", "엔비디아", "US", 4400, 182, "triple", 0, "NASDAQ"),
    ("TSLA", "테슬라", "US", 1400, 430, "consol", 0, "NASDAQ"),
    ("PLTR", "팔란티어", "US", 420, 178, "wrsiDh4", 1, "NASDAQ"),
    ("AMD", "AMD", "US", 380, 235, "triple", 0, "NASDAQ"),
    ("HOOD", "로빈후드", "US", 110, 135, "dh4", 1, "NASDAQ"),
    ("MSTR", "스트래티지", "US", 90, 330, "cap", 0, "NASDAQ"),
    ("AAPL", "애플", "US", 3800, 255, "plain", 0, "NASDAQ"),
    ("MSFT", "마이크로소프트", "US", 3800, 515, "plain", 0, "NASDAQ"),
    ("NFLX", "넷플릭스", "US", 520, 1210, "plain", 0, "NASDAQ"),
    ("SOUN", "사운드하운드", "US", 6, 15, "triple", 0, "NASDAQ"),
    ("005930", "삼성전자", "KR", 600, 98000, "capH4", 0, "KOSPI"),
    ("000660", "SK하이닉스", "KR", 330, 455000, "wdivCap", 1, "KOSPI"),
    ("012450", "한화에어로스페이스", "KR", 52, 1020000, "dh4", 0, "KOSPI"),
    ("196170", "알테오젠", "KR", 24, 450000, "dh4", 0, "KOSDAQ"),
    ("035720", "카카오", "KR", 27, 61000, "consol", 0, "KOSPI"),
    ("005380", "현대차", "KR", 54, 255000, "plain", 0, "KOSPI"),
    ("035420", "NAVER", "KR", 37, 235000, "plain", 0, "KOSPI"),
    ("108490", "로보티즈", "KR", 0.7, 75000, "wrsi", 0, "KOSDAQ"),
    ("BTC", "비트코인", "CR", None, 111000, "consolDh4", 17, "OKX"),
    ("ETH", "이더리움", "CR", None, 3900, "dh4", 1, "OKX"),
    ("SOL", "솔라나", "CR", None, 190, "wrsi", 0, "OKX"),
    ("XRP", "리플", "CR", None, 2.45, "plain", 0, "OKX"),
    ("DOGE", "도지코인", "CR", None, 0.2, "plain", 0, "OKX"),
]
VOL24 = {"BTC": 2.1e9, "ETH": 1.2e9, "SOL": 6e8, "XRP": 5e8, "DOGE": 3e8}


def items():
    now = datetime.now(timezone(timedelta(hours=9)))
    end = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now < end:
        end -= timedelta(days=1)
    end_lt = int(end.replace(tzinfo=timezone.utc).timestamp())  # 한국시간 벽시계 초
    out = []
    for s, n, m, cap, px, t, seed, venue in UNIVERSE:
        raw, dpw = gen_h4(s, m, t, px, seed, 1e6 * (1 + hstr(s) % 7))
        N = len(raw["c"])
        lt = [end_lt - (N - i) * 4 * 3600 for i in range(N)]
        h4 = {"t": [(x - 9 * 3600) * 1000 for x in lt], "lt": lt, **raw}
        d = _agg(h4, H4PD, h4)
        w = _agg(d, dpw, d)
        mo = _agg(d, 21 if m != "CR" else 30, d)
        r = rng(hstr(s + "#chart"))
        h1 = _split(h4, 4, 3600, r, 150)
        m15 = _split(h1, 4, 900, r, 150)
        m1 = _split(m15, 15, 60, r, 40)
        it = {"s": s, "n": n, "m": m, "venue": venue, "cap": cap, "bars": {"h4": h4, "d": d, "w": w}}
        if m == "CR":
            it["vol24"] = VOL24.get(s)
        it["chart"] = {"1m": m1, "15m": m15, "1h": h1, "4h": h4, "1d": d, "1w": w, "1M": mo}
        out.append(it)
    return out
