"""순매수 '방향' 효과 vs '거래 규모' 효과 분리 검증 (investor_flow_decile_backtest.py 후속).

10분위 분석에서 기관은 1그룹(가장 많이 순매도)과 10그룹(가장 많이 순매수)이 모두 시장보다 나은
U자 모양이 나왔다. 이것이 "기관이 판 종목이 반등한다(방향 효과)"인지,
"기관이 많이 거래하는 종목이 소외주보다 낫다(규모 효과)"인지 두 가지로 확인한다.

검증 A — 1그룹 vs 10그룹 직접 비교 (둘 다 기관이 많이 거래한 종목)
    D_d^h = R_{1,d}^h − R_{10,d}^h         (R = 10분위 포트폴리오의 시장 대비 초과수익률)
    H0: E[D] = 0 (양측).  D > 0 이면 같은 규모로 거래했을 때 판 종목이 산 종목보다 낫다 → 방향 효과.

검증 B — 시가총액 × 투자자 거래규모 통제 (조건부 이중 정렬)
    날짜·시장마다
      1) 시가총액으로 3등분 (소/중/대형)
      2) 각 시가총액 구간 안에서 투자자 거래규모 a = (매수거래대금 + 매도거래대금) / 시가총액 으로 3등분
         → 9개 셀. 같은 셀 = 크기와 그 투자자의 손길이 비슷한 종목
      3) 셀 안에서 순매수 강도 x = 순매수거래대금 / 시가총액 의 백분위로
           하위 30% = 순매도 그룹, 상위 30% = 순매수 그룹
    셀 대비 초과수익률 c = 종목 h일 수익률 − 같은 셀 전 종목 h일 수익률 평균
    날짜별 포트폴리오: C_매도,d = 순매도 그룹 종목의 c 평균, C_매수,d = 순매수 그룹 종목의 c 평균
    H0: E[C_매도] = 0, E[C_매수] = 0, E[C_매수 − C_매도] = 0 (양측)
    C_매도 > 0 이면 "같은 크기·같은 거래규모 종목 중에서 그 투자자가 판 종목이 더 오른다" → 저점 매수 근거.

t값: 날짜별 포트폴리오 수익률 시계열에 Newey-West (시차 h−1), 안 겹치는 표본 t 범위로 교차 검증.
유니버스, 수익률, 상장폐지 처리는 investor_flow_decile_backtest.py 와 같다.

출력:
  data/investor_flow_control_tests.csv : 검증 A, B 결과
  data/investor_flow_control_cells.csv : 검증 B 의 거래규모 구간별 결과

사용 예:
    python investor_flow_control_backtest.py
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from investor_flow_decile_backtest import (HORIZONS, INVESTORS, TESTED, assign_groups, attach_forward,
                                           build_universe, forward_returns, nonoverlap_t)
from netsell_reversal_backtest import load, nw_tstat

ROOT = Path(__file__).resolve().parent
TWO_SIDED_Z = 1.96
TAIL = 0.3  # 셀 안 하위/상위 30%


def tstats(y: pd.Series, h: int, days) -> dict:
    y = y.dropna().sort_index()
    out = {"T": len(y), "평균": y.mean()}
    if h in TESTED:
        t = nw_tstat(y.to_numpy(), h - 1)
        med, lo, hi, _ = nonoverlap_t(y, h, days)
        out.update({"t_NW": t, "유의_5%(양측)": abs(t) > TWO_SIDED_Z,
                    "비중첩_t_중앙값": med, "비중첩_t_최소": lo, "비중첩_t_최대": hi})
    return out


# ---------------------------------------------------------------- 검증 A
def test_a(d: pd.DataFrame, inv: str, days) -> list[dict]:
    rows = []
    for h in HORIZONS:
        p = d.groupby(["그룹", "일자"])[f"초과_{h}"].mean().unstack(0)
        diff = p[1] - p[10]
        rows.append({"검증": "A: 1그룹 − 10그룹", "투자자": inv, "구간": "전체", "보유기간": h,
                     "1그룹": p[1].mean(), "10그룹": p[10].mean(), **tstats(diff, h, days)})
    return rows


# ---------------------------------------------------------------- 검증 B
def assign_cells(d: pd.DataFrame, nb: pd.DataFrame, inv: str) -> pd.DataFrame:
    g = nb.loc[nb["투자자"] == inv].set_index(["일자", "종목코드"])
    gross = (g["매수거래대금"] + g["매도거래대금"]).reindex(list(zip(d["일자"], d["종목코드"]))).fillna(0)
    d = d.copy()
    d["a"] = gross.to_numpy() / d["시가총액"]
    d["크기"] = d.groupby(["일자", "시장"])["시가총액"].transform(lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
    d["규모"] = d.groupby(["일자", "시장", "크기"])["a"].transform(lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
    cell = d.groupby(["일자", "시장", "크기", "규모"])
    q = cell["x"].rank(pct=True)  # 동률(순매수 0)은 평균 순위 → 중간으로 빠짐
    d["방향"] = np.where(q <= TAIL, "순매도", np.where(q > 1 - TAIL, "순매수", ""))
    for h in HORIZONS:
        d[f"셀초과_{h}"] = d[f"수익_{h}"] - cell[f"수익_{h}"].transform("mean")
    return d


def test_b(d: pd.DataFrame, inv: str, days, cost: float) -> tuple[list[dict], list[dict]]:
    rows, cells = [], []
    s = d[d["방향"] != ""]
    for h in HORIZONS:
        c = s.groupby(["방향", "일자"])[f"셀초과_{h}"].mean().unstack(0)
        m = s.groupby(["방향", "일자"])[f"초과_{h}"].mean().unstack(0)
        for name, y in [("B: 순매도 (셀 대비)", c["순매도"]), ("B: 순매수 (셀 대비)", c["순매수"]),
                        ("B: 순매수 − 순매도 (셀 대비)", c["순매수"] - c["순매도"]),
                        ("B: 순매도 (시장 대비, 비용 후)", m["순매도"] - cost)]:
            rows.append({"검증": name, "투자자": inv, "구간": "전체", "보유기간": h, **tstats(y, h, days)})
        # 거래규모 구간별 (크기 구간은 합침)
        for lvl, lab in enumerate(["거래규모 하", "거래규모 중", "거래규모 상"]):
            sub = s[s["규모"] == lvl]
            cc = sub.groupby(["방향", "일자"])[f"셀초과_{h}"].mean().unstack(0)
            for side in ["순매도", "순매수"]:
                cells.append({"투자자": inv, "구간": lab, "방향": side, "보유기간": h, **tstats(cc[side], h, days)})
    return rows, cells


# ---------------------------------------------------------------- 출력
def fmt(r, pct=True):
    v = f"{r['평균'] * 100:+.2f}%"
    if r["보유기간"] in TESTED and pd.notna(r.get("t_NW")):
        v += f"({r['t_NW']:+.1f}){'*' if r['유의_5%(양측)'] else ''}"
    return v


def print_results(tests: pd.DataFrame, cells: pd.DataFrame):
    show = [1, 5, 10, 20, 60, 120, 240]
    print("\n=== 검증 A: 1그룹(가장 순매도) − 10그룹(가장 순매수), 시장 대비 초과수익률 차이 (NW t)  * 양측 5%")
    a = tests[tests["검증"].str.startswith("A")]
    lines = [[inv, *[fmt(g.set_index("보유기간").loc[h].to_dict() | {"보유기간": h}) for h in show]]
             for inv, g in a.groupby("투자자", sort=False)]
    print(pd.DataFrame(lines, columns=["투자자", *[f"{h}일" for h in show]]).to_string(index=False))

    print("\n=== 검증 B: 시가총액 × 거래규모 9개 셀 통제 후 (NW t)  * 양측 5%")
    b = tests[tests["검증"].str.startswith("B")]
    lines = []
    for (inv, name), g in b.groupby(["투자자", "검증"], sort=False):
        g = g.set_index("보유기간")
        lines.append([inv, name[3:], *[fmt(g.loc[h].to_dict() | {"보유기간": h}) for h in show]])
    print(pd.DataFrame(lines, columns=["투자자", "포트폴리오", *[f"{h}일" for h in show]]).to_string(index=False))

    print("\n=== 검증 B 거래규모 구간별: 셀 대비 초과수익률 (NW t)")
    lines = []
    for (inv, lab, side), g in cells.groupby(["투자자", "구간", "방향"], sort=False):
        g = g.set_index("보유기간")
        lines.append([inv, lab, side, *[fmt(g.loc[h].to_dict() | {"보유기간": h}) for h in [5, 20, 60]]])
    print(pd.DataFrame(lines, columns=["투자자", "구간", "방향", "5일", "20일", "60일"]).to_string(index=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--min-cap", type=float, default=500)
    p.add_argument("--cost", type=float, default=0.0025)
    args = p.parse_args()

    nb, px = load("netbuy"), load("ohlcv")
    names = nb.drop_duplicates("종목코드", keep="last").set_index("종목코드")["종목명"]
    days = sorted(px["일자"].unique())
    u = build_universe(px, names, args.min_cap)
    fwd, tickers = forward_returns(px, days)
    u = attach_forward(u, fwd, tickers, days)

    tests, cells = [], []
    for inv in INVESTORS:
        d = assign_groups(u, nb, inv)
        tests += test_a(d, inv, days)
        d = assign_cells(d, nb, inv)
        r, c = test_b(d, inv, days, args.cost)
        tests += r
        cells += c
        print(f"  {inv} 완료 (셀당 평균 {d.groupby(['일자', '시장', '크기', '규모']).size().mean():.0f}종목)")

    tests, cells = pd.DataFrame(tests), pd.DataFrame(cells)
    tests.to_csv(ROOT / "data" / "investor_flow_control_tests.csv", index=False, encoding="utf-8-sig")
    cells.to_csv(ROOT / "data" / "investor_flow_control_cells.csv", index=False, encoding="utf-8-sig")
    print_results(tests, cells)
    print("\n저장: data/investor_flow_control_tests.csv, data/investor_flow_control_cells.csv")


if __name__ == "__main__":
    main()
