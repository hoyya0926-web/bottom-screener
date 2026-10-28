"""카카오 인증 코드 → 토큰 발급 → KAKAO_REFRESH_TOKEN Secret 저장 → 연결 확인 메시지 발송
GitHub Actions의 kakao-setup 워크플로가 실행합니다. 토큰은 로그에 찍히지 않게 가립니다."""
import json
import os
import subprocess
import sys

import requests


def mask(v):
    if v:
        print(f"::add-mask::{v}")


def main():
    code = os.environ.get("CODE", "").strip()
    key = os.environ.get("KAKAO_REST_KEY", "").strip()
    secret = os.environ.get("KAKAO_CLIENT_SECRET", "").strip()
    page = os.environ.get("PAGE_URL", "").strip()
    mask(code)
    missing = [n for n, v in (("KAKAO_REST_KEY(Secret)", key), ("PAGE_URL(Variable)", page), ("GH_PAT(Secret)", os.environ.get("GH_TOKEN"))) if not v]
    if missing:
        sys.exit("먼저 등록해야 할 값: " + ", ".join(missing))

    data = {"grant_type": "authorization_code", "client_id": key, "redirect_uri": page, "code": code}
    if secret:
        data["client_secret"] = secret
    r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=20)
    j = r.json()
    if "refresh_token" not in j:
        print("토큰 발급 실패:", r.status_code, j.get("error"), j.get("error_description"))
        print("자주 있는 원인: 코드 만료(새로 받기) · 카카오 앱의 Redirect URI와 PAGE_URL이 글자 하나까지 같지 않음 · "
              "클라이언트 시크릿을 켰는데 KAKAO_CLIENT_SECRET 미등록")
        sys.exit(1)
    mask(j["access_token"]); mask(j["refresh_token"])

    p = subprocess.run(["gh", "secret", "set", "KAKAO_REFRESH_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
                       input=j["refresh_token"], text=True, capture_output=True)
    if p.returncode != 0:
        print("Secret 저장 실패. GH_PAT 권한(저장소 Secrets 읽기·쓰기)을 확인하세요.", p.stderr[:300])
        sys.exit(1)
    print("KAKAO_REFRESH_TOKEN 저장 완료")

    tpl = {"object_type": "text", "text": "바닥신호 스크리너 카카오톡 알림이 연결됐습니다. 매일 09시 일봉 마감 후 Top 5를 보내드립니다.",
           "link": {"web_url": page, "mobile_web_url": page}, "button_title": "페이지 열기"}
    s = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send", timeout=20,
                      headers={"Authorization": f"Bearer {j['access_token']}",
                               "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
                      data={"template_object": json.dumps(tpl, ensure_ascii=False)})
    if s.status_code == 200:
        print("확인 메시지 발송 완료 — 카카오톡 '나와의 채팅'을 확인하세요.")
    else:
        print("확인 메시지 실패:", s.status_code, s.text[:300])
        print("동의항목에서 '카카오톡 메시지 전송(talk_message)'을 켰는지, 웹 도메인에 페이지 주소를 등록했는지 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
