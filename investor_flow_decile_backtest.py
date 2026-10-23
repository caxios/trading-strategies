"""투자주체별 순매수 강도 10분위 백테스트 — 순매수를 따라 사면/순매도를 사면 시장보다 나은가.

fetch_investor_history.py 가 받은 data/history/ 를 읽어서 투자주체(외국인/기관/개인)마다

  1) 매일 시장(KOSPI/KOSDAQ)별로 전 종목을 순매수 강도 x = 순매수거래대금 / 그날 시가총액 으로 줄 세워
     10개 그룹으로 나눈다 (1그룹 = 가장 많이 순매도, 10그룹 = 가장 많이 순매수).
  2) 날짜 d 의 각 그룹을 하나의 포트폴리오로 보고, d일 종가에 동일가중으로 사서 h일 뒤 종가에 판다고 할 때
     시장 대비 초과수익률 R_{g,d}^h 를 계산한다.
       종목 초과수익률 = 종목 h일 수익률 − 같은 날 같은 시장 유니버스 전 종목의 h일 수익률 단순평균
  3) 검정 (투자자 × 보유기간마다, 표본 = 날짜):
       ① 순매수 따라 사기 : y_d = R_{10,d}^h − 비용,  H0: E[y] ≤ 0  vs  H1: E[y] > 0 (단측)
       ② 순매도 종목 사기 : y_d = R_{1,d}^h  − 비용,  H0: E[y] ≤ 0  vs  H1: E[y] > 0 (단측)
     t = mean(y) / sqrt(Ω_NW / T),  Ω_NW = Newey-West 분산 (시차 h−1, 보유기간 겹침 보정)
     교차 검증: h 일 간격으로만 뽑은 안 겹치는 표본의 일반 t (시작일 0..h−1 별 중앙값/최소/최대)
     보유기간 120일 이상은 안 겹치는 표본이 3개 이하라 평균만 보고하고 검정하지 않는다.

유니버스 (날짜마다): 거래량 > 0, 그날 시가총액 >= --min-cap 억, 스팩·우선주·리츠 제외.
상장폐지: 보유 중 상장폐지되면 마지막 거래일 종가까지의 수익률, 그 뒤는 0% (생존편향 제거).
비용: 왕복 --cost (기본 0.25% = 거래세 + 수수료), 보유기간과 무관하게 1회 차감.

출력:
  data/investor_flow_decile_tests.csv  : 검정 결과 (투자자 × 시장 × 그룹 × 보유기간)
  data/investor_flow_decile_groups.csv : 10개 그룹별 평균 초과/절대 수익률 + IC
  data/investor_flow_decile_daily.csv.gz : 날짜별 포트폴리오 수익률 R_{g,d}^h

사용 예:
    python investor_flow_decile_backtest.py
    python investor_flow_decile_backtest.py --min-cap 1000 --cost 0.003
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from netsell_reversal_backtest import load, nw_tstat

ROOT = Path(__file__).resolve().parent
INVESTORS = ["외국인", "기관", "개인"]
MARKETS = ["KOSPI", "KOSDAQ"]
HORIZONS = [1, 5, 10, 20, 60, 120, 240, 480]  # 480 영업일 ≈ 2년
TESTED = [h for h in HORIZONS if h <= 60]      # 검정하는 보유기간
N_GROUPS = 10
ALPHA_Z = 1.645                                 # 단측 5%
BONF_Z = 2.94                                   # 단측 5% / 30회 (본페로니)


# ---------------------------------------------------------------- 유니버스와 수익률
def build_universe(px: pd.DataFrame, names: pd.Series, min_cap: float) -> pd.DataFrame:
    u = px[["일자", "시장", "종목코드", "거래량", "시가총액"]].copy()
    u["종목명"] = u["종목코드"].map(names).fillna("")
    keep = (
        (u["거래량"] > 0)
        & (u["시가총액"] >= min_cap * 1e8)
        & u["종목코드"].str.endswith("0")                       # 우선주 제외 (보통주 코드 끝자리 0)
        & ~u["종목명"].str.contains("스팩")
        & ~(u["종목명"].str.contains("리츠") & ~u["종목명"].str.contains("메리츠"))
    )
    return u[keep].reset_index(drop=True)


def forward_returns(px: pd.DataFrame, days: list[str]) -> tuple[dict[int, np.ndarray], pd.Index]:
    """h 일 보유 수익률 행렬 (일자 × 종목). 거래정지·상장폐지 이후는 0% → 마지막 종가 기준."""
    px = px.assign(수익률=np.where(px["거래량"] > 0, px["등락률"] / 100, np.nan))
    R = px.pivot(index="일자", columns="종목코드", values="수익률").reindex(days)
    LR = np.log1p(R.fillna(0)).cumsum().to_numpy()
    out = {}
    for h in HORIZONS:
        F = np.full_like(LR, np.nan)
        if h < len(days):
            F[:-h] = np.expm1(LR[h:] - LR[:-h])
        out[h] = F
    return out, R.columns


def attach_forward(u: pd.DataFrame, fwd, tickers, days) -> pd.DataFrame:
    di = pd.Index(days).get_indexer(u["일자"])
    ci = pd.Index(tickers).get_indexer(u["종목코드"])
    for h in HORIZONS:
        u[f"수익_{h}"] = fwd[h][di, ci]
        bench = u.groupby(["일자", "시장"])[f"수익_{h}"].transform("mean")
        u[f"초과_{h}"] = u[f"수익_{h}"] - bench
    return u


def assign_groups(u: pd.DataFrame, nb: pd.DataFrame, investor: str) -> pd.DataFrame:
    flow = nb.loc[nb["투자자"] == investor].set_index(["일자", "종목코드"])["순매수거래대금"]
    d = u.copy()
    d["순매수"] = flow.reindex(list(zip(d["일자"], d["종목코드"]))).fillna(0).to_numpy()  # 거래 없음 = 0
    d["x"] = d["순매수"] / d["시가총액"]
    key = d.groupby(["일자", "시장"])["x"]
    r = key.rank(method="first")
    n = key.transform("size")
    d["그룹"] = ((r - 1) * N_GROUPS // n + 1).astype(int)
    d["x순위"] = key.rank(pct=True)
    return d


# ---------------------------------------------------------------- 날짜별 포트폴리오와 검정
def daily_portfolios(d: pd.DataFrame) -> pd.DataFrame:
    """(시장, 그룹, 일자) 별 포트폴리오 수익률. 시장='전체' 는 두 시장 종목을 합친 동일가중."""
    cols = [f"{k}_{h}" for k in ["초과", "수익"] for h in HORIZONS]
    by_mkt = d.groupby(["시장", "그룹", "일자"])[cols].mean()
    pooled = d.groupby(["그룹", "일자"])[cols].mean()
    pooled.index = pd.MultiIndex.from_tuples([("전체", g, day) for g, day in pooled.index], names=by_mkt.index.names)
    return pd.concat([pooled, by_mkt]).sort_index()


def daily_ic(d: pd.DataFrame) -> pd.DataFrame:
    """날짜 × 시장별 스피어만 IC (x 순위 vs h일 수익률 순위). 시장='전체' 는 두 시장 IC 평균."""
    rows = {}
    for h in HORIZONS:
        c = f"수익_{h}"
        sub = d.dropna(subset=[c]).copy()
        sub["y순위"] = sub.groupby(["일자", "시장"])[c].rank(pct=True)
        rows[h] = sub.groupby(["일자", "시장"]).apply(lambda g: g["x순위"].corr(g["y순위"]), include_groups=False)
    ic = pd.DataFrame(rows)
    pooled = ic.groupby("일자").mean()
    pooled["시장"] = "전체"
    return pd.concat([pooled.reset_index().set_index(["시장", "일자"]),
                      ic.reset_index().set_index(["시장", "일자"])])


def nonoverlap_t(y: pd.Series, h: int, days: list[str]):
    """h 일 간격 표본의 일반 t (시작일 0..h−1). (중앙값, 최소, 최대, 표본수)"""
    s = y.reindex(days).to_numpy()
    ts, ns = [], []
    for o in range(h):
        v = s[o::h]
        v = v[~np.isnan(v)]
        if len(v) >= 3 and v.std(ddof=1) > 0:
            ts.append(v.mean() / (v.std(ddof=1) / np.sqrt(len(v))))
            ns.append(len(v))
    if not ts:
        return np.nan, np.nan, np.nan, 0
    return float(np.median(ts)), float(np.min(ts)), float(np.max(ts)), int(np.median(ns))


def run_tests(port: pd.DataFrame, inv: str, days, cost: float) -> list[dict]:
    rows = []
    for mkt in ["전체", *MARKETS]:
        for g, label in [(N_GROUPS, "① 순매수 따라 사기 (10그룹)"), (1, "② 순매도 종목 사기 (1그룹)")]:
            p = port.loc[(mkt, g)]
            for h in HORIZONS:
                y = (p[f"초과_{h}"] - cost).dropna()
                row = {"투자자": inv, "시장": mkt, "검정": label, "그룹": g, "보유기간": h, "T": len(y),
                       "평균초과_비용전": p[f"초과_{h}"].mean(), "평균초과_비용후": y.mean(),
                       "평균절대수익": p[f"수익_{h}"].mean(), "양수비율": (y > 0).mean()}
                if h in TESTED:
                    t = nw_tstat(y.sort_index().to_numpy(), h - 1)
                    med, lo, hi, n = nonoverlap_t(y, h, days)
                    row.update({"t_NW": t, "유의_5%": t > ALPHA_Z, "유의_본페로니": t > BONF_Z,
                                "비중첩_t_중앙값": med, "비중첩_t_최소": lo, "비중첩_t_최대": hi, "비중첩_표본수": n})
                rows.append(row)
    return rows


def group_table(port: pd.DataFrame, ic: pd.DataFrame, inv: str) -> list[dict]:
    rows = []
    for mkt in ["전체", *MARKETS]:
        for h in HORIZONS:
            row = {"투자자": inv, "시장": mkt, "보유기간": h}
            for g in range(1, N_GROUPS + 1):
                row[f"G{g}_초과"] = port.loc[(mkt, g), f"초과_{h}"].mean()
            for g in range(1, N_GROUPS + 1):
                row[f"G{g}_절대"] = port.loc[(mkt, g), f"수익_{h}"].mean()
            v = ic.loc[mkt, h].dropna().sort_index().to_numpy()
            row["IC평균"] = v.mean()
            row["IC_t_NW"] = nw_tstat(v, h - 1) if h in TESTED else np.nan
            rows.append(row)
    return rows


# ---------------------------------------------------------------- 출력
def print_results(tests: pd.DataFrame, groups: pd.DataFrame, cost: float):
    pct = lambda v: "" if pd.isna(v) else f"{v * 100:+.2f}%"  # noqa: E731

    def cell(r):
        s = pct(r["평균초과_비용후"])
        if r.name in TESTED:
            mark = "**" if r["유의_본페로니"] else ("*" if r["유의_5%"] else "")
            s += f"({r['t_NW']:+.1f}){mark}"
        return s

    for mkt in ["전체", *MARKETS]:
        print(f"\n=== [{mkt}] 비용({cost * 100:.2f}%) 차감 후 시장 대비 초과수익률 평균 (NW t값)  * 단측 5%  ** 본페로니")
        lines = []
        for (inv, label), g in tests[tests["시장"] == mkt].groupby(["투자자", "검정"], sort=False):
            g = g.set_index("보유기간")
            lines.append([inv, label[:1], *[cell(g.loc[h]) for h in HORIZONS]])
            if mkt == "전체":
                lines.append(["", "절대", *[pct(g.loc[h, "평균절대수익"]) for h in HORIZONS]])
                lines.append(["", "비중첩t", *[
                    f"{g.loc[h, '비중첩_t_최소']:+.1f}~{g.loc[h, '비중첩_t_최대']:+.1f}" if h in TESTED and h > 1 else ""
                    for h in HORIZONS]])
        print(pd.DataFrame(lines, columns=["투자자", "검정", *[f"{h}일" for h in HORIZONS]]).to_string(index=False))

    show_h = [1, 5, 20, 60, 240]
    print("\n=== [전체] 10개 그룹별 시장 대비 초과수익률 (비용 전)  1그룹 = 가장 많이 순매도 … 10그룹 = 가장 많이 순매수")
    for inv, g in groups[groups["시장"] == "전체"].groupby("투자자", sort=False):
        g = g.set_index("보유기간").loc[show_h]
        tab = pd.DataFrame({f"{h}일": [pct(g.loc[h, f"G{k}_초과"]) for k in range(1, N_GROUPS + 1)] for h in show_h},
                           index=[f"G{k}" for k in range(1, N_GROUPS + 1)]).T
        tab["IC(t)"] = [f"{g.loc[h, 'IC평균']:+.3f}" + (f"({g.loc[h, 'IC_t_NW']:+.1f})" if h in TESTED else "")
                        for h in show_h]
        print(f"\n[{inv}]")
        print(tab.to_string())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--min-cap", type=float, default=500, help="유니버스 최소 시가총액(억, 그날 기준)")
    p.add_argument("--cost", type=float, default=0.0025, help="왕복 거래비용 (0.0025 = 0.25%%)")
    args = p.parse_args()

    nb, px = load("netbuy"), load("ohlcv")
    names = nb.drop_duplicates("종목코드", keep="last").set_index("종목코드")["종목명"]
    days = sorted(px["일자"].unique())

    u = build_universe(px, names, args.min_cap)
    fwd, tickers = forward_returns(px, days)
    u = attach_forward(u, fwd, tickers, days)
    per_day = u.groupby("일자").size()
    print(f"기간 {days[0]}~{days[-1]} {len(days)}영업일, 유니버스 하루 평균 {per_day.mean():.0f}종목 "
          f"(시총 {args.min_cap:.0f}억 이상, 스팩·우선주·리츠·거래정지 제외), 그룹당 약 {per_day.mean() / 20:.0f}종목/시장")

    tests, groups, daily = [], [], []
    for inv in INVESTORS:
        d = assign_groups(u, nb, inv)
        port = daily_portfolios(d)
        ic = daily_ic(d)
        tests += run_tests(port, inv, days, args.cost)
        groups += group_table(port, ic, inv)
        daily.append(port.reset_index().assign(투자자=inv))
        print(f"  {inv} 완료")

    tests, groups = pd.DataFrame(tests), pd.DataFrame(groups)
    out = ROOT / "data"
    tests.to_csv(out / "investor_flow_decile_tests.csv", index=False, encoding="utf-8-sig")
    groups.to_csv(out / "investor_flow_decile_groups.csv", index=False, encoding="utf-8-sig")
    pd.concat(daily).to_csv(out / "investor_flow_decile_daily.csv.gz", index=False, encoding="utf-8-sig")

    print_results(tests, groups, args.cost)
    print("\n※ 120일 이상은 안 겹치는 표본이 3개 이하라 t값 없음 (평균만 참고)")
    print("저장: data/investor_flow_decile_tests.csv, data/investor_flow_decile_groups.csv, data/investor_flow_decile_daily.csv.gz")


if __name__ == "__main__":
    main()
