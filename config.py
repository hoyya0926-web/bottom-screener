"""스크리너 기준값. 숫자만 바꾸면 다음 실행부터 반영됩니다."""

# 소형주 제외 기준 (시가총액)
MIN_CAP_USD_B = 10       # 미국: 100억 달러
MIN_CAP_KRW_JO = 1       # 국내: 1조 원
CRYPTO_TOP_N = 40        # 코인: OKX 24시간 거래대금 상위 N개
CRYPTO_MIN_VOL_USD = 20e6  # 코인: 24시간 거래대금 최소 2천만 달러

# RSI
RSI_LEN = 14
WEEKLY_RSI_IMPORTANT = 20     # 주봉 RSI 이 값 이하면 "중요"
WEEKLY_RSI_LOOKBACK = 4       # 최근 몇 주 안에서 확인할지

# 다이버전스: R=피벗 오른쪽 확인 봉 수, fresh=두 번째 저점이 최근 몇 봉 안이어야 하는지
DIV = {
    "h4": {"R": 2, "fresh": 10, "min_gap": 4, "max_gap": 40},
    "d":  {"R": 2, "fresh": 10, "min_gap": 5, "max_gap": 40},
    "w":  {"R": 1, "fresh": 3,  "min_gap": 4, "max_gap": 40},
}
DIV_RSI_MAX = 45    # 첫 번째 저점의 RSI가 이 값 미만일 때만
DIV_RSI_DIFF = 2    # 두 번째 RSI 저점이 이만큼 이상 높아야 함

# 바닥 거래량 + FVG
FVG_LOOKBACK_DAYS = 25
FVG_MIN_GAP = 0.01        # 빈 구간 최소 1%
FVG_VOL_MULT = 2.5        # 20일 평균 대비 거래량 배수
FVG_BOTTOM_DAYS = 60      # 이 기간 최저점 근처여야 '바닥'

# 고점 후 횡보
BOX_MAX_RANGE = 0.10      # 박스 고가/저가 폭 10% 이내
BOX_MIN_WEEKS = 4
BOX_PEAK_ABOVE = 1.20     # 직전 고점이 박스 상단보다 20% 이상 높아야 함
BOX_PEAK_LOOKBACK = 120

# 점수
SCORE = {"w": 15, "d": 12, "h4": 8, "triple": 10, "dh4": 5,
         "fvg": 18, "box": 12, "w20": 40, "overlap": 5, "pop": 0.3}
TOP_N = 5

# 페이지 차트에 담을 타임프레임과 봉 수 (신호가 잡힌 종목만 저장)
CHART_BARS = {"1m": 600, "15m": 600, "1h": 600, "4h": 500, "1d": 750, "1w": 260, "1M": 120}
