"""통제변수용 데이터 수집 (사전등록 분석계획 1단계).

  data/lookback/ohlcv_YYYYMMDD.csv.gz : 과거 참조 기간(기본 2023-09-01~2024-10-21) 전 종목 시세.
                                         모멘텀·베타 계산에만 쓰고 분석 표본에는 넣지 않는다.
                                         (data/history/ 와 섞이지 않게 따로 저장)
  data/fundamental/fund_YYYYMMDD.csv.gz : 전 종목 BPS, PER, PBR, EPS, DIV, DPS (기본 2023-09-01~2026-10-22)
  data/fundamental/cd91.csv              : CD 91일물 금리(연 %, 무위험수익률용, 기간 전체 1회 요청)

이미 받은 날짜는 건너뛰므로 끊겨도 다시 실행하면 이어서 받는다.
KRX 로그인이 필요하므로 .env 에 KRX_ID, KRX_PW 가 있어야 한다.

사용 예:
    python fetch_controls_history.py
    python fetch_controls_history.py --lookback-end 20241021 --end 20261022
"""
import argparse
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from pykrx import bond, stock  # noqa: E402  (.env 로드 후 import 해야 자동 로그인됨)

import fetch_investor_history as fih  # noqa: E402
from fetch_investor_history import MARKETS, call  # noqa: E402

fih.REQUEST_INTERVAL = 0.5  # 요청 자체가 ~1초 걸리므로 대기는 짧게 (실패 시 call() 이 늘려가며 재시도)

LOOKDIR = ROOT / "data" / "lookback"
FUNDDIR = ROOT / "data" / "fundamental"


def fetch_ohlcv(day: str) -> pd.DataFrame | None:
    frames = []
    for market in MARKETS:
        px = call(stock.get_market_ohlcv, day, market=market)
        if px.empty:
            return None
        px = px.reset_index().rename(columns={"티커": "종목코드"})
        px.insert(0, "시장", market)
        frames.append(px)
    return pd.concat(frames, ignore_index=True)


def fetch_fund(day: str) -> pd.DataFrame | None:
    frames = []
    for market in MARKETS:
        f = call(stock.get_market_fundamental, day, market=market)
        if f.empty:
            return None
        f = f.reset_index().rename(columns={"티커": "종목코드"})
        f.insert(0, "시장", market)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def fetch_cd91(start: str, end: str) -> pd.DataFrame:
    """기간 전체 CD 91일물 금리를 한 번에 받는다."""
    y = call(bond.get_otc_treasury_yields, start, end, "CD")
    return y.reset_index().rename(columns={"수익률": "CD91"})[["일자", "CD91"]]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="20230901")
    p.add_argument("--lookback-end", default="20241021")
    p.add_argument("--end", default="20261022")
    args = p.parse_args()

    LOOKDIR.mkdir(parents=True, exist_ok=True)
    FUNDDIR.mkdir(parents=True, exist_ok=True)
    days = [d.strftime("%Y%m%d") for d in stock.get_previous_business_days(fromdate=args.start, todate=args.end)]
    todo = [d for d in days if not (FUNDDIR / f"fund_{d}.csv.gz").exists()
            or (d <= args.lookback_end and not (LOOKDIR / f"ohlcv_{d}.csv.gz").exists())]
    print(f"기간 {days[0]}~{days[-1]} {len(days)}영업일, 남음 {len(todo)}", flush=True)

    cd = fetch_cd91(days[0], days[-1])
    cd.to_csv(FUNDDIR / "cd91.csv", index=False, encoding="utf-8-sig")
    print(f"CD 91일물 {len(cd)}일 저장", flush=True)

    t0, skipped = time.time(), []
    for i, day in enumerate(todo, 1):
        if day <= args.lookback_end and not (LOOKDIR / f"ohlcv_{day}.csv.gz").exists():
            px = fetch_ohlcv(day)
            if px is None:
                skipped.append(day)
                continue
            px.to_csv(LOOKDIR / f"ohlcv_{day}.csv.gz", index=False, encoding="utf-8-sig")
        if not (FUNDDIR / f"fund_{day}.csv.gz").exists():
            f = fetch_fund(day)
            if f is None:
                skipped.append(day)
                continue
            # 펀더멘털 파일을 마지막에 저장 → 이 파일이 있으면 그날은 완료
            f.to_csv(FUNDDIR / f"fund_{day}.csv.gz", index=False, encoding="utf-8-sig")
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"{i}/{len(todo)} 완료 ({day}), 경과 {el / 60:.0f}분, 남은 예상 {el / i * (len(todo) - i) / 60:.0f}분", flush=True)

    if skipped:
        print(f"데이터 없음으로 건너뛴 날: {skipped}")
    print(f"저장 위치: {LOOKDIR.relative_to(ROOT)}, {FUNDDIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
