"""재미용 전략: 옛 점수(기관 INST) 상위 10% 종목 장기 보유 + 리밸런싱 방식 비교 (2015~2025 연도별 묶음).

묶음(cohort): 연도 Y 의 첫 신호일(첫 주 마지막 거래일)에 기관 점수 상위 10%인 종목. 다음 거래일 시가에 동일 금액 매수.
보유 기간 H: 6개월(125거래일), 1년(250), 2년(500), 3년(750), 4년(1000), 5년(1250). 자료 끝(2026-10-22)을 넘는 H 는 계산하지 않는다.

리밸런싱 방식 (매 21거래일 = 약 1개월, 종가 기준):
    EW   동일 비중: 거래 가능한 보유 종목을 모두 같은 금액으로 다시 맞춘다(오른 종목을 덜어 떨어진 종목에 보탠다).
    BH   방치: 처음 산 뒤 손대지 않는다. 오른 종목의 비중이 자연히 커진다.
    WIN  승자 가중: g_i = 현재 가격 / 매수 가격. g_i ≤ 0.7(−30% 이하)이면 전량 매도하고 다시 사지 않는다.
         남은 종목의 목표 비중 ∝ g_i², 즉 수익이 날수록 비중을 더 크게 싣는다.
공통 규칙:
    - 거래정지 종목은 그날 사고팔지 않고 그대로 둔다. 상장폐지되면 마지막 가격으로 현금화(폐지 후 0원 처리 안 함).
    - 현금은 수익 0. EW·WIN 은 다음 리밸런싱 때 현금을 다시 투자하고, BH 는 현금으로 둔다.
    - 비용: 매수 = 수수료 0.015% + 반스프레드 0.2%, 매도 = 수수료 + 반스프레드 + 그 해 거래세. 보유 끝 날 전부 매도한다고 보고 비용을 뺀다.
비교 대상 (모두 같은 날 진입, 동일 금액 매수 후 방치):
    ALL   같은 날 기관 필터 통과 후보 전체(분위 1~10)
    BOT   기관 점수 하위 10%
    KOSPI, KOSDAQ 지수 (진입 전일 종가 기준)

결과: strategy2/results/inst_strategy/
    cohort_results.csv   묶음 × 보유 기간 × 방식: 총수익률, 연환산, 최대낙폭, 한 종목 최대 비중, 회전율
    summary.csv          보유 기간 × 방식: 묶음 평균·중앙값, 후보 전체·KOSPI 를 이긴 묶음 수
    cohort_stocks.csv    묶음 종목별 매수 후 방치 수익률(보유 기간별)
    paths.parquet        묶음 × 방식 일별 가치
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research as rs  # noqa: E402

OUT = rs.ROOT / "strategy2" / "results" / "inst_strategy"
H = {"6m": 125, "1y": 250, "2y": 500, "3y": 750, "4y": 1000, "5y": 1250}
REB = 21
HALF_SPREAD = 0.002
STOP = 0.7
POWER = 2.0
COHORTS = range(2015, 2026)


def load_px(codes):
    cols = ["date", "code", "ret", "adj_open", "adj_close", "halted"]
    ps = []
    for y in range(2015, 2027):
        p = pd.read_parquet(rs.CLEAN / f"panel_{y}.parquet", columns=cols)
        ps.append(p[p["code"].isin(codes)])
    p = pd.concat(ps)
    days = rs.calendar().index
    days = days[days >= p["date"].min()]
    piv = {c: p.pivot(index="date", columns="code", values=c).reindex(days) for c in cols[2:]}
    return days, piv


def tax_on(dates):
    t = pd.read_csv(rs.CLEAN / "ref" / "tax_rates.csv", parse_dates=["settle_from", "settle_to"])
    return np.array([t.loc[(t.settle_from <= d) & (d <= t.settle_to), "kospi_total"].iloc[0] / 100 for d in dates])


def simulate(codes, e, n, px, tax, mode):
    """진입일 위치 e 부터 n 거래일 동안의 일별 포트폴리오 가치(매도 비용 차감 전)와 보조 기록."""
    ao = px["adj_open"].iloc[e][codes].to_numpy(float)
    ok = np.isfinite(ao) & (ao > 0)
    codes = [c for c, k in zip(codes, ok) if k]
    ao = ao[ok]
    ret = px["ret"].iloc[e:e + n][codes].to_numpy(float)
    ac = px["adj_close"].iloc[e:e + n][codes].to_numpy(float)
    halted = px["halted"].iloc[e:e + n][codes].to_numpy(float)
    alive = np.isfinite(ac)                               # 상장 중(행이 있음)
    k = len(codes)
    cb = rs.FEE + HALF_SPREAD
    hold = np.full(k, (1.0 / k) / (1 + cb))               # 1원을 나눠 매수(매수 비용 차감)
    hold *= ac[0] / ao                                    # 진입일: 시가 → 종가
    cash, active = 0.0, np.ones(k, bool)
    vals, maxw, turnover = [hold.sum()], [hold.max() / hold.sum()], 0.0
    for d in range(1, n):
        r = np.where(alive[d], np.nan_to_num(ret[d]), 0.0)
        hold = hold * (1 + r)
        gone = active & ~alive[d] & alive[d - 1]          # 오늘 사라짐(상폐) → 직전 가격으로 현금화
        if gone.any():
            cash += hold[gone].sum() * (1 - rs.FEE - HALF_SPREAD - tax[e + d])
            hold[gone], active[gone] = 0.0, False
        if mode != "BH" and d % REB == 0:
            trad = active & alive[d] & (halted[d] == 0)
            if mode == "WIN":
                g = ac[d] / ao
                stop = trad & (g <= STOP)
                if stop.any():
                    sell = hold[stop].sum()
                    cash += sell * (1 - rs.FEE - HALF_SPREAD - tax[e + d])
                    turnover += sell
                    hold[stop], active[stop] = 0.0, False
                    trad &= ~stop
                tgt_w = np.where(trad, np.nan_to_num(g) ** POWER, 0.0)
            else:
                tgt_w = trad.astype(float)
            if tgt_w.sum() > 0:
                pool = hold[trad].sum() + cash
                tgt = np.zeros(k)
                tgt[trad] = pool * tgt_w[trad] / tgt_w[trad].sum()
                diff = tgt - hold
                sells = -diff[diff < 0].sum()
                buys = diff[diff > 0].sum()
                # 비용: 매도분에서 세금·수수료, 매수분에서 수수료 → 목표 금액을 비용만큼 비례 축소
                cost = sells * (rs.FEE + HALF_SPREAD + tax[e + d]) + buys * cb
                scale = (pool - cost) / pool
                hold = np.where(trad, tgt * scale, hold)
                cash = 0.0
                turnover += sells + buys
        tot = hold.sum() + cash
        vals.append(tot)
        maxw.append(hold.max() / tot if tot > 0 else np.nan)
    return np.array(vals), np.array(maxw), turnover, hold, cash


def stock_bh(codes, e, x, px):
    ao = px["adj_open"].iloc[e][codes]
    ac = px["adj_close"].iloc[:x + 1][codes].ffill().iloc[x]
    return ac / ao - 1


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sc = pd.read_parquet(OUT / "scores_INST_2015_2026.parquet")
    names = pd.read_csv(rs.CLEAN / "master.csv", dtype=str).set_index("code")["name"]
    firsts = {y: sc.loc[sc["date"].dt.year == y, "date"].min() for y in COHORTS}
    sc_c = sc[sc["date"].isin(firsts.values())]
    days, px = load_px(sc_c["code"].unique())
    tax = tax_on(days)
    last = len(days) - 1
    idx = rs.calendar().reindex(days)
    lidx = {m: np.log1p(idx[m].fillna(0)).cumsum().to_numpy() for m in ("KOSPI", "KOSDAQ")}

    rows, stock_rows, paths = [], [], []
    for y, t in firsts.items():
        d = sc_c[sc_c["date"] == t]
        e = days.searchsorted(t, side="right")
        n_max = min(max(H.values()), last - e + 1)
        groups = {"EW": d.loc[d.q == 10, "code"].tolist(), "BH": d.loc[d.q == 10, "code"].tolist(),
                  "WIN": d.loc[d.q == 10, "code"].tolist(), "ALL": d["code"].tolist(), "BOT": d.loc[d.q == 1, "code"].tolist()}
        sims = {}
        for name, codes in groups.items():
            mode = name if name in ("EW", "WIN") else "BH"
            sims[name] = simulate(codes, e, n_max, px, tax, mode)
            paths.append(pd.DataFrame({"cohort": y, "strategy": name, "day": np.arange(n_max), "value": sims[name][0]}))
        print(f"{y}: 신호일 {t.date()}, 진입 {days[e].date()}, 상위 10% {len(groups['EW'])}종목, 후보 {len(groups['ALL'])}종목, "
              f"추적 {n_max}거래일", flush=True)
        for h, n in H.items():
            if n > n_max:
                continue
            x = e + n - 1
            for name, (v, mw, to, _, _) in sims.items():
                val = v[:n]
                final = val[-1] - (val[-1]) * (rs.FEE + HALF_SPREAD + tax[x])  # 끝 날 전량 매도 비용(근사: 전액 기준)
                peak = np.maximum.accumulate(val)
                rows.append({"cohort": y, "horizon": h, "strategy": name, "total": final - 1,
                             "annual": final ** (250 / n) - 1, "mdd": (val / peak - 1).min(),
                             "max_weight": mw[n - 1], "n_stocks": len(groups[name])})
            for m in lidx:
                tot = np.expm1(lidx[m][x] - lidx[m][e - 1])
                rows.append({"cohort": y, "horizon": h, "strategy": m, "total": tot,
                             "annual": (1 + tot) ** (250 / n) - 1, "mdd": np.nan, "max_weight": np.nan, "n_stocks": np.nan})
            r = stock_bh(groups["EW"], e, x, px)
            stock_rows.append(pd.DataFrame({"cohort": y, "horizon": h, "code": r.index, "R": r.to_numpy()}))

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "cohort_results.csv", index=False, encoding="utf-8-sig")
    st = pd.concat(stock_rows)
    st["name"] = st["code"].map(names)
    st.to_csv(OUT / "cohort_stocks.csv", index=False, encoding="utf-8-sig")
    pd.concat(paths).to_parquet(OUT / "paths.parquet")

    piv = res.pivot_table(index=["horizon", "cohort"], columns="strategy", values="total")
    order = ["EW", "BH", "WIN", "ALL", "BOT", "KOSPI", "KOSDAQ"]
    summ = []
    for h in H:
        if h not in piv.index.get_level_values(0):
            continue
        p = piv.loc[h][order]
        for s in order:
            summ.append({"horizon": h, "strategy": s, "n_cohorts": p[s].notna().sum(), "mean": p[s].mean(),
                         "median": p[s].median(), "min": p[s].min(), "max": p[s].max(),
                         "beat_ALL": int((p[s] > p["ALL"]).sum()), "beat_KOSPI": int((p[s] > p["KOSPI"]).sum()),
                         "mdd_mean": res[(res.horizon == h) & (res.strategy == s)]["mdd"].mean()})
    summ = pd.DataFrame(summ)
    summ.to_csv(OUT / "summary.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    print("\n요약 (묶음별 총수익률, 비용 차감):")
    print(summ.round(3).to_string(index=False))
    print("\n묶음별 총수익률:")
    print(piv[order].round(3).to_string())
    sw = st.groupby(["horizon"]).agg(share_x2=("R", lambda r: (r >= 1).mean()), share_half=("R", lambda r: (r <= -.5).mean()))
    print("\n상위 10% 종목 단위(방치): 2배 이상·반토막 비율\n", sw.round(3).to_string())


if __name__ == "__main__":
    main()
