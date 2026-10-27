"""투자주체별 순매수/순매도 상위 종목의 주가수익률 검증.

investor_netbuy_daily_*.csv (fetch_investor_netbuy.py 결과)에 나온 종목들에 대해
pykrx 로 일별 수익률을 가져와서 다음을 확인한다.

  - 당일 수익률 : 순매수/순매도한 그날 주가가 올랐나/내렸나
  - 익일 수익률 : 다음 영업일에도 이어졌나 (매매 신호로 쓸 수 있는지)
  - 기간 누적 수익률 : 기간 동안 순매수(합계>0)/순매도(합계<0)한 종목이 기간 전체로 올랐나/내렸나
  - 시장 대비 초과수익률 : 같은 날 같은 시장 전 종목 단순평균 수익률을 뺀 값

수익률은 KRX 등락률(전일 종가 대비, 권리락 등 기준가 조정 반영)을 그대로 쓰고, 누적은 복리로 계산한다.

출력 (루트):
  investor_netbuy_returns_detail.csv   : 원본 순위 데이터 + 당일/익일/초과 수익률 (행 단위)
  investor_netbuy_returns_daily.csv    : 종목별 일별 수익률 + 기간 누적 수익률 (종목 × 일자)
  investor_netbuy_returns_summary.csv  : 주체 × 시장 × 구분별 요약 (일별 신호 기준 + 기간 누적 기준)

사용 예:
    python investor_netbuy_returns.py
    python investor_netbuy_returns.py --csv data/investor_netbuy_daily_top50_20261012_20261022.csv
"""
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from pykrx import stock  # noqa: E402  (.env 로드 후 import 해야 자동 로그인됨)

MARKETS = ["KOSPI", "KOSDAQ"]
REQUEST_INTERVAL = 1.0  # KRX 요청 간 대기(초)


def latest_csv() -> Path:
    files = [*ROOT.glob("investor_netbuy_daily_*.csv"), *(ROOT / "data").glob("investor_netbuy_daily_*.csv")]
    if not files:
        raise SystemExit("investor_netbuy_daily_*.csv 가 없습니다. fetch_investor_netbuy.py 를 먼저 실행하세요.")
    return max(files, key=lambda p: p.stat().st_mtime)


def next_business_day(day: str) -> str | None:
    """day 다음 영업일. 아직 데이터가 없으면 None."""
    d = datetime.strptime(day, "%Y%m%d")
    for i in range(1, 8):
        cand = (d + timedelta(days=i)).strftime("%Y%m%d")
        if cand > datetime.today().strftime("%Y%m%d"):
            return None
        if not stock.get_market_ohlcv(cand, market="KOSPI").empty:
            return cand
        time.sleep(REQUEST_INTERVAL)
    return None


def fetch_returns(days: list[str]) -> pd.DataFrame:
    """일자 × 시장 전 종목 등락률(%) → long format (일자, 시장, 종목코드, 종가, 수익률)."""
    frames = []
    for day in days:
        for market in MARKETS:
            df = stock.get_market_ohlcv(day, market=market)
            time.sleep(REQUEST_INTERVAL)
            if df.empty:
                print(f"  {day} {market}: 데이터 없음")
                continue
            df = df.reset_index().rename(columns={"티커": "종목코드"})
            df = df[df["거래량"] > 0]  # 거래정지 종목 제외 (등락률 0 으로 평균을 왜곡)
            frames.append(pd.DataFrame({
                "일자": day, "시장": market, "종목코드": df["종목코드"],
                "종가": df["종가"], "수익률": df["등락률"] / 100,
            }))
            print(f"  {day} {market}: {len(df)}종목")
    return pd.concat(frames, ignore_index=True)


def add_daily_returns(nb: pd.DataFrame, ret: pd.DataFrame, days: list[str], next_day: str | None) -> pd.DataFrame:
    mkt = ret.groupby(["일자", "시장"])["수익률"].mean().rename("시장평균")
    r = ret.set_index(["일자", "종목코드"])["수익률"]

    out = nb.copy()
    out["당일수익률"] = r.reindex(list(zip(out["일자"], out["종목코드"]))).to_numpy()
    out["당일시장평균"] = mkt.reindex(list(zip(out["일자"], out["시장"]))).to_numpy()

    nxt = {d: n for d, n in zip(days, days[1:] + [next_day])}
    out["익일"] = out["일자"].map(nxt)
    out["익일수익률"] = r.reindex(list(zip(out["익일"], out["종목코드"]))).to_numpy()
    out["익일시장평균"] = mkt.reindex(list(zip(out["익일"], out["시장"]))).to_numpy()

    out["당일초과수익률"] = out["당일수익률"] - out["당일시장평균"]
    out["익일초과수익률"] = out["익일수익률"] - out["익일시장평균"]
    return out


def stock_period_table(ret: pd.DataFrame, tickers: pd.DataFrame, days: list[str]) -> pd.DataFrame:
    """종목 × 일자 수익률 + 기간 누적 수익률 (첫 신호일 전일 종가 → 마지막 신호일 종가)."""
    sub = ret[ret["일자"].isin(days) & ret["종목코드"].isin(tickers["종목코드"])]
    piv = sub.pivot_table(index="종목코드", columns="일자", values="수익률")
    piv = piv.reindex(columns=days)
    cum = (1 + piv.fillna(0)).prod(axis=1) - 1
    piv.columns = [f"수익률_{d}" for d in days]
    table = tickers.set_index("종목코드").join(piv)
    table["기간누적수익률"] = cum
    return table.reset_index()


