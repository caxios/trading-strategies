"""
스윙 매매용 손익비 계산기 — 지금 차트 + 최근 변동성만 사용

1) 최근 6개월 차트에서 스윙 저점(지지선)과 스윙 고점(저항선)을 찾는다.
2) 손절선 = 현재가 아래 가장 가까운 지지선 − 0.5·ATR  (꼬리에 걸려 털리지 않게 여유)
   익절선 = 현재가 위 가장 가까운 저항선
   단, 현재가에서 1·ATR(하루 평균 변동폭)보다 가까운 선은 노이즈 범위라 건너뛴다.
   해당하는 선이 없으면(신고가·신저가 구간) 보유기간 변동폭 σ·√H 만큼으로 대신한다.
3) 손익비 RR = (익절가 − 현재가) / (현재가 − 손절가)
4) 최근 변동성 기준으로, 보유기간 H일 안에 익절선·손절선에 닿을 확률과 손익분기 승률을 같이 보여준다.

설치:  pip install yfinance pandas numpy
실행:  python swing_rr.py MU AMD 005930.KS --days 20
코드:  swing_rr("MU", hold_days=20)
"""
import math                                    # log, exp, sqrt
from statistics import NormalDist              # 표준정규 누적분포 Φ
import numpy as np                             # 수치 계산
import pandas as pd                            # 시계열 처리

ATR_N = 14          # ATR 계산 기간 (Wilder 표준)
PIVOT_N = 5         # 스윙 고점/저점 판정: 좌우 5봉보다 높으면 고점, 낮으면 저점
LOOKBACK = 120      # 지지/저항을 찾을 기간 (약 6개월)
MIN_GAP_ATR = 1.0   # 현재가에서 1 ATR 이내의 선은 노이즈로 보고 무시
STOP_BUF_ATR = 0.5  # 손절선은 지지선보다 0.5 ATR 아래에 둠
VOL_N = 20          # 최근 변동성 σ 계산 기간 (약 1개월)


def fetch(ticker: str, period: str = "1y") -> pd.DataFrame:
    """수정주가 OHLC 다운로드."""
    import yfinance as yf                                         # 이 함수에서만 필요
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)  # 분할·배당 반영
    if df.empty:                                                  # 티커 오타 / 네트워크 문제
        raise ValueError(f"{ticker}: 데이터를 받지 못했습니다.")
    if isinstance(df.columns, pd.MultiIndex):                     # (항목, 티커) 2단 컬럼이면
        df.columns = df.columns.get_level_values(0)               # 1단으로 정리
    return df[["Open", "High", "Low", "Close"]].dropna()


def atr(df: pd.DataFrame, n: int = ATR_N) -> float:
    """최근 ATR: 하루 평균 변동폭(갭 포함)."""
    prev_close = df["Close"].shift(1)                             # 전일 종가
    tr = pd.concat([df["High"] - df["Low"],                       # 당일 고가-저가
                    (df["High"] - prev_close).abs(),              # 갭상승 포함
                    (df["Low"] - prev_close).abs()], axis=1).max(axis=1)  # 갭하락 포함 → 셋 중 최대 = True Range
    return tr.ewm(alpha=1 / n, adjust=False).mean().iloc[-1]      # Wilder 평균의 마지막 값


def swing_levels(df: pd.DataFrame, n: int = PIVOT_N):
    """스윙 고점(저항 후보)과 스윙 저점(지지 후보) 가격 목록."""
    win = 2 * n + 1                                               # 자기 자신 + 좌우 n봉
    is_high = df["High"] == df["High"].rolling(win, center=True).max()  # 좌우 n봉 중 최고 → 스윙 고점
    is_low = df["Low"] == df["Low"].rolling(win, center=True).min()     # 좌우 n봉 중 최저 → 스윙 저점
    return df["High"][is_high].to_numpy(), df["Low"][is_low].to_numpy()


