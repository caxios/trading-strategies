"""strategy2 연구계획서 5절 파일럿: 2019-01-01 ~ 2020-12-31, 50종목으로 4~10절 전체를 끝까지 실행한다.

목적은 파이프라인이 끝까지 돌고 데이터 문제가 드러나는지 보는 것이다(5절 3항: 수익률 수치는 해석하지 않는다).
8.4절 (2) 5% 공시 발생률은 계획 변경 기록(assumptions.md 7절)에 따라 모든 분석 뒤 참고 분석으로 따로 한다.
수익률은 7.3절(2026-11-03 변경)대로 신호일 단위 h거래일 수익률이고, 보유 기간은 20(판정 기준)·60(보고)이다.

  strategy2/results/pilot/selection.csv          : 고른 50종목과 선정 사유
  strategy2/results/pilot/filter_counts_W*.csv   : 신호일별 필터 단계 종목 수 (11.2절 표 1)
  strategy2/results/pilot/scores_W*_H*.csv       : 신호일 × 그룹 × 종목 지표·점수·미래 수익률·분위
  strategy2/results/pilot/deciles_W*_H*.csv      : 신호일 × 그룹 × 분위 수익률과 왕복 비용
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
HOLDS = (20, 60)                      # 2절: 20거래일 = 9절 판정 기준, 60거래일 = 보고용
MAIN_GROUPS = ("FOR", "INST")
# 주 설정에서 함께 돌리는 보조 그룹: 숏커버링 필터 없는 FOR(8.5절), 연기금·투신 각각(2절 비고)
EXTRA_GROUPS = ("FOR_NOSC", "PENS", "IVTR")
SEED = 42
N_SHUFFLE = 100
MIN_SIGNALS = 30                      # 이중 정렬·시장 분리를 추정할 최소 신호일 수
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def lag_of(hold: int) -> int:
    """7.3절 Newey–West 시차 = h/5 (20일 → 4, 60일 → 12)."""
    return hold // 5


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
    """7.1·7.2절: 종목별 R, 같은 신호일 기준 시장(유동성 통과 전체) 동일 가중 평균 R̄, 초과수익률, 매도 세율."""
    R, Rbar = {}, {}
    for j, g in bm.groupby("j"):
        r = eng.stock_returns(j, g["code"], lag)
        Rbar[j] = r.mean() if len(r) else np.nan
        R.update({(j, c): v for c, v in r.items()})
    sc = sc.copy()
    sc["R"] = [R.get((j, c), np.nan) for j, c in zip(sc["j"], sc["code"])]
    sc["Rbar"] = sc["j"].map(Rbar)
    sc["Rex"] = sc["R"] - sc["Rbar"]
    sc["tax"] = sc["j"].map(lambda j: eng.sale_tax(j, lag) if j + lag + eng.hold <= len(eng.days) else np.nan)
    return sc


def add_deciles(d: pd.DataFrame, key: str = "score", nq: int = rs.NQ) -> pd.Series:
    return d.groupby("date")[key].transform(lambda x: rs.qassign(x, nq))


def ls_series(tab: pd.DataFrame, col: str = "Rex", hi=rs.NQ, lo=1) -> pd.Series:
    """신호일별 상위 − 하위 분위 차이 D_t."""
    w = tab[col].unstack()
    return w[hi] - w[lo]


def summarize(g: str, d: pd.DataFrame, hold: int) -> dict:
    """8.1절(분위 평균, 10−1, 단조성)과 8.3절(비용 차감 후, 민감도)."""
    lag = lag_of(hold)
    tab = rs.signal_returns(d, "q")
    means = tab["Rex"].unstack().mean()
    m_ls, t_ls, n = rs.nw_t(ls_series(tab), lag)
    w = tab.unstack()
    net10_ex = w[("Rex", rs.NQ)] - w[("cost", rs.NQ)]
    ls_net = net10_ex - (w[("Rex", 1)] + w[("cost", 1)])     # 숏 쪽도 왕복 비용을 낸다
    m_ln, t_ln, _ = rs.nw_t(net10_ex, lag)
    curve = rs.nonoverlap_curve(ls_series(tab), hold // 5)
    sens = {}
    for fee in (rs.FEE, rs.FEE_HIGH):
        for slip in (None, *rs.SLIP_FIXED):
            t = rs.signal_returns(d, "q", fee, slip).unstack()
            sens[f"수수료 {fee:.3%}, 슬리피지 {'AR' if slip is None else f'{slip:.1%}'}"] = \
                float((t[("Rex", rs.NQ)] - t[("cost", rs.NQ)]).mean())
    log(f"[{g}] 신호일 {n} | 분위 평균 {hold}일 초과수익률(%) {np.round(means.values * 100, 2).tolist()}")
    log(f"[{g}] 10−1 평균 {m_ls:.3%} NW t {t_ls:.2f} (시차 {lag}) | 스피어만 {rs.decile_monotonic(means):.2f} | "
        f"10분위 롱 비용 후 초과 {m_ln:.3%} t {t_ln:.2f} | 롱-숏 비용 후 {ls_net.mean():.3%} | "
        f"10분위 평균 왕복 비용 {w[('cost', rs.NQ)].mean():.3%} | 롱-숏 MDD(겹치지 않는 곡선) {rs.max_drawdown(curve):.1%}")
    log(f"[{g}] 비용 민감도(10분위 롱 비용 후 초과 평균): " + ", ".join(f"{k} = {v:.3%}" for k, v in sens.items()))
    tab.to_csv(OUT / f"deciles_{g}_H{hold}.csv", encoding="utf-8-sig")
    return {"ls": (m_ls, t_ls), "long_net": (m_ln, t_ln), "means": means}


def validate(g: str, d: pd.DataFrame, delayed: pd.DataFrame, wide: dict, hold: int) -> None:
    """8.2·8.4절과 10절 2·3번 점검."""
    lag = lag_of(hold)
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
        diff = (cell[5] - cell[1]).groupby("date").mean()
        m, t, n = rs.nw_t(diff, lag)
        log(f"[{g}] 이중 정렬 {ctrl}: 점수 5−1 평균 {m:.3%} NW t {t:.2f} (신호일 {n})")
    # 8.2 (2) Fama–MacBeth
    fm, dropped = rs.fama_macbeth(d)
    m, t, n = rs.nw_t(fm["score"], lag) if len(fm) else (np.nan, np.nan, 0)
    log(f"[{g}] Fama–MacBeth 점수 계수 평균 {m:.5f} NW t {t:.2f} (신호일 {n}, 업종 더미 뺀 신호일 {dropped})")
    # 8.4 (1) 적중률
    hit = d.dropna(subset=["Rex"]).groupby("q")["Rex"].apply(lambda v: (v > 0).mean())
    top = d.dropna(subset=["R"]).sort_values("score", ascending=False).groupby("date").head(20)
    basket = top.groupby("date").agg(R=("R", "mean"), Rbar=("Rbar", "first"), n=("code", "size"))
    log(f"[{g}] 적중률 분위별 {np.round(hit.values, 2).tolist()} | 상위 20 바구니 적중률 "
        f"{(basket['R'] > basket['Rbar']).mean():.2f} (바구니 평균 종목 {basket['n'].mean():.1f})")
    # 8.4 (3) 실적 발표 이벤트 [−1, +1] 누적 초과수익률 (보유 기간과 무관하므로 20일에서만)
    if hold == rs.HOLD:
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
            cars.append(np.nansum(exr[nxt[0] - 1:nxt[0] + 2, col[c]]) if len(nxt) and nxt[0] + 1 < len(days) else np.nan)
        ecar = pd.Series(cars, index=d.index).groupby(d["q"]).mean()
        log(f"[{g}] 실적 발표 CAR[−1,+1] 분위별 평균(%) {np.round(ecar.values * 100, 2).tolist()} "
            f"(이벤트 있는 비율 {np.mean(~np.isnan(cars)):.0%})")
    # 10절 2번 신호 지연: t+5 거래일 다음 날 시가 진입
    orig = ls_series(rs.signal_returns(d, "q")).mean()
    late = ls_series(rs.signal_returns(delayed, "q")).mean()
    log(f"[{g}] 신호 지연 점검: 10−1 평균 원래 {orig:.3%} → 1주 지연 {late:.3%}")
    # 10절 3번 무작위 점수: 같은 신호일 안에서 점수를 섞는다
    rng = np.random.default_rng(rs.NQ)
    sims = []
    for _ in range(N_SHUFFLE):
        s = d.copy()
        s["q"] = add_deciles(s.assign(score=s.groupby("date")["score"].transform(lambda v: rng.permutation(v.to_numpy()))))
        sims.append(ls_series(rs.signal_returns(s, "q")).mean())
    sims = np.array(sims)
    log(f"[{g}] 무작위 점수 {N_SHUFFLE}회: 10−1 평균의 평균 {sims.mean():.3%}, 표준편차 {sims.std():.3%}, "
        f"실제값 백분위 {(sims < orig).mean():.0%}")


def run(W: int, hold: int, wide, sectors, master, sigs, groups=MAIN_GROUPS, full=True) -> dict:
    log(f"\n===== 창 W={W}, 보유 {hold}거래일 =====")
    ind = rs.indicators(wide, W, groups=tuple(g for g in groups if g != "FOR_NOSC"))
    sc, bm, cnt = rs.cross_sections(wide, ind, master, sectors, sigs, W, groups=groups)
    cnt.to_csv(OUT / f"filter_counts_W{W}.csv", index=False, encoding="utf-8-sig")
    log("필터 단계별 종목 수 (신호일 평균):")
    log(cnt.drop(columns="date").mean().round(1).to_string())
    eng = rs.Engine(wide, hold)
    hs = rs.half_spread(wide)
    sc = attach_returns(sc, bm, eng)
    sc["hs"] = sc["hs"].fillna(sc.groupby("date")["hs"].transform("median"))
    delayed = attach_returns(sc.drop(columns=["R", "Rbar", "Rex", "tax"]), bm, eng, lag=6) if full else None
    log(f"신호일 {len(sigs)}개, 점수 행 {len(sc)}, R 결측 {sc['R'].isna().mean():.1%} (진입일 정지 또는 자료 끝)")
    log(f"반스프레드 분포(점수 행): 분위 {np.round(sc['hs'].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).values * 100, 3).tolist()}%")
    res = {}
    sc["q"] = np.nan
    for g in groups:
        d = sc[sc["group"] == g].copy()
        if d.empty:
            log(f"[{g}] 점수 산출 신호일 없음 (참여율 통과 종목이 {rs.NQ}개 미만)")
            continue
        d["q"] = add_deciles(d)
        sc.loc[d.index, "q"] = d["q"]
        res[g] = summarize(g, d, hold)
        if full and g in MAIN_GROUPS:
            dl = delayed.loc[d.index].assign(q=d["q"])
            validate(g, d, dl, wide, hold)
    sc.to_csv(OUT / f"scores_W{W}_H{hold}.csv", index=False, encoding="utf-8-sig")
    return {"sc": sc, "bm": bm, "res": res, "hold": hold}


def short_cover_analysis(main: dict):
    """8.5절: 필터 없는 FOR와 비교, 필터로 제외된 종목의 성과, 공매도 금지 기간별 제외 비율."""
    hold = main["hold"]
    log(f"\n----- 8.5절 숏커버링 필터 보조 분석 (보유 {hold}거래일) -----")
    sc = main["sc"]
    f, nf = sc[sc["group"] == "FOR"], sc[sc["group"] == "FOR_NOSC"]
    for g in ("FOR", "FOR_NOSC"):
        (m_ls, t_ls), (m_ln, t_ln) = main["res"][g]["ls"], main["res"][g]["long_net"]
        log(f"[{g}] 10−1 평균 {m_ls:.3%} NW t {t_ls:.2f} | 10분위 롱 비용 후 초과 {m_ln:.3%} t {t_ln:.2f}")
    kept = set(zip(f["j"], f["code"]))
    ex = nf[[(j, c) not in kept for j, c in zip(nf["j"], nf["code"])]].dropna(subset=["Rex"])
    log(f"제외된 (종목, 신호일) {len(ex)}쌍, 신호일당 평균 {len(ex) / nf['date'].nunique():.1f}종목")
    if ex.empty:
        return
    log(f"제외 종목 평균 초과수익률 {ex['Rex'].mean():.3%}, 시장을 이긴 비율 {(ex['Rex'] > 0).mean():.2f} "
        f"(필터 없는 FOR 전체 {nf['Rex'].mean():.3%} / {(nf['Rex'] > 0).mean():.2f}, "
        f"필터 없는 10분위 {nf.loc[nf['q'] == rs.NQ, 'Rex'].mean():.3%})")
    log("제외 종목의 필터 없는 FOR 점수 분위 분포: " + str(ex["q"].value_counts().sort_index().astype(int).to_dict()))
    m, t, n = rs.nw_t(ex.groupby("date")["Rex"].mean(), lag_of(hold))
    log(f"제외 종목 신호일 단위 초과수익률 평균 {m:.3%} NW t {t:.2f} (제외 종목이 있는 신호일 {n})")
    ban = pd.read_csv(rs.CLEAN / "ref" / "short_sale_ban.csv", parse_dates=["from", "to"])
    ban = ban[ban["regime"] == "전 종목 금지"]
    rate = (1 - f.groupby("date").size() / nf.groupby("date").size()).fillna(1.0)
    in_ban = pd.Series([((ban["from"] <= d) & (d <= ban["to"])).any() for d in rate.index], index=rate.index)
    log(f"제외 비율: 공매도 전면 금지 기간 {rate[in_ban].mean():.1%} (신호일 {in_ban.sum()}), "
        f"그 밖 {rate[~in_ban].mean():.1%} (신호일 {(~in_ban).sum()})")


def engine_check(sc: pd.DataFrame, codes: list[str], hold: int):
    """7.1절 종목 수익률 손계산 대조. 엔진은 일간 수익률(ret)을 복리로 쌓지만, 여기서는 패널의 수정 시가·종가
    수준만으로 직접 계산한다: 보유 마지막 날 가격 = 진입일 이후 마지막으로 거래된 수정 종가."""
    p = pd.concat([pd.read_parquet(rs.CLEAN / f"panel_{y}.parquet", columns=["date", "code", "adj_open", "adj_close"])
                   for y in YEARS])
    p = p[p["code"].isin(codes)]
    days = rs.calendar().index
    days = days[(days >= p["date"].min()) & (days <= p["date"].max())]
    o = p.pivot(index="date", columns="code", values="adj_open").reindex(days)
    c = p.pivot(index="date", columns="code", values="adj_close").reindex(days)
    f = sc[sc["R"].notna()].drop_duplicates(["j", "code"])
    man = np.array([c[code].iloc[j + 1:j + 1 + hold].ffill().iloc[-1] / o[code].iloc[j + 1] - 1
                    for j, code in zip(f["j"], f["code"])])
    log(f"수익률 엔진 손계산 대조 (보유 {hold}거래일): 종목 수익률 {len(f)}건, 최대 절대 차이 "
        f"{np.abs(man - f['R'].to_numpy()).max():.2e}")


def leakage_check(wide, sectors, master, sigs, full_sc, W):
    """10절 4번: 신호일 뒤 행을 모두 지운 자료로 다시 계산해도 그날 점수가 같아야 한다."""
    rng = np.random.default_rng(SEED)
    days = wide["exists"].index
    full_t = full_sc[full_sc["group"].isin(MAIN_GROUPS)]
    for t in sorted(rng.choice(sigs, 3, replace=False)):
        j = days.get_loc(t)
        cut = {k: v.iloc[:j + 1] for k, v in wide.items()}
        sc, _, _ = rs.cross_sections(cut, rs.indicators(cut, W), master, sectors, [t], W, groups=MAIN_GROUPS)
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
            m, t, n = rs.nw_t(ls_series(rs.signal_returns(d, "q")), lag_of(hold))
            log(f"[{g}] {name} 분리: 신호일 {n}, 10−1 평균 {m:.3%} NW t {t:.2f}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sel = select_pilot()
    sel.to_csv(OUT / "selection.csv", index=False, encoding="utf-8-sig")
    log("선정 종목:", sel.groupby("reason").size().to_dict())
    master = rs.eligible_master().loc[sel["code"]]
    wide, sectors = rs.load_wide(YEARS, sel["code"].tolist())
    log(f"행렬 {wide['exists'].shape}, 기간 {wide['exists'].index[0].date()} ~ {wide['exists'].index[-1].date()}")
    sigs = rs.signal_days(rs.calendar().index, START, END)
    tr = wide["halted"] == 0
    log(f"거래일인데 수정 시가 결측: {int((tr & wide['adj_open'].isna()).sum().sum())}건, "
        f"거래일 순매수(FOR) 결측: {int((tr & wide['FOR_net'].isna()).sum().sum())}건 / {int(tr.sum().sum())}")

    runs = {h: run(rs.W_MAIN, h, wide, sectors, master, sigs, MAIN_GROUPS + EXTRA_GROUPS) for h in HOLDS}
    for h in HOLDS:
        short_cover_analysis(runs[h])
    log("\n----- 10절 점검 -----")
    for h in HOLDS:
        engine_check(runs[h]["sc"], sel["code"].tolist(), h)
    leakage_check(wide, sectors, master, sigs, runs[rs.HOLD]["sc"], rs.W_MAIN)
    bm = runs[rs.HOLD]["bm"]
    dl = set(master.index[master["delisted"] == "True"])
    log("기준 시장에 포함된 상폐 종목 수(연도별):",
        bm[bm["code"].isin(dl)].groupby(bm["date"].dt.year)["code"].nunique().to_dict())
    # 11.2절 표 7 강건성 (판정 기준인 20거래일 보유에서): 창 20일, 시장 분리
    run(20, rs.HOLD, wide, sectors, master, sigs, full=False)
    log(f"\n----- 시장 분리 (창 60일, 보유 {rs.HOLD}거래일) -----")
    market_split(runs[rs.HOLD]["sc"], rs.HOLD)
    (OUT / "diagnostics.txt").write_text("\n".join(LOG), encoding="utf-8")


if __name__ == "__main__":
    main()
