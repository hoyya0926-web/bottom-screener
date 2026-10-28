"""시세 수집 (API 키 필요 없음)
- 미국·국내 주식: Yahoo Finance(yfinance)
    신호용  일봉(5년) → 주봉, 1시간봉(120일) → 4시간봉
    차트용  1분봉(5일), 15분봉(30일), 1시간봉, 월봉(10년)  ※ 신호가 잡힌 종목만 추가 수집
- 코인: OKX 공개 API (일봉·주봉은 UTC 00:00 = 한국 09:00 마감 기준). 막히면 Yahoo로 대체
신호 계산에는 마감된 봉만 씁니다. 차트에는 진행 중인 마지막 봉도 보여줍니다.

봉 형식: {"t":[UTC ms], "lt":[현지 시각을 UTC처럼 적은 초], "o":[], "h":[], "l":[], "c":[], "v":[]}
 lt는 차트에 거래소 현지 시각(국내·코인=한국시간, 미국=뉴욕시간)으로 보이게 하려는 값입니다."""
import time
from datetime import datetime, timezone

import pandas as pd
import requests

import config as C
import universe as UV

UA = {"User-Agent": "Mozilla/5.0 bottom-screener"}
CLOSE = {"KR": (15, 30), "US": (16, 0)}
TZ = {"KR": "Asia/Seoul", "US": "America/New_York", "CR": "Asia/Seoul"}
AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}


def _empty():
    return {"t": [], "lt": [], "o": [], "h": [], "l": [], "c": [], "v": []}


def _tz(df, tz="UTC"):
    if df.empty:
        return df
    if df.index.tz is None:
        df = df.copy()
        df.index = df.index.tz_localize(tz)
    return df


