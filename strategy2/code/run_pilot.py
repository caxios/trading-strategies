"""strategy2 연구계획서 5절 파일럿: 2019-01-01 ~ 2020-12-31, 50종목으로 4~10절 전체를 끝까지 실행한다.

목적은 파이프라인이 끝까지 돌고 데이터 문제가 드러나는지 보는 것이다(5절 3항: 수익률 수치는 해석하지 않는다).
분석 함수는 analysis.py 에 있고, 결과는 strategy2/results/pilot/ 에 저장한다(selection.csv = 고른 50종목).

사용 예:
    python strategy2/code/run_pilot.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis as an  # noqa: E402
import research as rs  # noqa: E402

OUT = rs.ROOT / "strategy2" / "results" / "pilot"
START, END = "2019-01-01", "2020-12-31"
YEARS = [2017, 2018, 2019, 2020, 2021]   # 앞쪽 2년은 252일 모멘텀·60일 창, 2021 은 보유 기간 수익률용
TRANSFERS = ["036420", "003670", "192080", "068270", "097520"]  # 기간 중·인접 시장 이전 (ticker_mapping.csv)


def select_pilot() -> pd.DataFrame:
    """5절 1항 기준: 2018-12-28 기준 KOSPI 대형 10, KOSPI 중소형 10, KOSDAQ 20, 기간 중 상폐 5, 이전상장 5."""
    m = rs.eligible_master()
    p = pd.read_parquet(rs.CLEAN / "panel_2018.parquet", columns=["date", "code", "market", "mktcap"])
    p = p[(p["date"] == p["date"].max()) & p["code"].isin(m.index)]
    rng = np.random.default_rng(an.SEED)
    chosen = {}

    def take(cands, k, why, random=True):
        cands = [c for c in cands if c not in chosen]
        pick = list(rng.choice(cands, size=min(k, len(cands)), replace=False)) if random else cands[:k]
        chosen.update({c: why for c in pick})

    take(TRANSFERS, 5, "시장 이전", random=False)
    dl = m[(m["delisted"] == "True") & m["last_date"].between("20190101", "20201231")].index
    take(sorted(set(dl) & set(p["code"])), 5, "기간 중 상폐")
    kospi = p[p["market"] == "KOSPI"].sort_values("mktcap", ascending=False)["code"].tolist()
    take(kospi, 10, "KOSPI 대형", random=False)
    take(kospi[100:], 10, "KOSPI 중소형 (시총 101위 이하)")
    take(sorted(p.loc[p["market"] == "KOSDAQ", "code"]), 20, "KOSDAQ")
    sel = pd.DataFrame({"code": list(chosen), "reason": list(chosen.values())})
    sel["name"] = sel["code"].map(m["name"])
    sel["last_date"] = sel["code"].map(m["last_date"])
    return sel


def main():
    an.setup(OUT, YEARS)
    sel = select_pilot()
    sel.to_csv(OUT / "selection.csv", index=False, encoding="utf-8-sig")
    an.log("선정 종목:", sel.groupby("reason").size().to_dict())
    master = rs.eligible_master().loc[sel["code"]]
    sigs = rs.signal_days(rs.calendar().index, START, END)
    wide, sectors = rs.load_wide(YEARS, sel["code"].tolist(), sector_dates=sigs)
    an.log(f"행렬 {wide['exists'].shape}, 기간 {wide['exists'].index[0].date()} ~ {wide['exists'].index[-1].date()}")
    main_run = an.analyze(wide, sectors, master, sigs, rs.W_MAIN)
    an.leakage_check(wide, sectors, master, sigs, main_run["sc"], rs.W_MAIN)
    bm = main_run["bm"]
    dl = set(master.index[master["delisted"] == "True"])
    an.log("기준 시장에 포함된 상폐 종목 수(연도별):",
           bm[bm["code"].isin(dl)].groupby(bm["date"].dt.year)["code"].nunique().to_dict())
    an.analyze(wide, sectors, master, sigs, 20, holds=(rs.HOLD,), groups=an.MAIN_GROUPS, full=False)
    an.save_log()


if __name__ == "__main__":
    main()
