"""기간 누적 순매수/순매도 상위 10 종목과 그 종목의 기간 누적 수익률.

investor_netbuy_returns.py 가 만든 investor_netbuy_returns_detail.csv 를 읽어서
투자주체(개인/기관/외국인) × 시장(KOSPI/KOSDAQ)마다
  - 기간 누적 순매수거래대금 상위 10 (순매수) / 하위 10 (순매도) 종목을 뽑고
  - 각 종목의 기간 누적 수익률(일별 수익률 복리)과 시장 대비 초과수익률을 계산한다.

주의:
  - 누적 순매수거래대금은 detail 에 있는 날(그날 상위 50위에 든 날)의 값만 합산한 것이다.
  - 일별 수익률은 detail 의 당일/익일 수익률을 모아서 쓰고, 빠진 날은 pykrx(KRX 공식 종가 기준)로 채운다.
  - 시장평균은 detail 의 당일시장평균(같은 날 같은 시장 전 종목 단순평균)을 복리로 누적한 값이다.

사용 예:
    python investor_netbuy_top10_returns.py
    python investor_netbuy_top10_returns.py --top 20 --out data/my_result.csv
"""
import argparse
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

INVESTORS = ["개인", "기관", "외국인"]
MARKETS = ["KOSPI", "KOSDAQ"]
REQUEST_INTERVAL = 1.0  # KRX 요청 간 대기(초)


def find_detail() -> Path:
    for p in [ROOT / "investor_netbuy_returns_detail.csv", ROOT / "data" / "investor_netbuy_returns_detail.csv"]:
        if p.exists():
            return p
    raise SystemExit("investor_netbuy_returns_detail.csv 가 없습니다. investor_netbuy_returns.py 를 먼저 실행하세요.")


def load_detail(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"종목코드": str, "일자": str, "익일": str})


def return_matrix(detail: pd.DataFrame, days: list[str]) -> pd.DataFrame:
    """detail 의 당일/익일 수익률을 모아 종목 × 일자 수익률 행렬을 만든다."""
    same = detail[["일자", "종목코드", "당일수익률"]].rename(columns={"당일수익률": "수익률"})
    nxt = detail[["익일", "종목코드", "익일수익률"]].rename(columns={"익일": "일자", "익일수익률": "수익률"})
    r = pd.concat([same, nxt]).dropna().drop_duplicates(["일자", "종목코드"])
    r = r[r["일자"].isin(days)]
    return r.pivot(index="종목코드", columns="일자", values="수익률").reindex(columns=days)


def fill_missing(mat: pd.DataFrame, tickers: list[str]) -> tuple[pd.DataFrame, int]:
    """선택된 종목의 빈 날짜를 pykrx 일자별 전 종목 시세(KRX 공식 종가 기준 등락률)로 채운다.

    그날 시세에도 없으면(거래정지 등) 0% 로 둔다.
    """
    mat = mat.reindex(index=sorted(set(mat.index) | set(tickers)))
    sub = mat.loc[tickers]
    missing_days = [d for d in mat.columns if sub[d].isna().any()]
    if not missing_days:
        return mat, 0

    from pykrx import stock  # 채울 게 있을 때만 로그인

    filled = 0
    for day in missing_days:
        df = pd.concat([stock.get_market_ohlcv(day, market=m) for m in MARKETS])
        time.sleep(REQUEST_INTERVAL)
        for t in sub.index[sub[day].isna()]:
            if t in df.index and df.loc[t, "거래량"] > 0:
                mat.loc[t, day] = df.loc[t, "등락률"] / 100
            else:
                mat.loc[t, day] = 0.0  # 거래정지 등
            filled += 1
    return mat, filled


def market_cum(detail: pd.DataFrame, days: list[str]) -> pd.Series:
    m = detail.drop_duplicates(["일자", "시장"]).pivot(index="시장", columns="일자", values="당일시장평균")
    return (1 + m.reindex(columns=days)).prod(axis=1) - 1


