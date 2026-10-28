# 바닥신호 스크리너

미국·국내 주식과 코인(OKX 시세, BingX·OKX 링크)을 매일 09:00 KST 일봉 마감 직후에 훑습니다.
아래 신호를 찾아 **텔레그램 · 카카오톡 · Gmail**로 Top 5를 보내고, 휴대폰에서 보는 무료 페이지를 갱신합니다.

- RSI 상승 다이버전스: 주봉·일봉·4시간봉, 세 개 모두 걸리면 1순위
- 주봉 RSI 20 이하: "중요" 표시
- 바닥 거래량 급증 + FVG 되돌림
- 고점 후 4주 이상 횡보

페이지에서는 종목마다 **1분 · 15분 · 1시간 · 4시간 · 일봉 · 주봉 · 월봉** 차트를 확대·이동하며 보고, 분석 글을 함께 읽을 수 있습니다.
분석 글에는 신호 설명, 타임프레임별 RSI, 지지·저항 가격, 체크 포인트가 들어갑니다.

비용은 0원입니다. GitHub(실행·페이지), Yahoo Finance·OKX(시세), 텔레그램·카카오(알림)를 모두 무료 범위에서 씁니다.

---

## 어떤 API를 어떻게 쓰나

| 용도 | 서비스 | 키 필요? | 어디에 쓰나 |
|---|---|---|---|
| 미국·국내 주식 시세 | Yahoo Finance (`yfinance`) | 없음 | `data.py` |
| 코인 시세 | OKX 공개 API `/api/v5/market/...` | 없음 | `data.py`, 페이지 실시간 차트 |
| 휴대폰 푸시 | 텔레그램 Bot API | 봇 토큰 | `notify.py` |
| 카카오톡 | 카카오 REST API "나에게 보내기" | REST API 키 + 토큰 | `notify.py`, `kakao_setup.py` |
| 메일 | Gmail SMTP | 앱 비밀번호 | `notify.py` |
| 자동 실행·페이지 | GitHub Actions · Pages | (자동) | `.github/workflows/` |

- 시세는 조회만 하므로 거래소 계정이나 API 키가 필요 없습니다. BingX·OKX API 키는 주문이나 잔고 조회용이라 이 도구에는 쓰지 않습니다.
- 키와 토큰은 코드에 적지 않습니다. GitHub **Secrets**에 넣으면 실행할 때만 꺼내 쓰고, 로그에도 가려져 나옵니다.

---

## 설치 순서 (처음 한 번, PC 권장 · 30분 정도)

### 1. GitHub 저장소
1. github.com에서 **New repository**를 누릅니다. 이름은 예를 들어 `bottom-screener`로 하고 **Public**을 고릅니다. 무료로 페이지를 띄우려면 공개 저장소여야 하며, 저장소에 개인정보는 들어가지 않습니다.
2. **Add file → Upload files**로 이 폴더의 파일을 모두 올립니다.
3. `.github` 폴더가 안 올라가면 **Add file → Create new file**에서 이름을 `.github/workflows/daily.yml`로 적고 같은 파일 내용을 붙여 넣습니다. `kakao-setup.yml`도 같은 방법으로 만듭니다.

### 2. 페이지 켜기 (휴대폰에서 보는 화면)
1. **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 바꿉니다.
2. 페이지 주소는 `https://<아이디>.github.io/<저장소이름>/`입니다. 끝의 `/`까지 포함해 정확히 적어 둡니다.
3. **Settings → Secrets and variables → Actions → Variables** 탭에서 `PAGE_URL`을 만들고 이 주소를 넣습니다.

