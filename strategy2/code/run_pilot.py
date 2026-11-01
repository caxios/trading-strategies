"""strategy2 연구계획서 5절 파일럿: 2019-01-01 ~ 2020-12-31, 50종목으로 4~10절 전체를 끝까지 실행한다.

목적은 파이프라인이 끝까지 돌고 데이터 문제가 드러나는지 보는 것이다(5절 3항: 수익률 수치는 해석하지 않는다).
8.4절 (2) 5% 공시 발생률은 계획 변경 기록(assumptions.md 7절)에 따라 모든 분석 뒤 참고 분석으로 따로 한다.

  strategy2/results/pilot/selection.csv          : 고른 50종목과 선정 사유
  strategy2/results/pilot/filter_counts_W*.csv   : 신호일별 필터 단계 종목 수 (11.2절 표 1)
  strategy2/results/pilot/scores_W*.csv          : 신호일 × 그룹 × 종목 지표·점수·미래 수익률
  strategy2/results/pilot/weekly_W*_H*.csv       : 분위·기준 시장의 주간 수익률, 회전율, 비용 재료
  strategy2/results/pilot/diagnostics.txt        : 단계별 실행 결과와 10절 점검 결과

사용 예:
    python strategy2/code/run_pilot.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research as rs  # noqa: E402

OUT = rs.ROOT / "strategy2" / "results" / "pilot"
START, END = "2019-01-01", "2020-12-31"
YEARS = [2017, 2018, 2019, 2020, 2021]   # 앞쪽 2년은 252일 모멘텀·60일 창, 2021 은 보유 기간 수익률용
TRANSFERS = ["036420", "003670", "192080", "068270", "097520"]  # 기간 중·인접 시장 이전 (ticker_mapping.csv)
SEED = 42
N_SHUFFLE = 100
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def select_pilot() -> pd.DataFrame:
    """5절 1항 기준: 2018-12-28 기준 KOSPI 대형 10, KOSPI 중소형 10, KOSDAQ 20, 기간 중 상폐 5, 이전상장 5."""
    m = rs.eligible_master()
    p = pd.read_parquet(rs.CLEAN / "panel_2018.parquet", columns=["date", "code", "market", "mktcap"])
    p = p[(p["date"] == p["date"].max()) & p["code"].isin(m.index)]
    rng = np.random.default_rng(SEED)
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


def attach_returns(sc: pd.DataFrame, bm: pd.DataFrame, eng: rs.Engine, lag: int = 1) -> pd.DataFrame:
    """7.1·7.2절: 종목별 R, 같은 신호일 기준 시장(유동성 통과 전체) 동일 가중 평균 R̄, 초과수익률."""
    R, Rbar = {}, {}
    for j, g in bm.groupby("j"):
        r = eng.stock_returns(j, g["code"], lag)
        Rbar[j] = r.mean()
        R.update({(j, c): v for c, v in r.items()})
    sc = sc.copy()
    sc["R"] = [R.get((j, c), np.nan) for j, c in zip(sc["j"], sc["code"])]
    sc["Rbar"] = sc["j"].map(Rbar)
    sc["Rex"] = sc["R"] - sc["Rbar"]
    return sc


def decile_cohorts(sc: pd.DataFrame, key: str = "score", nq: int = rs.NQ) -> dict:
    sc = sc.copy()
    sc["q"] = sc.groupby("date")[key].transform(lambda x: rs.qassign(x, nq))
    return {q: {j: g["code"].tolist() for j, g in d.groupby("j")} for q, d in sc.groupby("q")}, sc["q"]


def ls_mean(port: dict, nq: int = rs.NQ) -> float:
    return float((port[nq]["gross"] - port[1]["gross"]).mean())


MAIN_GROUPS = ("FOR", "INST")
# 주 설정에서만 함께 돌리는 보조 그룹: 숏커버링 필터 없는 FOR(8.5절), 연기금·투신 각각(2절 비고)
EXTRA_GROUPS = ("FOR_NOSC", "PENS", "IVTR")


def run(W: int, hold: int, wide, sectors, master, sigs, groups=MAIN_GROUPS) -> dict:
    log(f"\n===== W={W}, 보유 {hold}거래일 =====")
    lag_nw = max(rs.NW_LAG, hold // 5)
    ind = rs.indicators(wide, W, groups=tuple(g.removesuffix("_NOSC") for g in groups if g != "FOR_NOSC"))
    sc, bm, cnt = rs.cross_sections(wide, ind, master, sectors, sigs, W, groups=groups)
    cnt.to_csv(OUT / f"filter_counts_W{W}.csv", index=False, encoding="utf-8-sig")
    log("필터 단계별 종목 수 (신호일 평균):")
    log(cnt.drop(columns="date").mean().round(1).to_string())
    eng = rs.Engine(wide, hold)
    hs = rs.half_spread(wide)
    sc = attach_returns(sc, bm, eng)
    sig_pos = sorted(bm["j"].unique())
    log(f"신호일 {len(sigs)}개, 점수 행 {len(sc)}, R 결측 {sc['R'].isna().mean():.1%} (진입일 정지 또는 자료 끝)")
    log(f"반스프레드 분포(점수 행): 결측 {sc['hs'].isna().mean():.1%}, 분위 "
        f"{np.round(sc['hs'].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).values * 100, 3).tolist()}%")
    res, ports = {}, {}
    for g in groups:
        d = sc[sc["group"] == g].copy()
        if d.empty:
            log(f"[{g}] 점수 산출 신호일 없음")
            continue
        coh, d["q"] = decile_cohorts(d)
        coh["BM"] = {j: x["code"].tolist() for j, x in bm.groupby("j")}
        port = eng.portfolios(coh, sig_pos, hs=hs)
        wk = pd.DataFrame({"week": port["BM"]["week"]})
        for k, v in port.items():
            wk[f"{k}_gross"], wk[f"{k}_TO"], wk[f"{k}_hs"] = v["gross"], v["TO"], v["hs"]
        wk["tax"] = port["BM"]["tax"]
        wk.to_csv(OUT / f"weekly_W{W}_H{hold}_{g}.csv", index=False, encoding="utf-8-sig")
        ex = {q: port[q]["gross"] - port["BM"]["gross"] for q in range(1, rs.NQ + 1)}
        means = pd.Series({q: v.mean() for q, v in ex.items()})
        m_ls, t_ls, n_ls = rs.nw_t(port[rs.NQ]["gross"] - port[1]["gross"], lag_nw)
        net10 = rs.net_returns(port[rs.NQ])
        cost1 = port[1]["gross"] - rs.net_returns(port[1])
        ls_net = net10 - (port[1]["gross"] + cost1)  # 숏 쪽도 회전율만큼 비용을 낸다
        long_net_ex = net10 - port["BM"]["gross"]
        m_ln, t_ln, _ = rs.nw_t(long_net_ex, lag_nw)
        sens = {f"fee{f}_slip{s}": float((rs.net_returns(port[rs.NQ], f, s) - port["BM"]["gross"]).mean())
                for f in (rs.FEE, rs.FEE_HIGH) for s in (None, *rs.SLIP_FIXED)}
        log(f"[{g}] 주 {n_ls}개 | 분위 평균 주간 초과수익률(%) {np.round(means.values * 100, 3).tolist()}")
        log(f"[{g}] 10−1 평균 {m_ls:.4%} NW t {t_ls:.2f} | 스피어만 {rs.decile_monotonic(means):.2f} | "
            f"10분위 롱 비용 후 초과 {m_ln:.4%} t {t_ln:.2f} | 롱-숏 비용 후 {ls_net.mean():.4%}")
        log(f"[{g}] 10분위 주간 회전율 {port[rs.NQ]['TO'].mean():.3f}, 반스프레드 {port[rs.NQ]['hs'].mean():.4%}, "
            f"MDD 롱-숏 {rs.max_drawdown(port[rs.NQ]['gross'] - port[1]['gross']):.1%}")
        log(f"[{g}] 비용 민감도(10분위 롱 비용 후 초과 평균): " + ", ".join(f"{k}={v:.4%}" for k, v in sens.items()))
        r = {"ls": (m_ls, t_ls), "long_net": (m_ln, t_ln)}
        if hold == rs.HOLD and W == rs.W_MAIN and g in MAIN_GROUPS:
            r.update(validate(g, d, bm, eng, wide, sig_pos, hs, lag_nw))
        res[g], ports[g] = r, port
        sc.loc[d.index, "q"] = d["q"]
    sc.to_csv(OUT / f"scores_W{W}_H{hold}.csv", index=False, encoding="utf-8-sig")
    return {"sc": sc, "bm": bm, "res": res, "ports": ports, "eng": eng, "hs": hs, "sig_pos": sig_pos}


def short_cover_analysis(main: dict):
    """8.5절: 필터 없는 FOR와 비교, 필터로 제외된 종목의 성과, 공매도 금지 기간별 제외 비율."""
    log("\n===== 8.5절 숏커버링 필터 보조 분석 =====")
    sc, bm, eng, sig_pos = main["sc"], main["bm"], main["eng"], main["sig_pos"]
    f, nf = sc[sc["group"] == "FOR"], sc[sc["group"] == "FOR_NOSC"]
    for g in ("FOR", "FOR_NOSC"):
        m_ls, t_ls = main["res"][g]["ls"]
        m_ln, t_ln = main["res"][g]["long_net"]
        log(f"[{g}] 10−1 평균 {m_ls:.4%} NW t {t_ls:.2f} | 10분위 롱 비용 후 초과 {m_ln:.4%} t {t_ln:.2f}")
    kept = set(zip(f["j"], f["code"]))
    ex = nf[[(j, c) not in kept for j, c in zip(nf["j"], nf["code"])]].copy()
    log(f"제외된 (종목, 신호일) {len(ex)}쌍, 신호일당 평균 {len(ex) / nf['date'].nunique():.1f}종목")
    if ex.empty:
        return
    log(f"제외 종목 평균 초과수익률 {ex['Rex'].mean():.4%}, 시장을 이긴 비율 {(ex['Rex'] > 0).mean():.2f} "
        f"(필터 없는 FOR 전체 {nf['Rex'].mean():.4%} / {(nf['Rex'] > 0).mean():.2f}, "
        f"필터 없는 10분위 {nf.loc[nf['q'] == rs.NQ, 'Rex'].mean():.4%})")
    log("제외 종목의 필터 없는 FOR 점수 분위 분포: " + str(ex["q"].value_counts().sort_index().to_dict()))
    coh = {"SC": {j: g["code"].tolist() for j, g in ex.groupby("j")},
           "BM": {j: g["code"].tolist() for j, g in bm.groupby("j")}}
    port = eng.portfolios(coh, sig_pos, turnover=False)
    m, t, n = rs.nw_t(port["SC"]["gross"] - port["BM"]["gross"])
    log(f"제외 종목 포트폴리오 주간 초과수익률 평균 {m:.4%} NW t {t:.2f} (주 {n}, 제외 종목이 없는 날은 그 묶음이 비어 있음)")
    ban = pd.read_csv(rs.CLEAN / "ref" / "short_sale_ban.csv", parse_dates=["from", "to"])
    ban = ban[ban["regime"] == "전 종목 금지"]
    rate = (1 - f.groupby("date").size() / nf.groupby("date").size()).fillna(1.0)
    in_ban = pd.Series([((ban["from"] <= d) & (d <= ban["to"])).any() for d in rate.index], index=rate.index)
    log(f"제외 비율: 공매도 전면 금지 기간 {rate[in_ban].mean():.1%} (신호일 {in_ban.sum()}), "
        f"그 밖 {rate[~in_ban].mean():.1%} (신호일 {(~in_ban).sum()})")


def validate(g, d, bm, eng, wide, sig_pos, hs, lag_nw) -> dict:
    """8.2~8.4절과 10절 2·3번 점검 (주 설정 W=60, 보유 20일에서만)."""
    out = {}
    # 8.2 (1) 이중 정렬 5×5
    for ctrl in ("MOM", "SIZE"):
        x = d.dropna(subset=[ctrl]).copy()
        x = x[x.groupby("date")["code"].transform("size") >= 25]
        if x["date"].nunique() < 30:
            log(f"[{g}] 이중 정렬 {ctrl}: 25종목 이상인 신호일 {x['date'].nunique()}개 → 표본 부족으로 건너뜀")
            out[f"ds_{ctrl}"] = (np.nan, np.nan)
            continue
        x["cq"] = x.groupby("date")[ctrl].transform(lambda v: rs.qassign(v, 5))
        x["sq"] = x.groupby(["date", "cq"])["score"].transform(lambda v: rs.qassign(v, 5))
        coh = {(cq, sq): {j: y["code"].tolist() for j, y in z.groupby("j")} for (cq, sq), z in x.groupby(["cq", "sq"])}
        port = eng.portfolios(coh, sig_pos, turnover=False)
        diff = pd.concat([port[(c, 5)]["gross"] - port[(c, 1)]["gross"] for c in range(1, 6) if (c, 5) in port and (c, 1) in port], axis=1).mean(axis=1)
        m, t, n = rs.nw_t(diff, lag_nw)
        log(f"[{g}] 이중 정렬 {ctrl}: 점수5−1 평균 {m:.4%} NW t {t:.2f} (주 {n}, 칸당 평균 종목 {x.groupby(['date','cq','sq']).size().mean():.1f})")
        out[f"ds_{ctrl}"] = (m, t)
    # 8.2 (2) Fama–MacBeth
    fm, dropped = rs.fama_macbeth(d)
    m, t, n = rs.nw_t(fm["score"], lag_nw) if len(fm) else (np.nan, np.nan, 0)
    log(f"[{g}] Fama–MacBeth 점수 계수 평균 {m:.5f} NW t {t:.2f} (신호일 {n}, 업종 더미 뺀 신호일 {dropped})")
    out["fm"] = (m, t)
    # 8.4 (1) 적중률
    hit = d.dropna(subset=["Rex"]).groupby("q")["Rex"].apply(lambda v: (v > 0).mean())
    top = d.dropna(subset=["R"]).sort_values("score", ascending=False).groupby("date").head(20)
    basket = top.groupby("date").agg(R=("R", "mean"), Rbar=("Rbar", "first"), n=("code", "size"))
    log(f"[{g}] 적중률 분위별 {np.round(hit.values, 2).tolist()} | 상위 20 바구니 적중률 {(basket['R'] > basket['Rbar']).mean():.2f} "
        f"(바구니 평균 종목 {basket['n'].mean():.1f})")
    # 8.4 (3) 실적 발표 이벤트 [−1, +1] 누적 초과수익률
    ev = pd.read_csv(rs.CLEAN / "earnings_dates.csv", dtype=str)
    ev = ev[ev["code"].isin(d["code"].unique())]
    days = wide["exists"].index
    ev["pos"] = days.searchsorted(pd.to_datetime(ev["event_date"]))
    exr = (wide["ret"].fillna(0) - rs.market_ret(wide)).to_numpy()
    col = pd.Series(np.arange(wide["exists"].shape[1]), index=wide["exists"].columns)
    evp = ev.groupby("code")["pos"].apply(lambda s: np.sort(s.to_numpy()))
    cars = []
    for j, c in zip(d["j"], d["code"]):
        p = evp.get(c)
        nxt = p[(p > j) & (p <= j + rs.EVENT_DAYS)] if p is not None else []
        if len(nxt) and nxt[0] + 1 < len(days):
            e = nxt[0]
            cars.append(np.nansum(exr[e - 1:e + 2, col[c]]))
        else:
            cars.append(np.nan)
    d["ecar"] = cars
    ecar = d.groupby("q")["ecar"].agg(["mean", "count"])
    log(f"[{g}] 실적 발표 CAR[−1,+1] 분위별 평균(%) {np.round(ecar['mean'].values * 100, 2).tolist()} "
        f"(이벤트 있는 비율 {d['ecar'].notna().mean():.0%})")
    # 10절 2번 신호 지연: t+5 거래일 다음 날 시가 진입
    coh, _ = decile_cohorts(d)
    port_l = eng.portfolios(coh, sig_pos, lag=6, turnover=False)
    port_0 = eng.portfolios(coh, sig_pos, turnover=False)
    log(f"[{g}] 신호 지연 점검: 10−1 주간 평균 원래 {ls_mean(port_0):.4%} → 1주 지연 {ls_mean(port_l):.4%}")
    # 10절 3번 무작위 점수
    rng = np.random.default_rng(rs.NQ)
    sims = []
    for _ in range(N_SHUFFLE):
        s = d.copy()
        s["score"] = s.groupby("date")["score"].transform(lambda v: rng.permutation(v.to_numpy()))
        coh_s, _ = decile_cohorts(s)
        sims.append(ls_mean(eng.portfolios(coh_s, sig_pos, turnover=False)))
    sims = np.array(sims)
    actual = ls_mean(port_0)
    log(f"[{g}] 무작위 점수 {N_SHUFFLE}회: 10−1 평균의 평균 {sims.mean():.4%}, 표준편차 {sims.std():.4%}, "
        f"실제값 백분위 {(sims < actual).mean():.0%}")
    out["shuffle"] = (sims.mean(), sims.std())
    return out


def leakage_check(wide, sectors, master, sigs, full_sc, W):
    """10절 4번: 신호일 뒤 행을 모두 지운 자료로 다시 계산해도 그날 점수가 같아야 한다."""
    rng = np.random.default_rng(SEED)
    days = wide["exists"].index
    for t in sorted(rng.choice(sigs, 3, replace=False)):
        j = days.get_loc(t)
        cut = {k: v.iloc[:j + 1] for k, v in wide.items()}
        sc, _, _ = rs.cross_sections(cut, rs.indicators(cut, W), master, sectors, [t], W, groups=MAIN_GROUPS)
        full_t = full_sc[full_sc["group"].isin(MAIN_GROUPS)]
        a = full_t[full_t["date"] == t].set_index(["group", "code"])["score"].sort_index()
        b = sc.set_index(["group", "code"])["score"].sort_index()
        ok = a.index.equals(b.index) and np.allclose(a, b)
        log(f"미래 자료 차단 점검 {t.date()}: 종목 {len(a)} 일치 {ok}")
        assert ok, f"{t} 점수가 신호일 이후 자료에 의존함"


def engine_check(main: dict, codes: list[str]):
    """7절 수익률 엔진 손계산 대조. Engine 은 일간 수익률(ret)을 복리로 쌓지만, 여기서는 패널의 수정 시가·종가
    수준만으로 직접 계산한다: 보유 중 그날 가격 = 진입일 이후 마지막으로 거래된 수정 종가."""
    log("\n===== 수익률 엔진 손계산 대조 =====")
    p = pd.concat([pd.read_parquet(rs.CLEAN / f"panel_{y}.parquet", columns=["date", "code", "adj_open", "adj_close"])
                   for y in YEARS])
    p = p[p["code"].isin(codes)]
    eng, sc, sig_pos, h = main["eng"], main["sc"], main["sig_pos"], rs.HOLD
    o = p.pivot(index="date", columns="code", values="adj_open").reindex(eng.days)
    c = p.pivot(index="date", columns="code", values="adj_close").reindex(eng.days)

    def value(j, code, d):
        """신호일 j 묶음에서 종목 1원어치의 d일 종가 기준 가치 (진입 시가 = 1)."""
        e = j + 1
        return c[code].iloc[e:d + 1].ffill().iloc[-1] / o[code].iloc[e]

    # (1) 종목 수익률 R = Close_{t+20} / Open_{t+1} − 1
    f = sc[(sc["group"] == "FOR") & sc["R"].notna()]
    man = np.array([value(j, code, j + h) - 1 for j, code in zip(f["j"], f["code"])])
    log(f"(1) 종목 수익률 {len(f)}건: 최대 절대 차이 {np.abs(man - f['R'].to_numpy()).max():.2e}")

    # (2) 10분위 Jegadeesh–Titman 주간 수익률, (3) 회전율
    d = f[f["q"] == rs.NQ]
    coh = {j: g["code"].tolist() for j, g in d.groupby("j")}
    port = main["ports"]["FOR"][rs.NQ].set_index("week")
    rng = np.random.default_rng(SEED)
    weeks = [(a, b) for a, b in zip(sig_pos[:-1], sig_pos[1:]) if eng.days[a] in port.index]
    diffs_r, diffs_to = [], []
    for a, b in [weeks[i] for i in sorted(rng.choice(len(weeks), 5, replace=False))]:
        r = 1.0
        for day in range(a + 1, b + 1):
            act = [j for j in coh if j + 1 <= day <= j + h]
            daily = []
            for j in act:
                vals = [value(j, code, day) for code in coh[j]]
                prev = [value(j, code, day - 1) if day > j + 1 else 1.0 for code in coh[j]]
                daily.append(np.mean(vals) / np.mean(prev) - 1)
            r *= 1 + np.mean(daily)
        diffs_r.append(abs((r - 1) - port.loc[eng.days[a], "gross"]))
        e = a + 1  # 새 묶음 진입일

        def weights(day):
            act = [j for j in coh if j + 1 <= day <= j + h]
            w = {}
            for j in act:
                v = {code: (value(j, code, e - 1) if j + 1 < e else 1.0) for code in coh[j]}
                tot = sum(v.values())
                for code, x in v.items():
                    w[code] = w.get(code, 0) + x / tot / len(act)
            return w
        before, after = weights(e - 1), weights(e)
        to = sum(max(0.0, after.get(k, 0) - before.get(k, 0)) for k in set(before) | set(after))
        diffs_to.append(abs(to - port.loc[eng.days[a], "TO"]))
    log(f"(2) 10분위 주간 수익률 5주: 최대 절대 차이 {max(diffs_r):.2e}")
    log(f"(3) 10분위 주간 회전율 5주: 최대 절대 차이 {max(diffs_to):.2e}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sel = select_pilot()
    sel.to_csv(OUT / "selection.csv", index=False, encoding="utf-8-sig")
    log("선정 종목:", sel.groupby("reason").size().to_dict())
    master = rs.eligible_master().loc[sel["code"]]
    wide, sectors = rs.load_wide(YEARS, sel["code"].tolist())
    log(f"행렬 {wide['exists'].shape}, 기간 {wide['exists'].index[0].date()} ~ {wide['exists'].index[-1].date()}")
    sigs = rs.signal_days(rs.calendar().index, START, END)

    # 데이터 점검: 시가 0 인데 거래가 있는 날, 결측 비율
    tr = wide["halted"] == 0
    log(f"거래일인데 수정 시가 결측: {int((tr & wide['adj_open'].isna()).sum().sum())}건, "
        f"거래일 순매수(FOR) 결측: {int((tr & wide['FOR_net'].isna()).sum().sum())}건 / {int(tr.sum().sum())}")

    main_run = run(rs.W_MAIN, rs.HOLD, wide, sectors, master, sigs, MAIN_GROUPS + EXTRA_GROUPS)
    short_cover_analysis(main_run)
    engine_check(main_run, sel["code"].tolist())
    leakage_check(wide, sectors, master, sigs, main_run["sc"], rs.W_MAIN)
    # 10절 5번 생존편향: 유니버스(기준 시장)에 든 상폐 종목 수
    bm = main_run["bm"]
    dl = set(master.index[master["delisted"] == "True"])
    log("기준 시장에 포함된 상폐 종목 수(연도별):",
        bm[bm["code"].isin(dl)].groupby(bm["date"].dt.year)["code"].nunique().to_dict())
    # 11.2절 표 7 강건성: W=20, 보유 60일, KOSPI/KOSDAQ 분리
    run(20, rs.HOLD, wide, sectors, master, sigs)
    run(rs.W_MAIN, 60, wide, sectors, master, sigs)
    eng = rs.Engine(wide, rs.HOLD)
    sc = main_run["sc"]
    for mk, name in ((0, "KOSPI"), (1, "KOSDAQ")):
        for g in ("FOR", "INST"):
            d = sc[(sc["group"] == g) & (sc["kosdaq"] == mk)]
            d = d[d.groupby("date")["code"].transform("size") >= rs.NQ]
            if d["date"].nunique() < 30:
                log(f"[{g}] {name} 분리: 신호일당 {rs.NQ}종목 이상인 신호일 {d['date'].nunique()}개 → 표본 부족으로 건너뜀")
                continue
            coh, _ = decile_cohorts(d)
            port = eng.portfolios(coh, sorted(bm["j"].unique()), turnover=False)
            log(f"[{g}] {name} 분리: 신호일 {d['date'].nunique()}, 10−1 주간 평균 {ls_mean(port):.4%}")
    (OUT / "diagnostics.txt").write_text("\n".join(LOG), encoding="utf-8")


if __name__ == "__main__":
    main()
