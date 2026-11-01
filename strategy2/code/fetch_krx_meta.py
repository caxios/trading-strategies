"""strategy2 연구계획서 3.1절: KRX 보조 데이터 수집 (지수, 시점별 업종, 종목 마스터).

  data/index/index_daily.csv                 : KOSPI(1001), KOSDAQ(2001) 지수 일별 시세 (2014-01-01~)
  data/sectors/sectors_YYYYMMDD.csv.gz       : 매월 마지막 영업일 기준 업종 분류 (KOSPI, KOSDAQ)
                                               신호일에는 그 날짜 이전의 가장 최근 스냅샷을 붙인다
  data/master/listed_basic_YYYYMMDD.csv      : 수집일 기준 상장 종목 기본정보 (증권구분, 주식종류, 상장일 등)
  data/master/delisted_list.csv              : 상장폐지 종목 목록 (코드, 이름, 시장. 폐지일은 없음 → 시세 마지막 거래일로 판정)

이미 받은 파일은 건너뛴다. KRX 로그인이 필요하므로 .env 에 KRX_ID, KRX_PW 가 있어야 한다.

사용 예:
    python strategy2/code/fetch_krx_meta.py
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pykrx import stock  # noqa: E402  (.env 로드 후 import 해야 자동 로그인됨)
from pykrx.website.krx.market.core import 상폐종목검색, 전종목기본정보  # noqa: E402

from fetch_investor_history import MARKETS, call  # noqa: E402

# KRX 는 계정당 세션 하나만 유지되므로 fetch_flow_history 와 동시에 돌리지 않는다 (먼저 로그인한 쪽이 끊김)

DATA = ROOT / "data"
INDICES = {"KOSPI": "1001", "KOSDAQ": "2001"}


def fetch_index(start: str, end: str) -> None:
    path = DATA / "index" / "index_daily.csv"
    if path.exists():
        return
    frames = []
    for market, code in INDICES.items():
        df = call(stock.get_index_ohlcv_by_date, start, end, code, name_display=False)
        df = df.reset_index().rename(columns={"날짜": "일자"})
        df.insert(0, "지수", market)
        frames.append(df)
    pd.concat(frames, ignore_index=True).to_csv(path, index=False, encoding="utf-8-sig")
    print(f"지수 저장: {path.relative_to(ROOT)}", flush=True)


def fetch_sector_day(day: str) -> pd.DataFrame:
    frames = []
    for market in MARKETS:
        s = call(stock.get_market_sector_classifications, day, market)
        s = s.reset_index().rename(columns={"티커": "종목코드"})
        s.insert(0, "시장", market)
        frames.append(s[["시장", "종목코드", "종목명", "업종명", "시가총액"]])
    return pd.concat(frames, ignore_index=True)


def fetch_sectors(start: str, end: str) -> None:
    outdir = DATA / "sectors"
    days = pd.Series(pd.to_datetime([d for d in stock.get_previous_business_days(fromdate=start, todate=end)]))
    month_ends = days.groupby(days.dt.to_period("M")).max().dt.strftime("%Y%m%d").tolist()
    todo = [d for d in month_ends if not (outdir / f"sectors_{d}.csv.gz").exists()]
    print(f"업종 분류: 월말 {len(month_ends)}개, 남음 {len(todo)}", flush=True)
    for i, day in enumerate(todo, 1):
        fetch_sector_day(day).to_csv(outdir / f"sectors_{day}.csv.gz", index=False, encoding="utf-8-sig")
        if i % 20 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} 완료 ({day})", flush=True)


def fetch_master() -> None:
    outdir = DATA / "master"
    today = date.today().strftime("%Y%m%d")
    basic = outdir / f"listed_basic_{today}.csv"
    if not basic.exists():
        call(전종목기본정보().fetch, "ALL").to_csv(basic, index=False, encoding="utf-8-sig")
    delisted = outdir / "delisted_list.csv"
    if not delisted.exists():
        call(상폐종목검색().fetch, "ALL").to_csv(delisted, index=False, encoding="utf-8-sig")
    print(f"종목 마스터 저장: {outdir.relative_to(ROOT)}", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="20140101")
    p.add_argument("--end", default="20261022")
    args = p.parse_args()

    for d in ("index", "sectors", "master"):
        (DATA / d).mkdir(parents=True, exist_ok=True)
    fetch_index(args.start, args.end)
    fetch_master()
    fetch_sectors(args.start, args.end)


if __name__ == "__main__":
    main()
