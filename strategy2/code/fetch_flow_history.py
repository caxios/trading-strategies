"""strategy2 연구계획서 3.1절: 투자주체별 거래 + 전 종목 시세 일별 수집 (2014-01-01~).

기존 data/ 에 이미 있는 것은 다시 받지 않는다.
  - 시세: data/lookback/ (2023-09-01~2024-10-21), data/history/ (2024-10-22~) 에 있는 날은 건너뜀
  - 외국인: data/history/netbuy_*.csv.gz 에 있는 날은 건너뜀 (같은 pykrx 호출로 받은 값)

  data/flow/flow_YYYYMMDD.csv.gz   : 시장 × 투자자 × 종목 매수·매도·순매수 거래대금
                                     투자자 = 외국인, 기타외국인, 연기금, 투신 중 그날 기존 파일에 없는 것
  data/ohlcv/ohlcv_YYYYMMDD.csv.gz : 시장 × 전 종목 시세 (data/history/ohlcv 와 같은 형식)

투자자별 파일에는 그 주체가 그날 거래한 종목만 나온다(거래가 없으면 행 자체가 없음 = 0).
이미 받은 날짜는 건너뛰므로 끊겨도 다시 실행하면 이어서 받는다.
KRX 로그인이 필요하므로 .env 에 KRX_ID, KRX_PW 가 있어야 한다.

사용 예:
    python strategy2/code/fetch_flow_history.py
    python strategy2/code/fetch_flow_history.py --start 20140101 --end 20261022
"""
import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from pykrx import stock  # noqa: E402  (.env 로드 후 import 해야 자동 로그인됨)

import fetch_investor_history as fih  # noqa: E402
from fetch_investor_history import MARKETS, call  # noqa: E402


INVESTORS = ["외국인", "기타외국인", "연기금", "투신"]
DATA = ROOT / "data"
FLOWDIR = DATA / "flow"
PXDIR = DATA / "ohlcv"
MAX_BAD_DAYS = 3  # 일부 주체가 빈 날이 연달아 이만큼 나오면 세션 끊김·차단으로 보고 중단
NB_COLS = ["시장", "투자자", "종목코드", "종목명", "매수거래대금", "매도거래대금", "순매수거래대금"]


def has_ohlcv(day: str) -> bool:
    return any((DATA / d / f"ohlcv_{day}.csv.gz").exists() for d in ("ohlcv", "lookback", "history"))


def fetch_day(day: str, need_px: bool, investors: list[str]) -> tuple[pd.DataFrame, pd.DataFrame | None, list] | None:
    """하루치 투자주체별 거래/시세. 시세가 비어 있으면(휴장, 미집계) None."""
    nb_frames, px_frames, empty = [], [], []
    for market in MARKETS:
        if need_px:
            px = call(stock.get_market_ohlcv, day, market=market)
            if px.empty:
                return None
            px = px.reset_index().rename(columns={"티커": "종목코드"})
            px.insert(0, "시장", market)
            px_frames.append(px)

        for inv in investors:
            nb = call(stock.get_market_net_purchases_of_equities, day, day, market, inv)
            if nb.empty:  # 그 주체가 그 시장에서 하루 종일 거래가 없었거나 미집계 → 기록해 두고 진행
                empty.append(f"{market}/{inv}")
                continue
            nb = nb.reset_index().rename(columns={"티커": "종목코드"})
            nb.insert(0, "시장", market)
            nb.insert(1, "투자자", inv)
            nb_frames.append(nb[NB_COLS])
    if len(empty) == len(MARKETS) * len(investors):
        return None
    nb = pd.concat(nb_frames, ignore_index=True)
    return nb, (pd.concat(px_frames, ignore_index=True) if need_px else None), empty


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="20140101")
    p.add_argument("--end", default="20261022")
    args = p.parse_args()

    FLOWDIR.mkdir(parents=True, exist_ok=True)
    PXDIR.mkdir(parents=True, exist_ok=True)
    days = [d.strftime("%Y%m%d") for d in stock.get_previous_business_days(fromdate=args.start, todate=args.end)]
    todo = [d for d in days if not (FLOWDIR / f"flow_{d}.csv.gz").exists()]
    print(f"기간 {days[0]}~{days[-1]} {len(days)}영업일, 이미 받음 {len(days) - len(todo)}, 남음 {len(todo)}", flush=True)

    t0, skipped, partial, bad = time.time(), [], {}, 0
    for i, day in enumerate(todo, 1):
        has_foreign = (DATA / "history" / f"netbuy_{day}.csv.gz").exists()
        investors = [v for v in INVESTORS if not (has_foreign and v == "외국인")]
        # 재시도(call)까지 실패하면 예외로 그대로 종료한다. 재로그인·자동 재개는 하지 않는다.
        res = fetch_day(day, not has_ohlcv(day), investors)
        if res is None or res[2]:
            # 전부 비었거나 일부 주체가 비었으면 저장하지 않는다 → 다음 실행 때 다시 받는다
            if res is None:
                skipped.append(day)
            else:
                partial[day] = res[2]
            bad += 1
            print(f"  {day} {'전부' if res is None else res[2]} 비어 있음 → 저장 안 함 ({bad}/{MAX_BAD_DAYS})", flush=True)
            if bad >= MAX_BAD_DAYS:
                print("빈 응답이 연달아 나와 중단합니다 (세션 끊김 또는 차단 의심). 원인 확인 후 다시 실행하세요.", flush=True)
                break
        else:
            bad = 0
            nb, px, _ = res
            # 시세 먼저, flow 를 마지막에 저장 → flow 파일이 있으면 그날은 완료
            if px is not None:
                px.to_csv(PXDIR / f"ohlcv_{day}.csv.gz", index=False, encoding="utf-8-sig")
            nb.to_csv(FLOWDIR / f"flow_{day}.csv.gz", index=False, encoding="utf-8-sig")
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"{i}/{len(todo)} 완료 ({day}), 경과 {el / 60:.0f}분, 남은 예상 {el / i * (len(todo) - i) / 60:.0f}분", flush=True)

    if skipped:
        print(f"전부 비어 저장하지 않은 날: {skipped}")
    if partial:
        print(f"일부 주체가 비어 저장하지 않은 날 (다시 실행하면 재시도): {partial}")
    print(f"저장 위치: {FLOWDIR.relative_to(ROOT)}, {PXDIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
