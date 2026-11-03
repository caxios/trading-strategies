"""strategy2 연구계획서 7~10절 분석 실행 함수. run_pilot.py(5절)와 run_design.py(설계 확인 구간)가 같이 쓴다.

setup() 으로 결과 폴더와 읽을 연도를 정한 뒤 analyze() 를 부른다. 수익률은 7.3절(2026-11-03 변경)대로
신호일 단위 h거래일 수익률이고, 보유 기간은 20(9절 판정 기준)·60(보고)이다.

  <OUT>/filter_counts_W*.csv        : 신호일별 필터 단계 종목 수 (11.2절 표 1)
  <OUT>/indicator_stats_W*.csv      : 그룹별 지표 분포와 지표 간 순위상관 (11.2절 표 1)
  <OUT>/deciles_*_W*_H*.csv         : 분위별 평균 초과수익률·비용 후·적중률·변동성·지수 대비 (11.2절 표 2)
  <OUT>/signal_deciles_*_W*_H*.csv  : 신호일 × 분위 수익률과 왕복 비용
  <OUT>/scores_W*_H*.parquet        : 신호일 × 그룹 × 종목 지표·점수·미래 수익률·분위
  <OUT>/figures/*.png               : 11.3절 그림
  <OUT>/diagnostics.txt             : 단계별 실행 결과와 10절 점검 결과
"""
from pathlib import Path

import numpy as np
import pandas as pd

import research as rs

OUT: Path = rs.ROOT / "strategy2" / "results"
YEARS: list[int] = []
LOG: list[str] = []
HOLDS = (20, 60)                      # 2절: 20거래일 = 9절 판정 기준, 60거래일 = 보고용
MAIN_GROUPS = ("FOR", "INST")
# 주 설정에서 함께 돌리는 보조 그룹: 숏커버링 필터 없는 FOR(8.5절), 연기금 단독(2절 비고)
EXTRA_GROUPS = ("FOR_NOSC", "PENS")
SEED = 42
N_SHUFFLE = 100
MIN_SIGNALS = 30                      # 이중 정렬·시장 분리를 추정할 최소 신호일 수
DELAY_ALARM = 0.04                    # 10절 2번: 20거래일 롱-숏 평균이 이보다 크면 미래 정보 누출 의심
N_ENGINE_CHECK = 3000                 # 손계산 대조 표본 수


def setup(out: Path, years: list[int]):
    global OUT, YEARS
    OUT, YEARS = out, years
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    LOG.clear()


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def save_log():
    (OUT / "diagnostics.txt").write_text("\n".join(LOG), encoding="utf-8")


def lag_of(hold: int) -> int:
    """7.3절 Newey–West 시차 = h/5 (20일 → 4, 60일 → 12)."""
    return hold // 5


def stock_rex(sc: pd.DataFrame, bm: pd.DataFrame, eng: rs.Engine, lag: int = 1) -> pd.DataFrame:
    """7.1·7.2절: 종목별 R, 같은 신호일 기준 시장(유동성 통과 전체) 동일 가중 평균 R̄, 초과수익률, 매도 세율,
    그리고 보조 지표인 시장 지수 대비 초과수익률(지수는 종가만 있어 신호일 종가 → 보유 마지막 날 종가로 근사)."""
    idx = rs.calendar().reindex(eng.days)
    cum = {m: np.log1p(idx[m].fillna(0)).cumsum().to_numpy() for m in ("KOSPI", "KOSDAQ")}
    R, Rbar = {}, {}
    for j, g in bm.groupby("j"):
        r = eng.stock_returns(j, g["code"], lag)
        Rbar[j] = r.mean() if len(r) else np.nan
        R.update({(j, c): v for c, v in r.items()})
    out = pd.DataFrame(index=sc.index)
    out["R"] = [R.get((j, c), np.nan) for j, c in zip(sc["j"], sc["code"])]
    out["Rbar"] = sc["j"].map(Rbar).to_numpy()
    out["Rex"] = out["R"] - out["Rbar"]
    last = sc["j"] + lag + eng.hold - 1
    ok = last < len(eng.days)
    out["tax"] = np.where(ok, [eng.sale_tax(j, lag) if o else np.nan for j, o in zip(sc["j"], ok)], np.nan)
    lastc = last.clip(upper=len(eng.days) - 1).to_numpy()
    mret = np.where(sc["kosdaq"].to_numpy() == 1,
                    np.exp(cum["KOSDAQ"][lastc] - cum["KOSDAQ"][sc["j"].to_numpy()]),
                    np.exp(cum["KOSPI"][lastc] - cum["KOSPI"][sc["j"].to_numpy()])) - 1
    out["Rex_idx"] = np.where(ok, out["R"] - mret, np.nan)
    return out