def _df_to_bars(df, starts, tz):
    b = _empty()
    idx = pd.DatetimeIndex(starts)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    b["t"] = [int(x.timestamp() * 1000) for x in idx.tz_convert("UTC")]
    loc = idx.tz_convert(tz).tz_localize(None)
    b["lt"] = [int((x - pd.Timestamp("1970-01-01")).total_seconds()) for x in loc]
    for k, col in (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close"), ("v", "Volume")):
        b[k] = [float(x) for x in df[col].tolist()]
    return b


def _clean(df):
    if df.empty:
        return df
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if "Volume" in df:
        df = df.assign(Volume=df["Volume"].fillna(0))
    return df


def _drop_unfinished(df, mkt):
    """오늘 장이 아직 안 끝났으면(마감+10분 전) 오늘 날짜 봉을 버림"""
    if df.empty:
        return df
    df = _tz(df, TZ[mkt])
    now = pd.Timestamp.now(tz=TZ[mkt])
    hh, mm = CLOSE[mkt]
    if now < now.normalize() + pd.Timedelta(hours=hh, minutes=mm + 10):
        df = df[df.index.tz_convert(TZ[mkt]).normalize() < now.normalize()]
    return df


def _daily_weekly(d, mkt):
    d = _clean(d)
    if mkt == "KR":
        d = d[d["Volume"] > 0]
    d = _drop_unfinished(d, mkt)
    w = d.resample("W-FRI").agg(AGG).dropna()
    w_start = [t - pd.Timedelta(days=4) for t in w.index]  # 월요일 시작으로 표시
    return _df_to_bars(d, d.index, TZ[mkt]), _df_to_bars(w, w_start, TZ[mkt])


def _h4_from_h1(h, mkt, closed_only=True):
    """장 시작 시각부터 4시간씩 묶음 (미국 09:30–13:30, 13:30–16:00 / 국내 09:00–13:00, 13:00–15:30)"""
    h = _clean(h)
    if h.empty:
        return None
    h = _tz(h, TZ[mkt])
    if closed_only:
        h = _drop_unfinished(h, mkt)
    local = h.index.tz_convert(TZ[mkt])
    rows, starts = [], []
    for _, g in h.groupby(local.date):
        t0 = g.index[0]
        key = (g.index - t0) // pd.Timedelta(hours=4)
        for _, gg in g.groupby(key):
            starts.append(gg.index[0])
            rows.append({"Open": gg["Open"].iloc[0], "High": gg["High"].max(), "Low": gg["Low"].min(),
                         "Close": gg["Close"].iloc[-1], "Volume": gg["Volume"].sum()})
    return _df_to_bars(pd.DataFrame(rows), starts, TZ[mkt])


def _pick(df, sym):
    if df is None or df.empty:
        return pd.DataFrame()
    if not isinstance(df.columns, pd.MultiIndex):
        return df
    try:
        return df[sym]
    except KeyError:
        return pd.DataFrame()


def _download(symbols, **kw):
    import yfinance as yf
    if not symbols:
        return pd.DataFrame()
    for attempt in range(3):
        try:
            return yf.download(symbols, group_by="ticker", auto_adjust=True, threads=True, progress=False, **kw)
        except Exception as e:  # 야후가 가끔 끊김
            print("yfinance 재시도", attempt + 1, e)
            time.sleep(5 * (attempt + 1))
    return pd.DataFrame()


def fetch_stocks():
    """반환: [{s, n, m, venue, ysym, cap, bars:{h4,d,w}, _h1}]"""
    import yfinance as yf
    items = [{"s": s, "n": n, "m": "US", "ysym": s} for s, n in UV.US.items()]
    items += [{"s": code, "n": n, "m": "KR", "ysym": f"{code}.{mk}", "venue": "KOSPI" if mk == "KS" else "KOSDAQ"}
              for code, (n, mk) in UV.KR.items()]
    syms = [x["ysym"] for x in items]
    print(f"주식 {len(syms)}종목 일봉 수집")
    D = _download(syms, period="5y", interval="1d")
    print("1시간봉 수집")
    H = _download(syms, period="120d", interval="60m")
    out = []
    for x in items:
        try:
            d = _pick(D, x["ysym"])
            if d.empty or d["Close"].dropna().shape[0] < 80:
                continue
            x["bars"] = {}
            x["bars"]["d"], x["bars"]["w"] = _daily_weekly(d, x["m"])
            h = _clean(_pick(H, x["ysym"]))
            x["_h1"] = h
            x["bars"]["h4"] = _h4_from_h1(h, x["m"]) if not h.empty else None
            cap, exch = None, ""
            try:
                fi = yf.Ticker(x["ysym"]).fast_info
                cap = getattr(fi, "market_cap", None)
                exch = getattr(fi, "exchange", "") or ""
            except Exception:
                pass
            if x["m"] == "US":
                x["cap"] = round(cap / 1e9, 1) if cap else None
                x["venue"] = {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NYQ": "NYSE", "ASE": "AMEX"}.get(exch, "")
            else:
                x["cap"] = round(cap / 1e12, 2) if cap else None
            out.append(x)
        except Exception as e:
            print("건너뜀", x["s"], e)
    return out


# ---------- 코인 ----------
OKX = "https://www.okx.com/api/v5/market"
OKX_BAR = {"1m": "1m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1Dutc", "1w": "1Wutc", "1M": "1Mutc"}


def _okx_get(path, params):
    r = requests.get(f"{OKX}/{path}", params=params, headers=UA, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(j.get("msg"))
    return j["data"]


def _okx_rows_to_bars(rows):
    rows = sorted(rows, key=lambda x: int(x[0]))
    b = _empty()
    for x in rows:
        t = int(x[0])
        b["t"].append(t); b["lt"].append(t // 1000 + 9 * 3600)
        b["o"].append(float(x[1])); b["h"].append(float(x[2])); b["l"].append(float(x[3]))
        b["c"].append(float(x[4])); b["v"].append(float(x[5]))
    return b


def _okx_candles(inst, bar, n, closed_only=True):
    out, after, seen = [], None, set()
    while len(out) < n:
        p = {"instId": inst, "bar": bar, "limit": "100"}
        if after:
            p["after"] = after
        data = _okx_get("history-candles", p)
        data = [x for x in data if x[0] not in seen]
        if not data:
            break
        seen.update(x[0] for x in data)
        out += data
        after = data[-1][0]
        time.sleep(0.12)
    if closed_only:
        out = [x for x in out if x[8] == "1"]
    return _okx_rows_to_bars(out)


def _okx_recent(inst, bar, n=300):
    """최근 봉 (진행 중인 봉 포함), 차트용"""
    return _okx_rows_to_bars(_okx_get("candles", {"instId": inst, "bar": bar, "limit": str(n)}))


def fetch_crypto_okx():
    tick = _okx_get("tickers", {"instType": "SPOT"})
    rows = []
    for t in tick:
        base, _, quote = t["instId"].partition("-")
        if quote != "USDT" or base in UV.STABLES:
            continue
        vol = float(t.get("volCcy24h") or 0)  # 현물은 USDT 기준 거래대금
        if vol >= C.CRYPTO_MIN_VOL_USD:
            rows.append((vol, base))
    rows.sort(reverse=True)
    out = []
    for vol, base in rows[: C.CRYPTO_TOP_N]:
        inst = f"{base}-USDT"
        try:
            bars = {"h4": _okx_candles(inst, "4H", 600), "d": _okx_candles(inst, "1Dutc", 800),
                    "w": _okx_candles(inst, "1Wutc", 300)}
            if len(bars["d"]["c"]) < 80:
                continue
            out.append({"s": base, "n": UV.CRYPTO_NAMES.get(base, base), "m": "CR", "venue": "OKX",
                        "cap": None, "vol24": vol, "bars": bars, "src": "okx"})
            print("OKX", base)
        except Exception as e:
            print("OKX 건너뜀", base, e)
    return out


def _utc_closed(df):
    df = _tz(_clean(df), "UTC")
    now = pd.Timestamp.now(tz="UTC").normalize()
    return df[df.index.tz_convert("UTC").normalize() < now]


def fetch_crypto_yahoo():
    syms = [f"{s}-USD" for s in UV.CRYPTO_FALLBACK]
    D = _download(syms, period="5y", interval="1d")
    H = _download(syms, period="120d", interval="60m")
    out = []
    for s, ys in zip(UV.CRYPTO_FALLBACK, syms):
        try:
            d = _utc_closed(_pick(D, ys))
            if len(d) < 80:
                continue
            w = d.resample("W-SUN").agg(AGG).dropna()
            h1 = _tz(_clean(_pick(H, ys)), "UTC")
            hh = _utc_closed(h1).resample("4h", origin="epoch").agg(AGG).dropna()
            out.append({"s": s, "n": UV.CRYPTO_NAMES.get(s, s), "m": "CR", "venue": "Yahoo", "cap": None, "ysym": ys,
                        "src": "yahoo", "_h1": h1,
                        "bars": {"d": _df_to_bars(d, d.index, "Asia/Seoul"),
                                 "w": _df_to_bars(w, [t - pd.Timedelta(days=6) for t in w.index], "Asia/Seoul"),
                                 "h4": _df_to_bars(hh, hh.index, "Asia/Seoul")}})
        except Exception as e:
            print("Yahoo 코인 건너뜀", s, e)
    return out


def fetch_crypto():
    try:
        out = fetch_crypto_okx()
        if out:
            return out
        print("OKX 결과 없음 → Yahoo로 대체")
    except Exception as e:
        print("OKX 접속 실패 → Yahoo로 대체:", e)
    return fetch_crypto_yahoo()


# ---------- 차트용 추가 타임프레임 (신호 종목만) ----------
def _tail(b, n):
    return {k: v[-n:] for k, v in b.items()} if b else None


def add_chart_frames(items):
    """x["chart"] = {"1m","15m","1h","4h","1d","1w","1M"} 를 채움"""
    N = C.CHART_BARS
    ysyms = [x["ysym"] for x in items if x.get("ysym")]
    if ysyms:
        print(f"차트용 1분·15분·월봉 수집 {len(ysyms)}종목")
        M1 = _download(ysyms, period="5d", interval="1m")
        M15 = _download(ysyms, period="30d", interval="15m")
        MO = _download(ysyms, period="10y", interval="1mo")
    for x in items:
        ch = {"4h": _tail(x["bars"].get("h4"), N["4h"]), "1d": _tail(x["bars"]["d"], N["1d"]),
              "1w": _tail(x["bars"]["w"], N["1w"])}
        tz = TZ[x["m"]]
        try:
            if x.get("src") == "okx":
                inst = f"{x['s']}-USDT"
                for tf in ("1m", "15m", "1h"):
                    ch[tf] = _okx_recent(inst, OKX_BAR[tf], 300)
                ch["1M"] = _okx_candles(inst, "1Mutc", N["1M"], closed_only=False)
                # 차트에는 진행 중인 4H·일봉도 보이게 최근 봉을 이어 붙임
                for tf in ("4h", "1d"):
                    rec = _okx_recent(inst, OKX_BAR[tf], 5)
                    last = ch[tf]["t"][-1] if ch[tf] and ch[tf]["t"] else 0
                    for i, t in enumerate(rec["t"]):
                        if t > last:
                            for k in ch[tf]:
                                ch[tf][k].append(rec[k][i])
            elif x.get("ysym"):
                ys = x["ysym"]
                for tf, src in (("1m", M1), ("15m", M15)):
                    df = _tz(_clean(_pick(src, ys)), "UTC")
                    ch[tf] = _tail(_df_to_bars(df, df.index, tz), N[tf]) if not df.empty else None
                h1 = x.get("_h1")
                if h1 is not None and not h1.empty:
                    h1 = _tz(h1, "UTC")
                    ch["1h"] = _tail(_df_to_bars(h1, h1.index, tz), N["1h"])
                    if x["m"] != "CR":
                        ch["4h"] = _tail(_h4_from_h1(h1, x["m"], closed_only=False), N["4h"])
                mo = _tz(_clean(_pick(MO, ys)), tz)
                if not mo.empty:
                    ch["1M"] = _tail(_df_to_bars(mo, mo.index, tz), N["1M"])
        except Exception as e:
            print("차트 데이터 일부 실패", x["s"], e)
        x["chart"] = {k: v for k, v in ch.items() if v and v["c"]}
