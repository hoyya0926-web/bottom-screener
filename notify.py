"""알림 발송: 텔레그램 · 카카오톡(나에게 보내기) · Gmail
값은 GitHub 저장소 Settings → Secrets and variables → Actions 에 등록합니다. 값이 없는 채널은 건너뜁니다.
  텔레그램   TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
  카카오톡   KAKAO_REST_KEY, KAKAO_REFRESH_TOKEN, (선택) KAKAO_CLIENT_SECRET
  Gmail      GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO
  페이지 주소 PAGE_URL (Variables 탭)  ※ 카카오톡은 이 주소가 있어야 보냅니다
카카오 토큰은 실행할 때마다 새로 받고, 새 갱신 토큰이 나오면 .kakao_refresh_new 파일에 적어
워크플로가 Secret을 자동으로 바꿔 넣습니다."""
import html
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from analysis import fpx

MKT = {"US": "미국", "KR": "국내", "CR": "코인"}
DAYS = "월화수목금토일"
ROOT = os.path.dirname(os.path.abspath(__file__))


def page_url():
    return os.environ.get("PAGE_URL", "").strip()


def chart_url(r):
    if r["m"] == "KR":
        return f"https://www.tradingview.com/chart/?symbol=KRX:{r['s']}"
    if r["m"] == "US":
        pre = f"{r['venue']}:" if r.get("venue") else ""
        return f"https://www.tradingview.com/chart/?symbol={pre}{r['s'].replace('-', '.')}"
    return f"https://www.tradingview.com/chart/?symbol=OKX:{r['s']}USDT"


def short_tags(r):
    t = []
    if r["sig"]["w20"]:
        t.append(f"주RSI{r['wrsi']['v']:.0f}")
    if r["divTf"]:
        t.append("다이버" + "".join({"1w": "주", "1d": "일", "4h": "4H"}[x] for x in r["divTf"]))
    if r["fvg"]:
        t.append("FVG")
    if r["box"]:
        t.append(f"횡보{r['box']['wk']:.0f}주")
    return " ".join(t)


def compose(res, top, imp):
    a = datetime.fromisoformat(res["asOf"])
    ds = f"{a.month}/{a.day}({DAYS[a.weekday()]})"
    tag = "[데모] " if res.get("demo") else ""
    subject = f"{tag}{ds} 09:00 마감 바닥신호 Top {len(top)}"
    page = page_url()

    # 텍스트·메일
    t = [subject, ""]
    h = [f"<div style='font-family:sans-serif;max-width:640px'><h2 style='margin:0 0 12px'>{html.escape(subject)}</h2>"]
    g = [f"<b>{html.escape(subject)}</b>"]
    if imp:
        t.append("■ 중요 · 주봉 RSI 20 이하")
        h.append("<h3 style='color:#A3600E;margin:16px 0 6px'>중요 · 주봉 RSI 20 이하</h3><ul>")
        g.append("\n<b>⚠ 중요 · 주봉 RSI ≤ 20</b>")
        for r in imp:
            t.append(f"  - {r['n']} ({r['s']}) RSI {r['wrsi']['v']}")
            h.append(f"<li><a href='{chart_url(r)}'>{html.escape(r['n'])}</a> {r['s']} · RSI {r['wrsi']['v']}</li>")
            g.append(f"• <a href=\"{chart_url(r)}\">{html.escape(r['n'])}</a> {r['s']} · 주봉 RSI {r['wrsi']['v']}")
        h.append("</ul>")
        t.append("")
    t.append("■ Top 5")
    h.append("<h3 style='margin:16px 0 6px'>Top 5</h3>")
    g.append("\n<b>Top 5</b>")
    for i, r in enumerate(top, 1):
        an = r["an"]
        line = f"{r['n']} ({r['s']}, {MKT[r['m']]}) · {r['score']}점 · 종가 {fpx(r['m'], r['last'])} ({r['chg']:+.2f}%)"
        t += [f"{i}. {line}", f"   {an['head']}"] + [f"   · {x}" for x in an["signals"]]
        if an["watch"]:
            t.append(f"   체크: {an['watch'][0]}")
        t += [f"   차트: {chart_url(r)}", ""]
        sup = " / ".join(f"{z['l']} {fpx(r['m'], z['p'])}" for z in an["support"])
        rs = " / ".join(f"{z['l']} {fpx(r['m'], z['p'])}" for z in an["resist"])
        h.append(f"<div style='border-top:1px solid #ddd;padding:10px 0'><b>{i}. <a href='{chart_url(r)}'>{html.escape(r['n'])}</a></b> {r['s']} · {MKT[r['m']]} · <b>{r['score']}점</b>"
                 f" · 종가 {fpx(r['m'], r['last'])} ({r['chg']:+.2f}%)<br><b style='color:#A3600E'>{html.escape(an['head'])}</b>"
                 f"<p style='margin:6px 0'>{html.escape(an['summary'])}</p><ul style='margin:4px 0;padding-left:18px'>"
                 + "".join(f"<li>{html.escape(x)}</li>" for x in an["signals"]) + "</ul>"
                 + (f"<div>지지 {html.escape(sup)}</div>" if sup else "") + (f"<div>저항 {html.escape(rs)}</div>" if rs else "")
                 + "".join(f"<div style='color:#555'>체크 · {html.escape(x)}</div>" for x in an["watch"]) + "</div>")
        g.append(f"{i}. <a href=\"{chart_url(r)}\">{html.escape(r['n'])}</a> · {r['score']}점\n   {html.escape(an['head'])}"
                 + (f"\n   체크: {html.escape(an['watch'][0])}" if an["watch"] else ""))
    if not top:
        for arr in (t, g):
            arr.append("오늘은 조건에 맞는 종목이 없습니다.")
        h.append("<p>오늘은 조건에 맞는 종목이 없습니다.</p>")
    if page:
        t.append(f"차트·분석 전체 보기: {page}")
        h.append(f"<p><a href='{page}'>차트와 분석 전체 보기</a></p>")
        g.append(f"\n<a href=\"{page}\">차트·분석 전체 보기</a>")
    h.append("<p style='color:#888;font-size:12px'>자동으로 고른 기술적 신호이며 투자 권유가 아닙니다.</p></div>")

    # 카카오톡 (텍스트 템플릿 200자 제한)
    k = [f"{tag}{ds} 바닥신호"]
    if imp:
        k.append("⚠주봉RSI≤20 " + ", ".join(f"{r['n']} {r['wrsi']['v']:.0f}" for r in imp[:3]))
    for i, r in enumerate(top, 1):
        k.append(f"{i}.{r['n']} {r['score']}점 {short_tags(r)}")
    if not top:
        k.append("오늘은 조건에 맞는 종목이 없습니다.")
    kakao = ""
    for line in k:
        if len(kakao) + len(line) + 1 > 198:
            break
        kakao += ("\n" if kakao else "") + line
    return {"subject": subject, "text": "\n".join(t), "html": "".join(h), "tg": "\n".join(g), "kakao": kakao}


