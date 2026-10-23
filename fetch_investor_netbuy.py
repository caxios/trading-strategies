"""주체별(외국인/개인/기관) 코스피·코스닥 순매수/순매도 상위 종목 조회 (거래대금 기준).

저번주 + 이번주의 영업일마다 하루 단위로 순위를 매긴다.
KRX 정보데이터시스템 로그인이 필요하므로 .env 에 KRX_ID, KRX_PW 가 있어야 한다.

사용 예:
    python fetch_investor_netbuy.py                      # 저번주 + 이번주, 일별 상위 50
    python fetch_investor_netbuy.py --top 30 --date 20261016
"""
import argparse
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from pykrx import stock  # noqa: E402  (.env 로드 후 import 해야 자동 로그인됨)

MARKETS = ["KOSPI", "KOSDAQ"]
INVESTORS = {"외국인": "외국인", "개인": "개인", "기관": "기관합계"}
REQUEST_INTERVAL = 1.0  # KRX 요청 간 대기(초)


def week_days(d: date) -> list[str]:
    """d 가 속한 주의 월~금 중 오늘 이전 날짜 (YYYYMMDD)."""
    monday = d - timedelta(days=d.weekday())
    days = [monday + timedelta(days=i) for i in range(5)]
    return [x.strftime("%Y%m%d") for x in days if x <= date.today()]


def fetch_rank(day: str, market: str, investor: str, top: int) -> Optional[pd.DataFrame]:
    """하루치 순매수/순매도 상위. 휴장일이거나 아직 데이터가 없으면 None."""
    df = stock.get_market_net_purchases_of_equities(day, day, market, investor)
    if df.empty:
        return None
    df = df.reset_index().rename(columns={"티커": "종목코드"})

    buy = df.sort_values("순매수거래대금", ascending=False).head(top).copy()
    buy.insert(0, "구분", "순매수")
    sell = df.sort_values("순매수거래대금", ascending=True).head(top).copy()
    sell.insert(0, "구분", "순매도")

    out = pd.concat([buy, sell], ignore_index=True)
    out.insert(1, "순위", out.groupby("구분").cumcount() + 1)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=date.today().strftime("%Y%m%d"), help="이번주 기준일 (YYYYMMDD)")
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--out", default=None, help="저장 경로 (기본: 루트에 자동 이름)")
    args = p.parse_args()

    base = datetime.strptime(args.date, "%Y%m%d").date()
    weeks = {
        "저번주": week_days(base - timedelta(days=7)),
        "이번주": week_days(base),
    }

    frames = []
    for label, days in weeks.items():
        for day in days:
            for market in MARKETS:
                for inv_label, inv_code in INVESTORS.items():
                    df = fetch_rank(day, market, inv_code, args.top)
                    time.sleep(REQUEST_INTERVAL)
                    if df is None:
                        print(f"[{label} {day}] {market} {inv_label}: 데이터 없음 (휴장 또는 미집계) → 건너뜀")
                        continue
                    print(f"[{label} {day}] {market} {inv_label}: {len(df)}행")
                    df.insert(0, "주차", label)
                    df.insert(1, "일자", day)
                    df.insert(2, "시장", market)
                    df.insert(3, "투자자", inv_label)
                    frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    first, last = result["일자"].min(), result["일자"].max()
    out = Path(args.out) if args.out else ROOT / f"investor_netbuy_daily_top{args.top}_{first}_{last}.csv"
    result.to_csv(out, index=False, encoding="utf-8-sig")  # 엑셀 한글 깨짐 방지
    print(f"저장: {out} ({len(result)}행, 일자 {sorted(result['일자'].unique())})")


if __name__ == "__main__":
    main()
