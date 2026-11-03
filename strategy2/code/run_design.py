"""strategy2 설계 확인 구간 본 분석: 신호일 2015-01-01 ~ 2022-12-31, 전체 유니버스 (연구계획서 6~8·10절).

2014~2022년 패널만 읽는다. 보유 만기가 2022년 마지막 거래일을 넘는 신호일은 수익률이 없어 자동으로 빠지므로,
설계 단계에서 2023년 이후(표본 외 구간) 가격은 한 번도 쓰지 않는다(계획서 0절 2항).
결과는 strategy2/results/design/ 에 저장한다(파일 목록은 analysis.py 머리말).

사용 예:
    python strategy2/code/run_design.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis as an  # noqa: E402
import research as rs  # noqa: E402

OUT = rs.ROOT / "strategy2" / "results" / "design"
START, END = "2015-01-01", "2022-12-31"
YEARS = list(range(2014, 2023))


def main():
    an.setup(OUT, YEARS)
    master = rs.eligible_master()
    master = master[(master["first_date"] <= "20221231") & (master["last_date"] >= "20140102")]
    sigs = rs.signal_days(rs.calendar().index, START, END)
    wide, sectors = rs.load_wide(YEARS, master.index.tolist(), sector_dates=sigs)
    days = wide["exists"].index
    assert days[-1] <= pd.Timestamp(END), "설계 단계에서 표본 외 구간 자료를 읽음"
    an.log(f"행렬 {wide['exists'].shape}, 기간 {days[0].date()} ~ {days[-1].date()}, 신호일 {len(sigs)}개")
    tr = wide["halted"] == 0
    an.log(f"거래일인데 수정 시가 결측: {int((tr & wide['adj_open'].isna()).sum().sum())}건, "
           f"거래일 순매수(FOR) 결측: {int((tr & wide['FOR_net'].isna()).sum().sum())}건 / {int(tr.sum().sum())}")
    del tr

    main_run = an.analyze(wide, sectors, master, sigs, rs.W_MAIN)
    an.log("\n----- 10절 점검 -----")
    an.leakage_check(wide, sectors, master, sigs, main_run["sc"], rs.W_MAIN)
    bm = main_run["bm"]
    dl = set(master.index[master["delisted"] == "True"])
    an.log("10절 5번: 기준 시장에 포함된 상폐 종목 수(연도별):",
           bm[bm["code"].isin(dl)].groupby(bm["date"].dt.year)["code"].nunique().to_dict())
    an.log("기준 시장 종목 수(신호일 평균, 연도별):",
           bm.groupby([bm["date"].dt.year, "date"]).size().groupby(level=0).mean().round(0).to_dict())
    an.figures(main_run["results"])
    results = main_run["results"]
    del main_run
    an.save_log()
    # 11.2절 표 7 강건성: 창 20일 (판정 기준인 보유 20거래일)
    an.analyze(wide, sectors, master, sigs, 20, holds=(rs.HOLD,), groups=an.MAIN_GROUPS, full=False)
    an.save_log()
    return results


if __name__ == "__main__":
    main()
