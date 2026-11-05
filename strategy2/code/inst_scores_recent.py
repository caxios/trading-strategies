"""옛 점수(기관 INST)를 2023-01 ~ 자료 끝(2026-10-22) 신호일에 대해 계산하고, 시청자용 선별 목록을 만든다.

점수·필터는 설계 확인 구간과 같은 코드(research.cross_sections, 창 W=60거래일)를 그대로 쓴다.
2022-12 신호일도 함께 계산해 설계 단계 저장 점수와 같은지 확인한다(이어 붙이기 점검).

결과: strategy2/results/inst_strategy/
    scores_INST_2015_2026.parquet  2015~2026 기관 점수·분위 (2015~2022 = 설계 저장본, 2023~ = 이번 계산)
    picks_2025_2026.csv            2025-01 ~ 자료 끝 신호일별 기관 상위 10% 종목
    picks_latest.csv               마지막 신호일 기관 상위 10% 종목
    picks_2025_2026_freq.csv       2025~2026 종목별 상위 10% 선정 횟수
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research as rs  # noqa: E402

OUT = rs.ROOT / "strategy2" / "results" / "inst_strategy"
DESIGN = rs.ROOT / "strategy2" / "results" / "design" / "scores_W60_H20.parquet"
YEARS = list(range(2022, 2027))
START = "2022-12-01"
COLS = ["code", "date", "group", "score", "q", "C", "P", "Stilde", "CAR", "mktcap", "kosdaq"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    master = rs.eligible_master()
    master = master[master["last_date"] >= "20220101"]
    days_all = rs.calendar().index
    sigs = rs.signal_days(days_all, START, str(days_all[-1].date()))
    wide, sectors = rs.load_wide(YEARS, master.index.tolist(), sector_dates=sigs)
    print(f"행렬 {wide['exists'].shape}, {wide['exists'].index[0].date()} ~ {wide['exists'].index[-1].date()}, "
          f"신호일 {len(sigs)}개 ({sigs[0].date()} ~ {sigs[-1].date()})", flush=True)
    ind = rs.indicators(wide, rs.W_MAIN, groups=("INST",), rows=sigs)
    sc, _, cnt = rs.cross_sections(wide, ind, master, sectors, sigs, rs.W_MAIN, groups=("INST",))
    del ind, wide
    sc["q"] = sc.groupby("date")["score"].transform(lambda x: rs.qassign(x, rs.NQ))
    print("필터 단계별 종목 수 평균:\n", cnt.drop(columns="date").mean().round(1).to_string(), flush=True)

    # 이어 붙이기 점검: 2022-12 신호일은 설계 저장본과 같아야 한다
    old = pd.read_parquet(DESIGN, columns=COLS)
    old = old[old["group"] == "INST"]
    chk = sc[sc["date"] <= "2022-12-31"].merge(old, on=["date", "code"], suffixes=("", "_d"))
    n_new = (sc["date"] <= "2022-12-31").sum()
    n_old = (old["date"] >= START).sum()
    print(f"\n점검(2022-12): 이번 {n_new}행, 설계본 {n_old}행, 공통 {len(chk)}행, "
          f"점수 최대 차이 {np.abs(chk['score'] - chk['score_d']).max():.2e}, 분위 일치 {(chk['q'] == chk['q_d']).mean():.1%}",
          flush=True)

    allsc = pd.concat([old[old["date"] < "2023-01-01"], sc.loc[sc["date"] >= "2023-01-01", COLS]], ignore_index=True)
    allsc.to_parquet(OUT / "scores_INST_2015_2026.parquet")

    names = rs.eligible_master()["name"]
    top = allsc[(allsc["q"] == 10) & (allsc["date"] >= "2025-01-01")].copy()
    top["name"] = top["code"].map(names)
    top["market"] = np.where(top["kosdaq"] == 1, "KOSDAQ", "KOSPI")
    top = top.sort_values(["date", "score"], ascending=[True, False])
    out_cols = ["date", "code", "name", "market", "score", "C", "P", "CAR", "mktcap"]
    top[out_cols].to_csv(OUT / "picks_2025_2026.csv", index=False, encoding="utf-8-sig")
    latest = top[top["date"] == top["date"].max()]
    latest[out_cols].to_csv(OUT / "picks_latest.csv", index=False, encoding="utf-8-sig")
    freq = (top.groupby(["code", "name", "market"])
            .agg(n=("date", "size"), first=("date", "min"), last=("date", "max"), score_mean=("score", "mean"))
            .sort_values("n", ascending=False).reset_index())
    freq.to_csv(OUT / "picks_2025_2026_freq.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(f"\n2025~ 신호일 {top['date'].nunique()}개, 상위 10% 행 {len(top)}, 서로 다른 종목 {len(freq)}")
    print(f"\n마지막 신호일 {latest['date'].max().date()} 상위 10% ({len(latest)}종목):")
    print(latest[["code", "name", "market", "score", "C", "P", "CAR"]].round(3).to_string(index=False))
    print("\n2025~2026 선정 횟수 상위 20:")
    print(freq.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
