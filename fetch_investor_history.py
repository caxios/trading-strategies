"""일별 전 종목 투자주체별 순매수 + 전 종목 시세 히스토리 수집 (백테스트용).

영업일마다 하루치를 받아 data/history/ 에 날짜별 파일로 저장한다.
이미 받은 날짜는 건너뛰므로 중간에 끊겨도 다시 실행하면 이어서 받는다.

  data/history/netbuy_YYYYMMDD.csv.gz : 시장 × 투자자(외국인/기관/개인) × 전 종목 순매수
  data/history/ohlcv_YYYYMMDD.csv.gz  : 시장 × 전 종목 시세 (KRX 공식 종가, 등락률)
  data/history/sectors_YYYYMMDD.csv   : 종료일 기준 업종 분류 (1회)

KRX 로그인이 필요하므로 .env 에 KRX_ID, KRX_PW 가 있어야 한다.

사용 예:
    python fetch_investor_history.py                       # 최근 2년 (어제까지)
    python fetch_investor_history.py --start 20250101 --end 20251231
"""
import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from pykrx import stock  # noqa: E402  (.env 로드 후 import 해야 자동 로그인됨)

MARKETS = ["KOSPI", "KOSDAQ"]
INVESTORS = {"외국인": "외국인", "기관": "기관합계", "개인": "개인"}
REQUEST_INTERVAL = 0.7  # KRX 요청 간 대기(초)
RETRIES = 4
OUTDIR = ROOT / "data" / "history"


def call(fn, *args, **kwargs) -> pd.DataFrame:
    """KRX 요청 + 대기 + 실패 시 재시도 (대기 시간을 늘려가며)."""
    for i in range(RETRIES):
        try:
            df = fn(*args, **kwargs)
            time.sleep(REQUEST_INTERVAL)
            return df
        except Exception as e:  # 네트워크 오류, 일시 차단 등
            wait = 5 * (i + 1)
            print(f"  요청 실패 ({e.__class__.__name__}: {e}) → {wait}초 후 재시도", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{fn.__name__}{args} 재시도 {RETRIES}회 실패")


def fetch_day(day: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """하루치 순매수/시세. 데이터가 비어 있으면(휴장, 미집계) None."""
    nb_frames, px_frames = [], []
    for market in MARKETS:
        px = call(stock.get_market_ohlcv, day, market=market)
        if px.empty:
            return None
        px = px.reset_index().rename(columns={"티커": "종목코드"})
        px.insert(0, "시장", market)
        px_frames.append(px)

        for label, code in INVESTORS.items():
            nb = call(stock.get_market_net_purchases_of_equities, day, day, market, code)
            if nb.empty:
                return None
            nb = nb.reset_index().rename(columns={"티커": "종목코드"})
            nb.insert(0, "시장", market)
            nb.insert(1, "투자자", label)
            nb_frames.append(nb[["시장", "투자자", "종목코드", "종목명", "매수거래대금", "매도거래대금", "순매수거래대금"]])
    return pd.concat(nb_frames, ignore_index=True), pd.concat(px_frames, ignore_index=True)


def main():
    yesterday = date.today() - timedelta(days=1)
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=(yesterday - timedelta(days=365 * 2)).strftime("%Y%m%d"))
    p.add_argument("--end", default=yesterday.strftime("%Y%m%d"))
    args = p.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    days = [d.strftime("%Y%m%d") for d in stock.get_previous_business_days(fromdate=args.start, todate=args.end)]
    todo = [d for d in days if not (OUTDIR / f"netbuy_{d}.csv.gz").exists()]
    print(f"기간 {days[0]}~{days[-1]} {len(days)}영업일, 이미 받음 {len(days) - len(todo)}, 남음 {len(todo)}", flush=True)

    sector_path = OUTDIR / f"sectors_{days[-1]}.csv"
    if not sector_path.exists():
        sec = []
        for market in MARKETS:
            s = call(stock.get_market_sector_classifications, days[-1], market)
            s = s.reset_index().rename(columns={"티커": "종목코드"})
            s.insert(0, "시장", market)
            sec.append(s[["시장", "종목코드", "종목명", "업종명", "시가총액"]])
        pd.concat(sec).to_csv(sector_path, index=False, encoding="utf-8-sig")

    t0, skipped = time.time(), []
    for i, day in enumerate(todo, 1):
        res = fetch_day(day)
        if res is None:
            skipped.append(day)
        else:
            nb, px = res
            # ohlcv 먼저, netbuy 를 마지막에 저장 → netbuy 파일이 있으면 그날은 완료
            px.to_csv(OUTDIR / f"ohlcv_{day}.csv.gz", index=False, encoding="utf-8-sig")
            nb.to_csv(OUTDIR / f"netbuy_{day}.csv.gz", index=False, encoding="utf-8-sig")
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"{i}/{len(todo)} 완료 ({day}), 경과 {el / 60:.0f}분, 남은 예상 {el / i * (len(todo) - i) / 60:.0f}분", flush=True)

    if skipped:
        print(f"데이터 없음으로 건너뛴 날: {skipped}")
    print(f"저장 위치: {OUTDIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
