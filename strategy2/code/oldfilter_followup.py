"""옛 점수(조용한 꾸준한 매수)의 2022년 신호일 선별 종목 사후 추적: 2023~2026 주가 수익률.

연구자 결정(logs/assumptions.md 7절, 2026-11-05)에 따른 사후 확인이다. 점수·필터·분위는 설계 확인 구간에서
저장한 scores_W60_H20.parquet 를 그대로 쓴다(재계산·수정 없음).

수익률 정의 (종목 i, 신호일 t, 보유 끝 날 T):
    R_i = AdjClose_{i,T} / AdjOpen_{i,t+1} − 1
    - 진입: 신호 다음 거래일 시가(수정). 그날 시가가 없으면(거래정지) 그 종목은 뺀다.
    - 보유 끝 T: 진입일부터 250거래일(약 1년), 500거래일(약 2년), 그리고 자료 마지막 날(2026-10-22).
    - 상장폐지 종목은 마지막 거래 가격을 그대로 유지한다(정리매매 가격 포함, 폐지 후 0원 처리는 하지 않음 → 성과를 다소 좋게 봄).
    - 거래비용은 빼지 않는다(장기 보유라 왕복 비용 약 1% 수준으로 결론에 영향 작음).
비교 기준:
    - 같은 신호일 분위 1~10 전체(필터 통과 후보 전체)의 동일 가중 평균
    - 같은 기간 종목 소속 시장 지수 수익률(KOSPI/KOSDAQ 종가 기준) → 지수 대비 초과수익률

결과: strategy2/results/oldfilter_followup/
    decile_summary.csv   그룹 × 보유 기간 × 분위: 평균·중앙값·2배 이상 비율·반토막 비율 (2022년 신호일 평균)
    picks_20221229.csv   2022-12-29 상위 10% 종목별 수익률
    picks_2022_all.csv   2022년 신호일 상위 10% 종목-신호일별 수익률
    report.md            요약
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research as rs  # noqa: E402

OUT = rs.ROOT / "strategy2" / "results" / "oldfilter_followup"
SCORES = rs.ROOT / "strategy2" / "results" / "design" / "scores_W60_H20.parquet"
HORIZONS = {"1y": 250, "2y": 500, "to_end": None}
GROUPS = ["FOR", "INST"]


def load_prices():
    cols = ["date", "code", "adj_open", "adj_close"]
    p = pd.concat([pd.read_parquet(rs.CLEAN / f"panel_{y}.parquet", columns=cols) for y in range(2022, 2027)])
    ao = p.pivot(index="date", columns="code", values="adj_open").sort_index()
    ac = p.pivot(index="date", columns="code", values="adj_close").sort_index()
    return ao, ac.ffill()  # 상폐·정지 후에는 마지막 가격 유지


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sc = pd.read_parquet(SCORES, columns=["code", "date", "group", "score", "q", "kosdaq"])
    sc = sc[sc["group"].isin(GROUPS) & (sc["date"].dt.year == 2022)].copy()
    master = pd.read_csv(rs.CLEAN / "master.csv", dtype=str).set_index("code")
    ao, ac = load_prices()
    days = ac.index
    idx = rs.calendar().reindex(days)
    lidx = {m: np.log1p(idx[m].fillna(0)).cumsum() for m in ("KOSPI", "KOSDAQ")}
    last = len(days) - 1

    rows = []
    for t, d in sc.groupby("date"):
        e = days.searchsorted(t, side="right")  # 신호 다음 거래일
        assert days[e] > t
        codes = d["code"].to_numpy()
        o = ao.iloc[e].reindex(codes).to_numpy()
        for h, n in HORIZONS.items():
            x = last if n is None else e + n - 1
            if x > last:
                continue
            c = ac.iloc[x].reindex(codes).to_numpy()
            with np.errstate(invalid="ignore", divide="ignore"):
                r = np.where(o > 0, c / o - 1, np.nan)
            # 지수: 진입 전일 종가 → 끝 날 종가 (지수 시가가 없어 근사)
            mk = {m: np.expm1(lidx[m].iloc[x] - lidx[m].iloc[e - 1]) for m in lidx}
            rm = np.where(d["kosdaq"].to_numpy() == 1, mk["KOSDAQ"], mk["KOSPI"])
            rows.append(pd.DataFrame({"group": d["group"].to_numpy(), "date": t, "code": codes, "q": d["q"].to_numpy(),
                                      "score": d["score"].to_numpy(), "horizon": h, "entry": days[e], "exit": days[x],
                                      "R": r, "R_index": rm}))
    res = pd.concat(rows, ignore_index=True).dropna(subset=["R"])
    res["Rex_index"] = res["R"] - res["R_index"]
    res["name"] = res["code"].map(master["name"])
    res["delisted"] = res["code"].map(master["delisted"]).eq("True") & (
        pd.to_datetime(res["code"].map(master["last_date"])) < res["exit"])

    # 신호일 × 분위 단면 통계 → 2022년 신호일 평균
    def stats(g):
        return pd.Series({"mean": g["R"].mean(), "median": g["R"].median(), "ex_index": g["Rex_index"].mean(),
                          "share_x2": (g["R"] >= 1).mean(), "share_half": (g["R"] <= -0.5).mean(), "n": len(g)})
    per = res.groupby(["group", "horizon", "date", "q"]).apply(stats).reset_index()
    allq = res.groupby(["group", "horizon", "date"]).apply(stats).reset_index().assign(q=0)  # 0 = 후보 전체
    per = pd.concat([per, allq])
    summ = per.groupby(["group", "horizon", "q"])[["mean", "median", "ex_index", "share_x2", "share_half", "n"]].mean()
    summ["n_dates"] = per.groupby(["group", "horizon", "q"]).size()
    summ.to_csv(OUT / "decile_summary.csv", encoding="utf-8-sig")

    top = res[res["q"] == 10].sort_values(["group", "horizon", "date", "score"], ascending=[True, True, True, False])
    cols = ["group", "date", "code", "name", "score", "horizon", "entry", "exit", "R", "R_index", "Rex_index", "delisted"]
    top[cols].to_csv(OUT / "picks_2022_all.csv", index=False, encoding="utf-8-sig")
    lastsig = top[top["date"] == top["date"].max()]
    wide = lastsig.pivot_table(index=["group", "code", "name", "score"], columns="horizon", values="R").reset_index()
    wide = wide.sort_values(["group", "score"], ascending=[True, False])
    wide.to_csv(OUT / "picks_20221229.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print(summ.round(3).to_string())
    print("\n2022-12-29 묶음 (분위별, 끝까지):")
    l = res[(res["date"] == res["date"].max())]
    print(l.groupby(["group", "horizon", "q"]).apply(stats).unstack("horizon").round(3).to_string())
    print("\n2022-12-29 상위 10%:")
    print(wide.round(3).to_string(index=False))
    print("\n데이터 끝:", days[-1].date(), "/ 상폐 처리된 상위 종목-신호 수:",
          int(top.loc[top.horizon == "to_end", "delisted"].sum()))


if __name__ == "__main__":
    main()