# ---------- 텔레그램 ----------
def send_telegram(msg):
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        print("텔레그램 설정 없음 → 건너뜀")
        return
    text = msg["tg"]
    if len(text) > 4000:
        text = text[:3990] + "…"
    r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=20,
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
    print("텔레그램", "OK" if r.status_code == 200 else f"실패 {r.status_code} {r.text[:200]}")


# ---------- 카카오톡 ----------
def _mask(v):
    if v and os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{v}")


def kakao_token(rest_key, refresh, secret=None):
    data = {"grant_type": "refresh_token", "client_id": rest_key, "refresh_token": refresh}
    if secret:
        data["client_secret"] = secret
    r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=20)
    j = r.json()
    if r.status_code != 200 or "access_token" not in j:
        raise RuntimeError(f"카카오 토큰 갱신 실패 {r.status_code} {j.get('error_description') or j}")
    _mask(j["access_token"])
    if j.get("refresh_token"):
        _mask(j["refresh_token"])
    return j


def send_kakao(msg):
    key, refresh = os.environ.get("KAKAO_REST_KEY"), os.environ.get("KAKAO_REFRESH_TOKEN")
    if not (key and refresh):
        print("카카오톡 설정 없음 → 건너뜀")
        return
    page = page_url()
    if not page:
        print("카카오톡: PAGE_URL이 없어 건너뜀 (메시지 링크에 필요)")
        return
    j = kakao_token(key, refresh, os.environ.get("KAKAO_CLIENT_SECRET"))
    if j.get("refresh_token"):
        with open(os.path.join(ROOT, ".kakao_refresh_new"), "w") as f:
            f.write(j["refresh_token"])
        print("카카오 갱신 토큰이 새로 발급됨 → Secret 자동 교체 예정")
    tpl = {"object_type": "text", "text": msg["kakao"],
           "link": {"web_url": page, "mobile_web_url": page}, "button_title": "차트·분석 보기"}
    r = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send", timeout=20,
                      headers={"Authorization": f"Bearer {j['access_token']}",
                               "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
                      data={"template_object": json.dumps(tpl, ensure_ascii=False)})
    print("카카오톡", "OK" if r.status_code == 200 else f"실패 {r.status_code} {r.text[:200]}")


# ---------- Gmail ----------
def send_mail(msg):
    user, pw, to = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD"), os.environ.get("MAIL_TO")
    if not (user and pw and to):
        print("메일 설정 없음 → 건너뜀")
        return
    m = MIMEMultipart("alternative")
    m["Subject"], m["From"], m["To"] = msg["subject"], user, to
    m.attach(MIMEText(msg["text"], "plain", "utf-8"))
    m.attach(MIMEText(msg["html"], "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw.replace(" ", ""))
        s.sendmail(user, [x.strip() for x in to.split(",")], m.as_string())
    print("메일 OK")


def send_all(msg):
    for fn in (send_telegram, send_kakao, send_mail):
        try:
            fn(msg)
        except Exception as e:  # 한 채널이 실패해도 다른 채널은 보냄
            print(fn.__name__, "실패:", e)
