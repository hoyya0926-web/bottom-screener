"""종목별 분석 글. 신호 결과와 시세에서 숫자를 뽑아 쉬운 문장으로 씁니다.
매수·매도 권유가 아니라 '지금 차트가 어떤 상태이고, 어디를 보면 되는지'를 적습니다."""
import signals as SG

TF_ORDER = [("15m", "15분"), ("1h", "1시간"), ("4h", "4시간"), ("1d", "일봉"), ("1w", "주봉"), ("1M", "월봉")]


def fpx(m, p):
    if p is None:
        return "—"
    if m == "KR":
        return f"{round(p):,}원"
    if m == "US":
        return f"${p:,.2f}"
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.3f}"
    return f"${p:.3g}"


def rsi_state(v):
    if v is None:
        return "—"
    if v <= 20:
        return "극단적 과매도"
    if v < 30:
        return "과매도"
    if v < 45:
        return "약세"
    if v <= 55:
        return "중립"
    if v < 70:
        return "강세"
    return "과매수"


def sma(c, n):
    return sum(c[-n:]) / n if len(c) >= n else None


def _last_rsi(b):
    if not b or len(b["c"]) < 20:
        return None
    r = SG.rsi(b["c"])
    return round(r[-1], 1) if r[-1] is not None else None


def build(x, a, dpw):
    """x: 종목(bars, chart 포함), a: signals.analyze 결과"""
    m, d, w = x["m"], x["bars"]["d"], x["bars"]["w"]
    ch = x.get("chart", {})
    c = d["c"]
    last = c[-1]
    dv, s = a["div"], a["s"]

    # 타임프레임별 RSI
    rsi = []
    for tf, name in TF_ORDER:
        src = {"4h": x["bars"].get("h4"), "1d": d, "1w": w}.get(tf) or ch.get(tf)
        v = _last_rsi(src)
        rsi.append({"tf": tf, "name": name, "v": v, "st": rsi_state(v)})

    # 추세
    ma = {n: sma(c, n) for n in (20, 60, 120)}
    below = [n for n, v in ma.items() if v and last < v]
    above = [n for n, v in ma.items() if v and last >= v]
    if len(below) == 3:
        trend = "일봉 종가가 20일·60일·120일 이동평균선 아래에 있어 하락 추세가 이어지는 중입니다."
    elif not below:
        trend = "일봉 종가가 20일·60일·120일 이동평균선 위에 있어 큰 흐름은 상승 쪽입니다."
    else:
        trend = f"일봉 종가가 {'·'.join(f'{n}일' for n in above)}선 위, {'·'.join(f'{n}일' for n in below)}선 아래에 있어 방향을 다투는 중입니다."
    w20 = sma(w["c"], 20)
    if w20:
        trend += f" 주봉으로는 20주선({fpx(m, w20)}) {'위' if w['c'][-1] >= w20 else '아래'}입니다."
    yr = 252 if dpw == 5 else 365
    hi52, lo52 = max(d["h"][-yr:]), min(d["l"][-yr:])
    pos = f"52주 고점 {fpx(m, hi52)}보다 {(1 - last / hi52) * 100:.0f}% 낮고, 52주 저점 {fpx(m, lo52)}보다 {(last / lo52 - 1) * 100:.0f}% 높은 자리입니다."

    # 신호 설명 · 지지/저항 · 체크 포인트
    sig, sup, res, watch = [], [], [], []
    tfn = {"w": "주봉", "d": "일봉", "h4": "4시간봉"}
    if s["w20"]:
        sig.append(f"주봉 RSI가 {a['wrsi']['v']:.1f}까지 내려갔습니다. 20 아래는 몇 달 동안 거의 매주 빠져야 나오는 숫자라 드뭅니다. 파는 힘이 바닥에 가까워졌다는 뜻이지만, 과매도 상태가 몇 주 더 이어질 수도 있습니다.")
        watch.append("주봉 RSI가 30 위로 올라오는 주가 나오면 과매도 구간을 벗어난 것입니다.")
    on = [k for k in ("w", "d", "h4") if dv[k]]
    if on:
        k = "d" if dv["d"] else on[0]
        v = dv[k]
        B = x["bars"][k]
        p1, p2 = B["l"][v["p1"]], B["l"][v["p2"]]
        sig.append(f"RSI 상승 다이버전스가 {'·'.join(tfn[t] for t in on)}에서 나왔습니다. {tfn[k]} 기준으로 가격 저점은 {fpx(m, p1)}에서 {fpx(m, p2)}까지 "
                   f"{(1 - p2 / p1) * 100:.1f}% 더 내려갔는데, RSI 저점은 {v['r1']:.0f}에서 {v['r2']:.0f}까지 올라왔습니다. 값은 더 싸졌는데 파는 힘은 약해졌다는 신호입니다.")
        if len(on) == 3:
            sig.append("짧은 4시간봉부터 긴 주봉까지 같은 신호가 겹쳐서, 한 시간대에서만 나온 경우보다 믿을 만합니다.")
        sup.append(("다이버전스 저점", p2))
        watch.append(f"{tfn[k]} 종가가 {fpx(m, p2)} 아래로 내려가면 저점이 또 깨진 것이라 다이버전스는 무효입니다.")
    if a["fvg"]:
        f = a["fvg"]
        sig.append(f"바닥 근처에서 거래량이 20일 평균의 {f['vx']:.1f}배 터지며 급등했고, 그때 비어 있던 가격 구간(FVG) {fpx(m, f['lo'])}~{fpx(m, f['hi'])}까지 다시 내려왔습니다. "
                   "급등을 만든 매수세가 같은 자리에서 다시 받쳐 주는지 시험하는 구간입니다.")
        sup.append(("FVG 하단", f["lo"]))
        res.append(("FVG 상단", f["hi"]))
        watch.append(f"종가가 FVG 하단({fpx(m, f['lo'])})을 지키면 매수세가 살아 있는 것이고, 깨고 내려가면 그 매수세가 밀린 것입니다.")
    if a["box"]:
        b = a["box"]
        sig.append(f"고점 {fpx(m, b['pk'])}에서 {b['dd'] * 100:.0f}% 빠진 뒤 {b['wk']:.1f}주째 {fpx(m, b['lo'])}~{fpx(m, b['hi'])} 안에서 움직이고 있습니다. "
                   "하락이 멈추고 사는 쪽과 파는 쪽이 힘겨루기를 하는 구간입니다.")
        sup.append(("박스 하단", b["lo"]))
        res.append(("박스 상단", b["hi"]))
        watch.append(f"박스 상단({fpx(m, b['hi'])})을 거래량을 동반해 넘으면 위쪽으로 방향이 정해진 신호이고, 하단({fpx(m, b['lo'])})을 깨면 추가 하락을 염두에 둬야 합니다.")
    for n in (20, 60):
        if ma[n] and ma[n] > last:
            res.append((f"{n}일선", ma[n]))
    if ma[20] and ma[20] > last:
        watch.append(f"일봉이 20일선({fpx(m, ma[20])}) 위에서 마감하고 일봉 RSI가 50을 넘으면 반등이 확인된 것으로 봅니다.")
    sup.append(("52주 저점", lo52))
    def uniq(lst, ok):
        seen = {}
        for lbl, p in lst:
            key = float(f"{p:.6g}")
            if ok(p) and key not in seen:
                seen[key] = (lbl, p)
        return list(seen.values())
    sup = sorted(uniq(sup, lambda p: p <= last * 1.001), key=lambda z: -z[1])[:3]
    res = sorted(uniq(res, lambda p: p >= last * 0.999), key=lambda z: z[1])[:3]

    # 제목
    if s["w20"] and on:
        head = "주봉 과매도 속 다이버전스 — 바닥 다지기 초기 신호"
    elif s["w20"]:
        head = "주봉 RSI 20 이하 — 드문 과매도 구간"
    elif s["div3"]:
        head = "주·일·4시간 다이버전스 동시 발생 — 여러 시간대에서 하락 힘 약화"
    elif a["fvg"]:
        head = "바닥 거래량 급증 뒤 FVG 되돌림 — 첫 매수세 자리 재시험"
    elif s["div2"]:
        head = "일봉·4시간 다이버전스 — 단기 하락 힘 약화"
    elif a["box"]:
        head = f"고점 이후 {a['box']['wk']:.0f}주 횡보 — 방향 결정 대기"
    else:
        head = f"{'·'.join(tfn[t] for t in on)} 다이버전스 — 하락 힘 약화 초기"
    extra = [lbl for ok, lbl in ((a["fvg"] and "FVG" not in head, "FVG"), (a["box"] and "횡보" not in head, "횡보"),
                                 (bool(on) and "다이버전스" not in head, "다이버전스")) if ok]
    if extra:
        head += " + " + "·".join(extra)

    rd = next(r for r in rsi if r["tf"] == "1d")["v"]
    summary = f"{pos} {trend}"
    if rd is not None:
        summary += f" 일봉 RSI는 {rd:.0f}({rsi_state(rd)})입니다."

    return {"head": head, "summary": summary, "signals": sig, "rsi": rsi,
            "support": [{"l": l, "p": float(f"{p:.6g}")} for l, p in sup],
            "resist": [{"l": l, "p": float(f"{p:.6g}")} for l, p in res],
            "watch": watch}