def rank_top(detail: pd.DataFrame, top: int) -> pd.DataFrame:
    net = (detail.groupby(["투자자", "시장", "종목코드", "종목명"])
           .agg(누적순매수거래대금=("순매수거래대금", "sum"), 상위50포함일수=("일자", "nunique"))
           .reset_index())
    frames = []
    for (inv, mkt), g in net.groupby(["투자자", "시장"]):
        buy = g[g["누적순매수거래대금"] > 0].nlargest(top, "누적순매수거래대금").assign(구분="순매수")
        sell = g[g["누적순매수거래대금"] < 0].nsmallest(top, "누적순매수거래대금").assign(구분="순매도")
        for part in (buy, sell):
            part = part.copy()
            part["순위"] = range(1, len(part) + 1)
            frames.append(part)
    return pd.concat(frames, ignore_index=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=None, help="입력 detail CSV (기본: 루트 또는 data/ 의 investor_netbuy_returns_detail.csv)")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--out", default=None, help="저장 경로 (기본: data/investor_netbuy_top{N}_period_returns.csv)")
    args = p.parse_args()

    path = Path(args.csv) if args.csv else find_detail()
    detail = load_detail(path)
    days = sorted(detail["일자"].unique())
    print(f"입력: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} ({len(detail)}행, 기간 {days[0]}~{days[-1]}, {len(days)}영업일)")

    ranked = rank_top(detail, args.top)
    mat = return_matrix(detail, days)
    mat, filled = fill_missing(mat, ranked["종목코드"].unique().tolist())
    if filled:
        print(f"detail 에 없던 일별 수익률 {filled}칸을 pykrx 로 채움")

    cum = (1 + mat).prod(axis=1) - 1
    mkt = market_cum(detail, days)

    ranked["누적순매수거래대금(억)"] = (ranked["누적순매수거래대금"] / 1e8).round(1)
    ranked["기간누적수익률"] = ranked["종목코드"].map(cum)
    ranked["시장평균누적수익률"] = ranked["시장"].map(mkt)
    ranked["초과수익률"] = ranked["기간누적수익률"] - ranked["시장평균누적수익률"]
    ranked["시작일"], ranked["종료일"] = days[0], days[-1]

    ranked["투자자"] = pd.Categorical(ranked["투자자"], INVESTORS, ordered=True)
    ranked["시장"] = pd.Categorical(ranked["시장"], MARKETS, ordered=True)
    ranked["구분"] = pd.Categorical(ranked["구분"], ["순매수", "순매도"], ordered=True)
    ranked = ranked.sort_values(["투자자", "시장", "구분", "순위"])
    cols = ["시작일", "종료일", "투자자", "시장", "구분", "순위", "종목코드", "종목명", "누적순매수거래대금(억)",
            "상위50포함일수", "기간누적수익률", "시장평균누적수익률", "초과수익률"]
    ranked = ranked[cols]

    out = Path(args.out) if args.out else ROOT / "data" / f"investor_netbuy_top{args.top}_period_returns.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(out, index=False, encoding="utf-8-sig")

    # 콘솔 출력
    pct = lambda v: f"{v * 100:+.2f}%"  # noqa: E731
    print("\n시장 동일가중 기간 누적 수익률: " + ", ".join(f"{k} {pct(v)}" for k, v in mkt.items()))
    for (inv, mkt_name), g in ranked.groupby(["투자자", "시장"], observed=True):
        print(f"\n=== {inv} · {mkt_name}")
        for side, gg in g.groupby("구분", observed=True):
            show = gg[["순위", "종목명", "누적순매수거래대금(억)", "상위50포함일수", "기간누적수익률", "초과수익률"]].copy()
            show["기간누적수익률"] = show["기간누적수익률"].map(pct)
            show["초과수익률"] = show["초과수익률"].map(pct)
            print(f"[{side} TOP{args.top}]  평균 수익률 {pct(gg['기간누적수익률'].mean())}, "
                  f"평균 초과 {pct(gg['초과수익률'].mean())}, 상승 {int((gg['기간누적수익률'] > 0).sum())}/{len(gg)}")
            print(show.to_string(index=False))
    print(f"\n저장: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} ({len(ranked)}행)")


if __name__ == "__main__":
    main()
