"""매일 실행: 수집 → 신호 계산 → 분석 글 → 페이지용 파일 저장 → 텔레그램·카카오톡·메일 발송
  python run.py           실제 시세 (GitHub Actions가 매일 09:03 KST에 실행)
  python run.py --demo    인터넷 없이 가상 데이터로 전체 흐름 점검 (발송 안 함)
  python run.py --no-send 실제 시세로 계산만, 발송 생략
결과: docs/results.json (목록·분석), docs/data/<종목>.json (차트 7개 타임프레임)"""
import json
import math
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone

import analysis
import config as C
import notify
import signals as SG

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
TFMAP = {"h4": "4h", "d": "1d", "w": "1w"}


def r6(x):
    return float(f"{x:.6g}")


def cap_pass(x):
    if x["cap"] is None:
        return True
    return x["cap"] >= (C.MIN_CAP_USD_B if x["m"] == "US" else C.MIN_CAP_KRW_JO)


def popularity(items):
    """시장별 최근 20일 평균 거래대금 순위 → 0~100 (코인은 OKX 24시간 거래대금)"""
    for m in ("US", "KR", "CR"):
        grp = [x for x in items if x["m"] == m]
        for x in grp:
            d = x["bars"]["d"]
            x["_tv"] = x.get("vol24") or sum(c * v for c, v in zip(d["c"][-20:], d["v"][-20:])) / 20
        grp.sort(key=lambda x: x["_tv"])
        for i, x in enumerate(grp):
            x["pop"] = round(100 * i / max(1, len(grp) - 1))


def fkey(x):
    return f"{x['m']}_{re.sub(r'[^A-Za-z0-9_-]', '_', x['s'])}"


def overlays(x, a):
    """차트에 그릴 표시. 위치는 봉 번호가 아니라 시각(lt)으로 넘겨서 어느 타임프레임에서도 찾을 수 있게 함"""
    B = x["bars"]
    div = {}
    for k, tf in TFMAP.items():
        v = a["div"][k]
        if v:
            b = B[k]
            div[tf] = {"t1": b["lt"][v["p1"]], "t2": b["lt"][v["p2"]], "p1": r6(b["l"][v["p1"]]), "p2": r6(b["l"][v["p2"]]),
                       "r1": round(v["r1"], 1), "r2": round(v["r2"], 1)}
    d = B["d"]
    fvg = box = None
    if a["fvg"]:
        f = a["fvg"]
        fvg = {"lo": r6(f["lo"]), "hi": r6(f["hi"]), "vx": round(f["vx"], 1), "t0": d["lt"][f["a"]], "tv": d["lt"][f["vi"]]}
    if a["box"]:
        b = a["box"]
        box = {"lo": r6(b["lo"]), "hi": r6(b["hi"]), "pk": r6(b["pk"]), "dd": round(b["dd"], 3), "wk": round(b["wk"], 1),
               "t0": d["lt"][b["st"]], "tp": d["lt"][b["pi"]]}
    w = a["wrsi"]
    wr = {"v": round(w["v"], 1) if w["v"] != math.inf else None, "t": B["w"]["lt"][w["i"]] if w["i"] >= 0 else None}
    return div, fvg, box, wr


def summarize(x, a, sc, groups):
    s = a["s"]
    combo = (["w20"] if s["w20"] else []) + (["div3"] if s["div3"] else (["div2"] if s["div2"] else [])) + [k for k in ("fvg", "box") if s[k]]
    div, fvg, box, wr = overlays(x, a)
    d = x["bars"]["d"]
    return {
        "s": x["s"], "n": x["n"], "m": x["m"], "venue": x.get("venue", ""), "cap": x["cap"], "capOk": cap_pass(x),
        "last": r6(d["c"][-1]), "chg": round((d["c"][-1] / d["c"][-2] - 1) * 100, 2),
        "pop": x["pop"], "score": sc, "groups": groups,
        "sig": s, "divTf": [TFMAP[k] for k in ("w", "d", "h4") if a["div"][k]], "combo": combo,
        "div": div, "fvg": fvg, "box": box, "wrsi": wr,
        "lastBar": datetime.fromtimestamp(d["lt"][-1], timezone.utc).strftime("%Y-%m-%d"),
        "file": f"data/{fkey(x)}.json",
    }


def chart_file(x):
    out = {}
    for tf, b in x.get("chart", {}).items():
        n = len(b["c"])
        out[tf] = [[b["lt"][i], r6(b["o"][i]), r6(b["h"][i]), r6(b["l"][i]), r6(b["c"][i]), r6(b["v"][i])]
                   for i in range(max(0, n - C.CHART_BARS.get(tf, n)), n)]
    return out


def main():
    demo = "--demo" in sys.argv
    send = not demo and "--no-send" not in sys.argv
    if demo:
        import demo as DM
        items = DM.items()
    else:
        import data
        items = data.fetch_stocks() + data.fetch_crypto()
    print(f"수집 완료 {len(items)}종목")
    popularity(items)

    hits = []
    for x in items:
        dpw = 7 if x["m"] == "CR" else 5
        a = SG.analyze(x["bars"], dpw)
        sc, groups = SG.score(a, x["pop"])
        if groups:
            hits.append((x, a, sc, groups, dpw))
    print(f"신호 종목 {len(hits)}개")
    if not demo:
        data.add_chart_frames([h[0] for h in hits])

    res = []
    shutil.rmtree(os.path.join(DOCS, "data"), ignore_errors=True)
    os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)
    for x, a, sc, groups, dpw in hits:
        r = summarize(x, a, sc, groups)
        r["an"] = analysis.build(x, a, dpw)
        with open(os.path.join(DOCS, r["file"]), "w", encoding="utf-8") as f:
            json.dump(chart_file(x), f, separators=(",", ":"))
        res.append(r)
    res.sort(key=lambda r: (-r["score"], -r["pop"]))

    now = datetime.now(KST)
    asof = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now < asof:
        asof -= timedelta(days=1)
    out = {
        "asOf": asof.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "generated": now.strftime("%Y-%m-%d %H:%M KST"),
        "demo": demo,
        "scanned": {m: sum(1 for x in items if x["m"] == m) for m in ("US", "KR", "CR")},
        "smallExcluded": {m: sum(1 for x in items if x["m"] == m and not cap_pass(x)) for m in ("US", "KR", "CR")},
        "items": res,
    }
    with open(os.path.join(DOCS, "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    size = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fs in os.walk(os.path.join(DOCS, "data")) for fn in fs)
    print(f"저장 docs/results.json · 차트 파일 {len(res)}개 {size // 1024}KB")

    top = [r for r in res if r["capOk"]][: C.TOP_N]
    imp = [r for r in res if r["capOk"] and r["sig"]["w20"]]
    msg = notify.compose(out, top, imp)
    print("\n" + msg["text"] + "\n\n[카카오톡]\n" + msg["kakao"])
    if send:
        notify.send_all(msg)


if __name__ == "__main__":
    main()