def add_deciles(d: pd.DataFrame, key: str = "score", nq: int = rs.NQ) -> pd.Series:
    return d.groupby("date")[key].transform(lambda x: rs.qassign(x, nq))


def ls_series(tab: pd.DataFrame, col: str = "Rex", hi=rs.NQ, lo=1) -> pd.Series:
    """신호일별 상위 − 하위 분위 차이 D_t."""
    w = tab[col].unstack()
    return w[hi] - w[lo]


def summarize(g: str, d: pd.DataFrame, hold: int, tag: str) -> dict:
    """8.1절(분위 평균, 10−1, 단조성)과 8.3절(비용 차감 후, 민감도), 8.4절 (1) 적중률, 11.2절 표 2."""
    lag = lag_of(hold)
    tab = rs.signal_returns(d, "q")
    w = tab.unstack()
    means = w["Rex"].mean()
    m_ls, t_ls, n = rs.nw_t(ls_series(tab), lag)
    net_ex = w["Rex"] - w["cost"]
    ls_net = net_ex[rs.NQ] - (w["Rex"][1] + w["cost"][1])     # 숏 쪽도 왕복 비용을 낸다
    m_ln, t_ln, _ = rs.nw_t(net_ex[rs.NQ], lag)
    m_lsn, t_lsn, _ = rs.nw_t(ls_net, lag)
    idx_ex = d.dropna(subset=["R"]).groupby(["date", "q"])["Rex_idx"].mean().unstack()
    hit = d.dropna(subset=["Rex"]).groupby("q")["Rex"].apply(lambda v: (v > 0).mean())
    table = pd.DataFrame({
        "초과수익률_비용전": means, "초과수익률_비용후": net_ex.mean(), "신호일간_표준편차": w["Rex"].std(),
        "적중률": hit, "지수대비_초과수익률": idx_ex.mean(), "평균_종목수": w["n"].mean(), "평균_왕복비용": w["cost"].mean()})
    table.to_csv(OUT / f"deciles_{g}_{tag}.csv", encoding="utf-8-sig")
    tab.to_csv(OUT / f"signal_deciles_{g}_{tag}.csv", encoding="utf-8-sig")
    sens = {}
    for fee in (rs.FEE, rs.FEE_HIGH):
        for slip in (None, *rs.SLIP_FIXED):
            t = rs.signal_returns(d, "q", fee, slip).unstack()
            sens[f"수수료 {fee:.3%}, 슬리피지 {'AR' if slip is None else f'{slip:.1%}'}"] = \
                rs.nw_t(t["Rex"][rs.NQ] - t["cost"][rs.NQ], lag)[:2]
    curve = rs.nonoverlap_curve(ls_series(tab), hold // 5)
    log(f"[{g}] 신호일 {n} | 분위 평균 {hold}일 초과수익률(%) {np.round(means.values * 100, 2).tolist()}")
    log(f"[{g}] 10−1 평균 {m_ls:.3%} NW t {t_ls:.2f} (시차 {lag}) | 스피어만 {rs.decile_monotonic(means):.2f} | "
        f"10분위 롱 비용 후 초과 {m_ln:.3%} t {t_ln:.2f} | 롱-숏 비용 후 {m_lsn:.3%} t {t_lsn:.2f} | "
        f"10분위 평균 왕복 비용 {w['cost'][rs.NQ].mean():.3%} | 롱-숏 MDD(겹치지 않는 곡선) {rs.max_drawdown(curve):.1%}")
    log(f"[{g}] 적중률 분위별 {np.round(hit.values, 3).tolist()} | 10분위 지수 대비 초과 {idx_ex[rs.NQ].mean():.3%}")
    log(f"[{g}] 비용 민감도(10분위 롱 비용 후 초과 평균, t): "
        + ", ".join(f"{k} = {v[0]:.3%} ({v[1]:.2f})" for k, v in sens.items()))
    return {"tab": tab, "ls": (m_ls, t_ls, n), "long_net": (m_ln, t_ln), "ls_net": (m_lsn, t_lsn),
            "means": means, "table": table, "sens": sens}


def validate(g: str, d: pd.DataFrame, wide: dict, hold: int) -> dict:
    """8.2·8.4절과 10절 2·3번 점검. d 에는 1주 지연 진입 수익률 Rex_delay 열이 있어야 한다."""
    lag = lag_of(hold)
    out = {}
    # 8.2 (1) 이중 정렬 5×5
    for ctrl in ("MOM", "SIZE"):
        x = d.dropna(subset=[ctrl, "R"]).copy()
        x = x[x.groupby("date")["code"].transform("size") >= 25]
        if x["date"].nunique() < MIN_SIGNALS:
            log(f"[{g}] 이중 정렬 {ctrl}: 25종목 이상인 신호일 {x['date'].nunique()}개 → 표본 부족으로 건너뜀")
            continue
        x["cq"] = x.groupby("date")[ctrl].transform(lambda v: rs.qassign(v, 5))
        x["sq"] = x.groupby(["date", "cq"])["score"].transform(lambda v: rs.qassign(v, 5))
        cell = x.groupby(["date", "cq", "sq"])["Rex"].mean().unstack()
        diff_by_c = (cell[5] - cell[1]).unstack()
        diff = diff_by_c.mean(axis=1)
        m, t, n = rs.nw_t(diff, lag)
        out[f"ds_{ctrl}"] = (m, t, n, diff_by_c.mean())
        log(f"[{g}] 이중 정렬 {ctrl}: 점수 5−1 평균 {m:.3%} NW t {t:.2f} (신호일 {n}) | 통제 분위별 "
            f"{np.round(diff_by_c.mean().values * 100, 2).tolist()}%")
    # 8.2 (2) Fama–MacBeth
    fm, dropped = rs.fama_macbeth(d)
    m, t, n = rs.nw_t(fm["score"], lag) if len(fm) else (np.nan, np.nan, 0)
    out["fm"] = (m, t, n)
    ctrl_t = {v: rs.nw_t(fm[v], lag)[1] for v in ("MOM", "REV", "SIZE", "TURN")} if len(fm) else {}
    log(f"[{g}] Fama–MacBeth 점수 계수 평균 {m:.5f} NW t {t:.2f} (신호일 {n}, 업종 더미 뺀 신호일 {dropped}) | "
        "통제 변수 t " + ", ".join(f"{k} {v:.2f}" for k, v in ctrl_t.items()))
    # 8.4 (1) 상위 20 바구니
    top = d.dropna(subset=["R"]).sort_values("score", ascending=False).groupby("date").head(20)
    basket = top.groupby("date").agg(R=("R", "mean"), Rbar=("Rbar", "first"), n=("code", "size"))
    out["basket_hit"] = float((basket["R"] > basket["Rbar"]).mean())
    log(f"[{g}] 상위 20 바구니 적중률 {out['basket_hit']:.3f} (신호일 {len(basket)}), "
        f"바구니 평균 초과수익률 {(basket['R'] - basket['Rbar']).mean():.3%}")
    # 8.4 (3) 실적 발표 이벤트 [−1, +1] 누적 초과수익률 (보유 기간과 무관하므로 20일에서만)
    if hold == rs.HOLD:
        ev = pd.read_csv(rs.CLEAN / "earnings_dates.csv", dtype=str)
        ev = ev[ev["code"].isin(d["code"].unique())]
        days = wide["exists"].index
        ev["pos"] = days.searchsorted(pd.to_datetime(ev["event_date"]))
        exr = (wide["ret"].fillna(0) - rs.market_ret(wide)).to_numpy(dtype="float64")
        col = pd.Series(np.arange(wide["exists"].shape[1]), index=wide["exists"].columns)
        evp = ev.groupby("code")["pos"].apply(lambda s: np.sort(s.to_numpy()))
        cars = np.full(len(d), np.nan)
        for k, (j, c) in enumerate(zip(d["j"].to_numpy(), d["code"].to_numpy())):
            p = evp.get(c)
            if p is None:
                continue
            i = np.searchsorted(p, j, side="right")
            if i < len(p) and p[i] <= j + rs.EVENT_DAYS and p[i] + 1 < len(days):
                cars[k] = np.nansum(exr[p[i] - 1:p[i] + 2, col[c]])
        del exr
        ecar = pd.Series(cars, index=d.index).groupby(d["q"]).agg(["mean", "count"])
        diff = pd.Series(cars, index=d.index)[d["q"] == rs.NQ].mean() - pd.Series(cars, index=d.index)[d["q"] == 1].mean()
        by_sig = pd.DataFrame({"car": cars, "q": d["q"].to_numpy(), "date": d["date"].to_numpy()})
        sig_diff = by_sig.groupby(["date", "q"])["car"].mean().unstack()
        m, t, n = rs.nw_t(sig_diff[rs.NQ] - sig_diff[1], lag)
        out["ecar"] = (ecar, m, t)
        log(f"[{g}] 실적 발표 CAR[−1,+1] 분위별 평균(%) {np.round(ecar['mean'].values * 100, 3).tolist()} "
            f"(이벤트 있는 비율 {np.mean(~np.isnan(cars)):.0%}) | 10−1 신호일 평균 {m:.3%} NW t {t:.2f}")
        ecar.to_csv(OUT / f"earnings_car_{g}.csv", encoding="utf-8-sig")
    # 10절 2번 신호 지연: t+5 거래일 다음 날 시가 진입
    orig = ls_series(rs.signal_returns(d, "q")).mean()
    late = ls_series(rs.signal_returns(d.assign(Rex=d["Rex_delay"], R=d["R_delay"]), "q")).mean()
    out["delay"] = (orig, late)
    alarm = " ← 기준(20일 4%) 초과, 원인 확인 필요" if hold == rs.HOLD and abs(orig) >= DELAY_ALARM else ""
    log(f"[{g}] 신호 지연 점검: 10−1 평균 원래 {orig:.3%} → 1주 지연 {late:.3%}{alarm}")
    # 10절 3번 무작위 점수: 같은 신호일 안에서 점수를 섞는다
    rng = np.random.default_rng(rs.NQ)
    base = d[["date", "score", "R", "Rex", "hs", "tax", "code"]].dropna(subset=["R"]).copy()
    sims = []
    for _ in range(N_SHUFFLE):
        base["score_s"] = base.groupby("date")["score"].transform(lambda v: rng.permutation(v.to_numpy()))
        base["q"] = add_deciles(base, "score_s")
        sims.append(ls_series(rs.signal_returns(base, "q")).mean())
    sims = np.array(sims)
    out["shuffle"] = (sims, orig)
    log(f"[{g}] 무작위 점수 {N_SHUFFLE}회: 10−1 평균의 평균 {sims.mean():.3%}, 표준편차 {sims.std():.3%}, "
        f"실제값 백분위 {(sims < orig).mean():.0%}")
    return out


def describe_indicators(sc: pd.DataFrame, W: int):
    """11.2절 표 1: 그룹별 지표 분포와 지표 간 스피어만 상관(신호일별 상관의 평균)."""
    rows = []
    for g, d in sc.groupby("group"):
        desc = d[["C", "P", "S", "Stilde", "CAR", "score"]].describe(percentiles=[0.01, 0.25, 0.5, 0.75, 0.99]).T
        desc.insert(0, "group", g)
        rows.append(desc)
        corr = d.groupby("date")[["C", "P", "Stilde", "CAR"]].corr(method="spearman").groupby(level=1).mean()
        corr = corr.loc[["C", "P", "Stilde", "CAR"], ["C", "P", "Stilde", "CAR"]]
        corr.to_csv(OUT / f"indicator_corr_{g}_W{W}.csv", encoding="utf-8-sig")
        log(f"[{g}] 지표 간 순위상관(신호일 평균): C–P {corr.loc['C', 'P']:.2f}, C–S̃ {corr.loc['C', 'Stilde']:.2f}, "
            f"P–S̃ {corr.loc['P', 'Stilde']:.2f}, C–CAR {corr.loc['C', 'CAR']:.2f}, P–CAR {corr.loc['P', 'CAR']:.2f}, "
            f"S̃–CAR {corr.loc['Stilde', 'CAR']:.2f}")
    pd.concat(rows).to_csv(OUT / f"indicator_stats_W{W}.csv", encoding="utf-8-sig")


def short_cover_analysis(sc: pd.DataFrame, res: dict, hold: int):
    """8.5절: 필터 없는 FOR와 비교, 필터로 제외된 종목의 성과, 공매도 금지 기간별 제외 비율."""
    log(f"\n----- 8.5절 숏커버링 필터 보조 분석 (보유 {hold}거래일) -----")
    f, nf = sc[sc["group"] == "FOR"], sc[sc["group"] == "FOR_NOSC"]
    for g in ("FOR", "FOR_NOSC"):
        (m_ls, t_ls, _), (m_ln, t_ln) = res[g]["ls"], res[g]["long_net"]
        log(f"[{g}] 10−1 평균 {m_ls:.3%} NW t {t_ls:.2f} | 10분위 롱 비용 후 초과 {m_ln:.3%} t {t_ln:.2f}")
    kept = pd.MultiIndex.from_arrays([f["j"], f["code"]])
    ex = nf[~pd.MultiIndex.from_arrays([nf["j"], nf["code"]]).isin(kept)].dropna(subset=["Rex"])
    log(f"제외된 (종목, 신호일) {len(ex)}쌍, 신호일당 평균 {len(ex) / nf['date'].nunique():.1f}종목")
    if ex.empty:
        return
    log(f"제외 종목 평균 초과수익률 {ex['Rex'].mean():.3%}, 시장을 이긴 비율 {(ex['Rex'] > 0).mean():.3f} "
        f"(필터 없는 FOR 전체 {nf['Rex'].mean():.3%} / {(nf['Rex'] > 0).mean():.3f}, "
        f"필터 없는 10분위 {nf.loc[nf['q'] == rs.NQ, 'Rex'].mean():.3%})")
    dist = ex["q"].value_counts(normalize=True).sort_index()
    log("제외 종목의 필터 없는 FOR 점수 분위 분포(비율): " + str({int(k): round(v, 3) for k, v in dist.items()}))
    m, t, n = rs.nw_t(ex.groupby("date")["Rex"].mean(), lag_of(hold))
    log(f"제외 종목 신호일 단위 초과수익률 평균 {m:.3%} NW t {t:.2f} (제외 종목이 있는 신호일 {n})")
    ban = pd.read_csv(rs.CLEAN / "ref" / "short_sale_ban.csv", parse_dates=["from", "to"])
    ban = ban[ban["regime"] == "전 종목 금지"]
    rate = (1 - f.groupby("date").size() / nf.groupby("date").size()).fillna(1.0)
    in_ban = pd.Series([((ban["from"] <= d) & (d <= ban["to"])).any() for d in rate.index], index=rate.index)
    log(f"제외 비율: 공매도 전면 금지 기간 {rate[in_ban].mean():.1%} (신호일 {in_ban.sum()}), "
        f"그 밖 {rate[~in_ban].mean():.1%} (신호일 {(~in_ban).sum()})")


def engine_check(sc: pd.DataFrame, codes, hold: int):
    """7.1절 종목 수익률 손계산 대조(무작위 표본). 엔진은 일간 수익률(ret)을 복리로 쌓지만, 여기서는 패널의
    수정 시가·종가 수준만으로 직접 계산한다: 보유 마지막 날 가격 = 진입일 이후 마지막으로 거래된 수정 종가."""
    f = sc[sc["R"].notna()].drop_duplicates(["j", "code"])
    f = f.sample(min(N_ENGINE_CHECK, len(f)), random_state=SEED)
    need = set(f["code"])
    p = pd.concat([pd.read_parquet(rs.CLEAN / f"panel_{y}.parquet", columns=["date", "code", "adj_open", "adj_close"],
                                   filters=[("code", "in", list(need))]) for y in YEARS])
    days = rs.calendar().index
    days = days[(days >= p["date"].min()) & (days <= p["date"].max())]
    o = p.pivot(index="date", columns="code", values="adj_open").reindex(days)
    c = p.pivot(index="date", columns="code", values="adj_close").reindex(days)
    man = np.array([c[code].iloc[j + 1:j + 1 + hold].ffill().iloc[-1] / o[code].iloc[j + 1] - 1
                    for j, code in zip(f["j"], f["code"])])
    log(f"수익률 엔진 손계산 대조 (보유 {hold}거래일): 무작위 {len(f)}건, 최대 절대 차이 "
        f"{np.abs(man - f['R'].to_numpy()).max():.2e}")


def leakage_check(wide, sectors, master, sigs, full_sc, W):
    """10절 4번: 신호일 뒤 행을 모두 지운 자료로 다시 계산해도 그날 점수가 같아야 한다."""
    rng = np.random.default_rng(SEED)
    days = wide["exists"].index
    full_t = full_sc[full_sc["group"].isin(MAIN_GROUPS)]
    for t in sorted(rng.choice(sigs, 3, replace=False)):
        j = days.get_loc(t)
        cut = {k: v.iloc[:j + 1] for k, v in wide.items()}
        sc, _, _ = rs.cross_sections(cut, rs.indicators(cut, W, rows=[t]), master, sectors, [t], W, groups=MAIN_GROUPS)
        del cut
        a = full_t[full_t["date"] == t].set_index(["group", "code"])["score"].sort_index()
        b = sc.set_index(["group", "code"])["score"].sort_index()
        ok = a.index.equals(b.index) and np.allclose(a, b)
        log(f"미래 자료 차단 점검 {t.date()}: 종목 {len(a)} 일치 {ok}")
        assert ok, f"{t} 점수가 신호일 이후 자료에 의존함"


def market_split(sc: pd.DataFrame, hold: int):
    """11.2절 표 7: KOSPI·KOSDAQ 따로 10분위."""
    for mk, name in ((0, "KOSPI"), (1, "KOSDAQ")):
        for g in MAIN_GROUPS:
            d = sc[(sc["group"] == g) & (sc["kosdaq"] == mk)].copy()
            d = d[d.groupby("date")["code"].transform("size") >= rs.NQ]
            if d["date"].nunique() < MIN_SIGNALS:
                log(f"[{g}] {name} 분리: {rs.NQ}종목 이상인 신호일 {d['date'].nunique()}개 → 표본 부족으로 건너뜀")
                continue
            d["q"] = add_deciles(d)
            tab = rs.signal_returns(d, "q")
            m, t, n = rs.nw_t(ls_series(tab), lag_of(hold))
            m10, t10, _ = rs.nw_t(tab["Rex"].unstack()[rs.NQ] - tab["cost"].unstack()[rs.NQ], lag_of(hold))
            log(f"[{g}] {name} 분리: 신호일 {n}, 신호일당 평균 {d.groupby('date').size().mean():.0f}종목, "
                f"10−1 평균 {m:.3%} NW t {t:.2f}, 10분위 롱 비용 후 초과 {m10:.3%} t {t10:.2f}")


def figures(results: dict):
    """11.3절 그림 1~4."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    for hold, res in results.items():
        # 그림 1: 분위별 평균 초과수익률
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
        for ax, g in zip(axes, MAIN_GROUPS):
            t = res[g]["table"]
            ax.bar(t.index - 0.2, t["초과수익률_비용전"] * 100, 0.4, label="비용 전", color="#4C72B0")
            ax.bar(t.index + 0.2, t["초과수익률_비용후"] * 100, 0.4, label="비용 후", color="#DD8452")
            ax.axhline(0, color="k", lw=0.8)
            ax.set_title(f"{g}: 점수 분위별 평균 {hold}거래일 초과수익률")
            ax.set_xlabel("점수 분위 (10 = 상위)")
            ax.set_xticks(range(1, rs.NQ + 1))
        axes[0].set_ylabel("%")
        axes[0].legend()
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"fig1_deciles_H{hold}.png", dpi=130)
        plt.close(fig)
        # 그림 2: 10분위, 1분위, 기준 시장의 누적 수익률 (겹치지 않는 신호일, 비용 전·후)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        for ax, g in zip(axes, MAIN_GROUPS):
            w = res[g]["tab"].unstack()
            step = hold // 5
            for q, color in ((rs.NQ, "#C44E52"), (1, "#4C72B0")):
                ax.plot(rs.nonoverlap_curve(w["R"][q], step), color=color, label=f"{q}분위 비용 전")
                ax.plot(rs.nonoverlap_curve(w["R"][q] - w["cost"][q], step), color=color, ls="--",
                        label=f"{q}분위 비용 후")
            rbar = (w["R"][rs.NQ] - w["Rex"][rs.NQ])
            ax.plot(rs.nonoverlap_curve(rbar, step), color="k", label="기준 시장(동일 가중)")
            ax.set_yscale("log")
            ax.set_title(f"{g}: 누적 가치 ({hold}거래일 보유, 겹치지 않는 신호일)")
            ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"fig2_cumulative_H{hold}.png", dpi=130)
        plt.close(fig)
        # 그림 3: 이중 정렬
        if all(f"ds_{c}" in res[g].get("val", {}) for g in MAIN_GROUPS for c in ("MOM", "SIZE")):
            fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
            for ax, ctrl in zip(axes, ("MOM", "SIZE")):
                for k, g in enumerate(MAIN_GROUPS):
                    v = res[g]["val"][f"ds_{ctrl}"][3]
                    ax.bar(v.index + (k - 0.5) * 0.4, v.values * 100, 0.4, label=g)
                ax.axhline(0, color="k", lw=0.8)
                ax.set_title(f"{ctrl} 5분위 안에서 점수 5−1 차이 ({hold}거래일)")
                ax.set_xlabel(f"{ctrl} 분위 (1 = 낮음)")
            axes[0].set_ylabel("%")
            axes[0].legend()
            fig.tight_layout()
            fig.savefig(OUT / "figures" / f"fig3_double_sort_H{hold}.png", dpi=130)
            plt.close(fig)
        # 그림 4: 무작위 점수 분포와 실제값
        if all("shuffle" in res[g].get("val", {}) for g in MAIN_GROUPS):
            fig, axes = plt.subplots(1, 2, figsize=(11, 4))
            for ax, g in zip(axes, MAIN_GROUPS):
                sims, actual = res[g]["val"]["shuffle"]
                ax.hist(sims * 100, bins=20, color="#8C8C8C")
                ax.axvline(actual * 100, color="#C44E52", lw=2, label="실제 점수")
                ax.set_title(f"{g}: 무작위 점수 {N_SHUFFLE}회의 10−1 평균 ({hold}거래일)")
                ax.set_xlabel("%")
                ax.legend()
            fig.tight_layout()
            fig.savefig(OUT / "figures" / f"fig4_shuffle_H{hold}.png", dpi=130)
            plt.close(fig)


def analyze(wide, sectors, master, sigs, W: int, holds=HOLDS, groups=MAIN_GROUPS + EXTRA_GROUPS,
            full: bool = True) -> dict:
    """창 W 하나에 대해 점수를 한 번 만들고, 보유 기간마다 수익률을 붙여 7~8절과 10절 점검을 수행한다."""
    log(f"\n===== 창 W={W} =====")
    ind = rs.indicators(wide, W, groups=tuple(g for g in groups if g != "FOR_NOSC"), rows=sigs)
    sc, bm, cnt = rs.cross_sections(wide, ind, master, sectors, sigs, W, groups=groups)
    del ind
    sc["hs"] = sc["hs"].fillna(sc.groupby("date")["hs"].transform("median"))  # 추정 불가 종목은 그날 중앙값
    cnt.to_csv(OUT / f"filter_counts_W{W}.csv", index=False, encoding="utf-8-sig")
    log("필터 단계별 종목 수 (신호일 평균 / 최소 / 최대):")
    log(cnt.drop(columns="date").agg(["mean", "min", "max"]).T.round(1).to_string())
    log(f"점수 행 {len(sc)}, 신호일 {sc['date'].nunique()}")
    if full:
        describe_indicators(sc, W)
    sc["q"] = np.nan
    for g in groups:
        idx = sc.index[sc["group"] == g]
        sc.loc[idx, "q"] = add_deciles(sc.loc[idx])
    results = {}
    for hold in holds:
        log(f"\n----- 창 W={W}, 보유 {hold}거래일 -----")
        eng = rs.Engine(wide, hold)
        sc[["R", "Rbar", "Rex", "tax", "Rex_idx"]] = stock_rex(sc, bm, eng)
        if full:
            dl = stock_rex(sc, bm, eng, lag=6)
            sc["R_delay"], sc["Rex_delay"] = dl["R"], dl["Rex"]
        log(f"수익률 있는 점수 행 {sc['R'].notna().mean():.1%} (없는 행 = 진입일 정지 또는 보유 만기가 자료 끝을 넘음)")
        res = {}
        for g in groups:
            d = sc[sc["group"] == g]
            if d.empty:
                log(f"[{g}] 점수 산출 신호일 없음")
                continue
            res[g] = summarize(g, d, hold, f"W{W}_H{hold}")
            if full and g in MAIN_GROUPS:
                res[g]["val"] = validate(g, d, wide, hold)
        if "FOR_NOSC" in res:
            short_cover_analysis(sc, res, hold)
        if full:
            engine_check(sc, wide["exists"].columns, hold)
            log(f"\n시장 분리 (보유 {hold}거래일):")
            market_split(sc, hold)
        sc.to_parquet(OUT / f"scores_W{W}_H{hold}.parquet")
        results[hold] = res
        del eng
    return {"sc": sc, "bm": bm, "results": results}