### 3. 텔레그램
1. 텔레그램에서 **@BotFather** → `/newbot` → 이름 정하기 → **토큰**을 받습니다.
2. 만든 봇과 대화를 열고 아무 메시지나 보냅니다.
3. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates`를 열면 `"chat":{"id":숫자` 부분의 숫자가 **chat ID**입니다.
4. Secrets에 `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`로 등록합니다.

### 4. 카카오톡 (나와의 채팅으로 받기)
카카오 메뉴 이름은 개편 때마다 조금씩 바뀝니다. 비슷한 이름을 찾으면 됩니다.

1. [developers.kakao.com](https://developers.kakao.com) 로그인 → **내 애플리케이션 → 애플리케이션 추가**. 이름은 아무거나 넣습니다.
2. 앱 키에서 **REST API 키**를 복사합니다. Secrets에 `KAKAO_REST_KEY`로 등록합니다.
3. **카카오 로그인**을 활성화하고, **Redirect URI**에 페이지 주소(`PAGE_URL`과 글자 하나까지 같게)를 등록합니다.
4. **플랫폼(또는 제품 링크 관리) → Web 사이트 도메인**에 `https://<아이디>.github.io`를 등록합니다. 메시지 안 링크가 열리려면 필요합니다.
5. **동의항목**에서 **카카오톡 메시지 전송(talk_message)**을 "선택 동의"로 켭니다.
6. 보안 메뉴에서 **Client Secret**이 켜져 있으면 그 값을 Secrets에 `KAKAO_CLIENT_SECRET`으로 등록합니다. 꺼져 있으면 건너뜁니다.
7. **GH_PAT 만들기:** 카카오 토큰은 2달마다 바뀌어서, 자동으로 바꿔 넣으려면 GitHub 토큰이 필요합니다.
   - GitHub 오른쪽 위 프로필 → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
   - Repository access는 이 저장소만, Permissions는 **Secrets: Read and write**로 설정합니다.
   - 만든 토큰을 Secrets에 `GH_PAT`로 등록합니다.
8. 먼저 7단계(첫 실행)를 해서 페이지가 뜨게 합니다. 그다음 페이지 맨 아래 **"휴대폰 앱처럼 쓰기 · 알림 연결 도우미"**를 엽니다.
9. REST API 키를 넣고 **카카오 로그인**을 누릅니다. 동의하고 나면 페이지로 돌아와 **인증 코드**가 보입니다.
10. 코드를 복사하고 **kakao-setup 실행하러 가기**를 누릅니다. **Run workflow** 칸에 붙여 넣고 실행하면 카카오톡 "나와의 채팅"에 연결 확인 메시지가 옵니다. 코드는 몇 분 안에 만료되니 바로 실행하세요.

이후에는 매일 토큰을 새로 받고, 갱신 토큰이 바뀌면 `GH_PAT`로 자동 저장합니다. GH_PAT 없이도 쓸 수 있지만, 그 경우 2달마다 8~10단계를 다시 해야 합니다.

### 5. Gmail (선택)
1. Google 계정 → 보안에서 **2단계 인증**을 켭니다.
2. **앱 비밀번호**를 만들어 16자리를 받습니다.
3. Secrets에 `GMAIL_USER`(보내는 주소), `GMAIL_APP_PASSWORD`(16자리), `MAIL_TO`(받을 주소, 여러 개면 쉼표로 구분)를 등록합니다.

알림 채널은 원하는 것만 설정하면 됩니다. 값이 없는 채널은 건너뜁니다.

### 6. Secrets 한눈에 보기
| 이름 | 종류 | 필수 |
|---|---|---|
| `PAGE_URL` | Variable | 카카오톡 쓰면 필수 |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | Secret | 텔레그램 |
| `KAKAO_REST_KEY`, `KAKAO_REFRESH_TOKEN`(자동 생성), `KAKAO_CLIENT_SECRET`(선택), `GH_PAT` | Secret | 카카오톡 |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO` | Secret | 메일 |

### 7. 첫 실행
**Actions** 탭 → `daily-screener` → **Run workflow**를 누릅니다. 10~15분 뒤 알림이 오고 페이지가 실데이터로 바뀌면 성공입니다.
그다음부터는 매일 09:03 KST에 자동으로 돕니다. GitHub 사정으로 몇 분에서 수십 분 늦을 수 있습니다.

### 8. 휴대폰 홈 화면에 추가
- 아이폰 Safari: 공유 → **홈 화면에 추가**
- 안드로이드 Chrome: ⋮ → **홈 화면에 추가** 또는 **앱 설치**

앱처럼 전체 화면으로 열립니다.

---

## 알아둘 점
- **마감 기준:** 09:00 KST는 코인 일봉 마감 시각(UTC 00:00)입니다. 미국은 같은 날 새벽 마감분, 국내는 전 거래일 15:30 마감분이 반영됩니다. 신호 계산에는 마감된 봉만 씁니다.
- **차트 시각:** 국내·코인은 한국시간, 미국은 뉴욕 현지 시각으로 표시됩니다.
- **차트 데이터:** 주식 1분·15분·1시간봉은 실행 시점(09시) 스냅샷입니다. 코인 1분·15분·1시간봉은 페이지를 연 순간 OKX에서 실시간으로 받아 30초마다 갱신합니다. OKX가 막힌 환경에서는 스냅샷을 보여줍니다.
- **다이버전스 표시:** 4시간·일봉·주봉 판정은 서버 계산을 그대로 씁니다. 1분·15분·1시간·월봉은 페이지가 같은 규칙으로 즉석에서 계산합니다.
- **인기도:** 시장별 최근 20일 평균 거래대금 순위입니다. 코인은 OKX 24시간 거래대금 순위입니다.
- **소형주 제외:** 미국은 시총 100억 달러, 국내는 1조 원 미만을 Top 5와 알림에서 뺍니다. 페이지에서 "전체"를 고르면 볼 수 있습니다.
- **OKX 접속:** GitHub 서버는 미국에 있어서 OKX가 막힐 때가 있습니다. 그러면 Yahoo Finance 코인 시세로 자동 전환됩니다.
- **예약 실행 유지:** 공개 저장소는 60일 동안 커밋이 없으면 예약 실행이 멈춥니다. 매달 1일 `keepalive.txt`를 자동 커밋해 막아 둡니다.
- **카카오톡 제한:** 무료 "나에게 보내기"는 본인 카톡으로만 갑니다. 친구에게 보내려면 카카오 심사가 필요한 별도 권한이 있어야 합니다. 메시지는 200자 제한이라 요약만 보내고, "차트·분석 보기" 버튼으로 페이지를 엽니다.
- **문자(SMS):** 유료 발송 서비스(알리고, 솔라피 등)가 필요해서 넣지 않았습니다.

## 파일 구성
| 파일 | 내용 |
|---|---|
| `config.py` | 기준값 (RSI 20, 횡보 10%, 거래량 2.5배, 시총 하한 등) |
| `universe.py` | 조회할 종목 목록 |
| `data.py` | 시세 수집 |
| `signals.py` | 신호 판별 |
| `analysis.py` | 종목별 분석 글 |
| `notify.py` | 텔레그램·카카오톡·메일 |
| `run.py` | 전체 실행 (`--demo`, `--no-send`) |
| `demo.py` | 인터넷 없이 점검용 가상 데이터 |
| `kakao_setup.py` | 카카오 첫 연결 |
| `web/` → `build_page.py` → `docs/index.html` | 페이지. 모양을 고치면 `python build_page.py` 실행 |

이 도구는 기술적 신호를 자동으로 고르는 도구이며 투자 권유가 아닙니다.