def market_period_return(ret: pd.DataFrame, days: list[str]) -> pd.Series:
    """시장별 동일가중 일평균 수익률을 복리로 누적."""
    m = ret[ret["일자"].isin(days)].groupby(["시장", "일자"])["수익률"].mean().unstack()
    return (1 + m).prod(axis=1) - 1


def summarize(detail: pd.DataFrame, period: pd.DataFrame, nb: pd.DataFrame, mkt_cum: pd.Series) -> pd.DataFrame:
    rows = []

    # 1) 일별 신호 기준: 그날 상위 N에 든 종목의 당일/익일 수익률
    for (inv, mkt, side), g in detail.groupby(["투자자", "시장", "구분"]):
        nx = g.dropna(subset=["익일수익률"])
        rows.append({
            "기준": "일별신호", "투자자": inv, "시장": mkt, "구분": side, "표본수": len(g),
            "평균수익률": g["당일수익률"].mean(),
            "상승비율": (g["당일수익률"] > 0).mean(),
            "시장평균": g["당일시장평균"].mean(),
            "평균초과수익률": g["당일초과수익률"].mean(),
            "익일_평균수익률": nx["익일수익률"].mean(),
            "익일_상승비율": (nx["익일수익률"] > 0).mean(),
            "익일_평균초과수익률": nx["익일초과수익률"].mean(),
        })

    # 2) 기간 누적 기준: 기간 순매수 합계 부호로 순매수/순매도 그룹을 나눔
    #    (상위 N위에 든 날의 순매수거래대금만 합산한 값)
    net = nb.groupby(["투자자", "시장", "종목코드"])["순매수거래대금"].sum().rename("기간순매수합").reset_index()
    net = net.merge(period[["종목코드", "기간누적수익률"]], on="종목코드", how="left")
    for (inv, mkt), g in net.groupby(["투자자", "시장"]):
        corr = g["기간순매수합"].rank().corr(g["기간누적수익률"].rank())  # 스피어만 순위상관
        for side, gg in [("순매수", g[g["기간순매수합"] > 0]), ("순매도", g[g["기간순매수합"] < 0])]:
            rows.append({
                "기준": "기간누적", "투자자": inv, "시장": mkt, "구분": side, "표본수": len(gg),
                "평균수익률": gg["기간누적수익률"].mean(),
                "상승비율": (gg["기간누적수익률"] > 0).mean(),
                "시장평균": mkt_cum.get(mkt, np.nan),
                "평균초과수익률": gg["기간누적수익률"].mean() - mkt_cum.get(mkt, np.nan),
                "순매수금액_수익률_순위상관": corr,
            })
    return pd.DataFrame(rows)


def print_summary(s: pd.DataFrame):
    pct = lambda v: "" if pd.isna(v) else f"{v * 100:+.2f}%"  # noqa: E731
    rate = lambda v: "" if pd.isna(v) else f"{v * 100:.0f}%"  # noqa: E731
    for basis, title in [("일별신호", "일별 신호 (그날 상위 종목의 당일 / 익일 수익률)"),
                         ("기간누적", "기간 누적 (기간 순매수 합계 부호별 누적 수익률)")]:
        print(f"\n=== {title}")
        g = s[s["기준"] == basis].copy()
        cols = {"평균수익률": pct, "상승비율": rate, "평균초과수익률": pct}
        if basis == "일별신호":
            cols.update({"익일_평균수익률": pct, "익일_상승비율": rate, "익일_평균초과수익률": pct})
        else:
            cols.update({"순매수금액_수익률_순위상관": lambda v: f"{v:+.2f}"})
        for c, f in cols.items():
            g[c] = g[c].map(f)
        print(g[["투자자", "시장", "구분", "표본수", *cols]].to_string(index=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=None, help="입력 CSV (기본: 루트 또는 data/ 의 최신 investor_netbuy_daily_*.csv)")
    p.add_argument("--outdir", default=str(ROOT))
    args = p.parse_args()

    csv_path = Path(args.csv) if args.csv else latest_csv()
    nb = pd.read_csv(csv_path, encoding="utf-8-sig", dtype={"종목코드": str, "일자": str})
    days = sorted(nb["일자"].unique())
    print(f"입력: {csv_path.name} ({len(nb)}행, {nb['종목코드'].nunique()}종목, 일자 {days[0]}~{days[-1]})")

    next_day = next_business_day(days[-1])
    print(f"익일 수익률용 다음 영업일: {next_day or '아직 없음 (마지막 날 익일 수익률은 비움)'}")
    ret = fetch_returns(days + ([next_day] if next_day else []))

    detail = add_daily_returns(nb, ret, days, next_day)
    tickers = nb.drop_duplicates("종목코드")[["종목코드", "종목명", "시장"]]
    period = stock_period_table(ret, tickers, days)
    mkt_cum = market_period_return(ret, days)
    summary = summarize(detail, period, nb, mkt_cum)

    outdir = Path(args.outdir)
    detail.to_csv(outdir / "investor_netbuy_returns_detail.csv", index=False, encoding="utf-8-sig")
    period.to_csv(outdir / "investor_netbuy_returns_daily.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(outdir / "investor_netbuy_returns_summary.csv", index=False, encoding="utf-8-sig")

    print(f"\n시장 동일가중 기간 누적 수익률: " + ", ".join(f"{k} {v * 100:+.2f}%" for k, v in mkt_cum.items()))
    print_summary(summary)
    missing = detail["당일수익률"].isna().sum()
    if missing:
        print(f"\n※ 수익률을 못 찾은 행 {missing}개 (거래정지 등)")
    print("\n저장: investor_netbuy_returns_detail.csv, investor_netbuy_returns_daily.csv, investor_netbuy_returns_summary.csv")


if __name__ == "__main__":
    main()