def swing_rr(ticker: str, hold_days: int = 20, period: str = "1y") -> dict:
    df = fetch(ticker, period)                                    # 가격 데이터
    if len(df) < LOOKBACK:                                        # 6개월치도 없으면 차트 판단 불가
        raise ValueError(f"{ticker}: 데이터가 {len(df)}일뿐입니다 (최소 {LOOKBACK}일).")

    s0 = df["Close"].iloc[-1]                                     # 현재가 (최근 종가)
    a_tr = atr(df)                                                # 최근 ATR (가격 단위)
    sigma_d = np.log(df["Close"]).diff().iloc[-VOL_N:].std()      # 최근 20일 일간 로그수익률 표준편차
    move_H = sigma_d * math.sqrt(hold_days)                       # 보유기간 H일 통상 변동폭 (로그) = σ·√H

    highs, lows = swing_levels(df.iloc[-LOOKBACK:])               # 최근 6개월 지지/저항 후보

    # 손절선: 현재가보다 1 ATR 이상 아래 있는 지지선 중 가장 가까운 것 − 0.5 ATR
    supports = lows[lows <= s0 - MIN_GAP_ATR * a_tr]
    if len(supports):
        stop, stop_src = supports.max() - STOP_BUF_ATR * a_tr, "지지선"
    else:                                                         # 아래에 지지선이 없음 (신저가 구간)
        stop, stop_src = s0 * math.exp(-move_H), "변동성(σ√H)"

    # 익절선: 현재가보다 1 ATR 이상 위에 있는 저항선 중 가장 가까운 것
    resists = highs[highs >= s0 + MIN_GAP_ATR * a_tr]
    if len(resists):
        take, take_src = resists.min(), "저항선"
    else:                                                         # 위에 저항선이 없음 (신고가 구간)
        take, take_src = s0 * math.exp(move_H), "변동성(σ√H)"

    a = math.log(s0 / stop)                                       # 로그 손절폭
    b = math.log(take / s0)                                       # 로그 익절폭
    phi = NormalDist().cdf                                        # 표준정규 누적분포 Φ

    return {
        "현재가": round(s0, 2),
        "손절가": round(stop, 2),
        "익절가": round(take, 2),
        "손절%": round((stop / s0 - 1) * 100, 2),
        "익절%": round((take / s0 - 1) * 100, 2),
        "손익비 RR": round((take - s0) / (s0 - stop), 2),         # 이익폭 / 손실폭
        "근거(손절/익절)": f"{stop_src} / {take_src}",
        "ATR(하루 변동폭)%": round(a_tr / s0 * 100, 2),
        f"{hold_days}일 통상 변동폭%": round((math.exp(move_H) - 1) * 100, 2),
        # 손익분기 승률: 이 손익비에서 본전이 되려면 익절이 먼저 나와야 하는 비율 = a/(a+b)
        "손익분기 승률": round(a / (a + b), 3),
        # 추세가 없다고 볼 때 H일 안에 그 선을 한 번이라도 건드릴 확률 = 2·(1 − Φ(거리 / σ√H))  (반사원리)
        f"{hold_days}일 내 익절선 도달확률": round(2 * (1 - phi(b / move_H)), 3),
        f"{hold_days}일 내 손절선 도달확률": round(2 * (1 - phi(a / move_H)), 3),
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="스윙 매매 손익비 (차트 지지/저항 + 최근 변동성)")
    p.add_argument("tickers", nargs="+", help="예: MU AMD 005930.KS")
    p.add_argument("--days", type=int, default=20, help="예상 보유기간(거래일). 1~2주=5~10, 1~2달=20~40")
    args = p.parse_args()

    out = {}
    for t in args.tickers:
        try:
            out[t] = swing_rr(t, args.days)
        except ValueError as e:
            print(f"[건너뜀] {e}")
    if out:
        pd.set_option("display.unicode.east_asian_width", True)   # 한글 정렬
        print(pd.DataFrame(out).to_string())                     # 행 = 항목, 열 = 종목