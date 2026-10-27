"""사전등록 분석계획(strategy1/paper/사전등록_분석계획.md) 3·4단계 — 본 분석.

4단계 (꼬리 위험, 계획서 5.1~5.2절)
  날짜 d 마다 횡단면 선형확률모형
      Y_{i,d} = a_d + β_S S^j_{i,d} + β_B B^j_{i,d} + δ KOSPI_i + γ' Z_{i,d} + ε
  Y = 1{d+1 종가 진입 20일 시장 대비 초과수익률 ≤ −20%}, S/B = 투자주체 j 순매수 강도 그날·시장 하위/상위 10%,
  Z = 통제변수 11개 (날짜별 1%/99% 윈저화). 날짜별 계수 평균 + Newey-West t (시차 max(h−1, 5)).
  같은 식에 NCSKEW·DUVOL (20일, 60일)을 종속변수로 넣은 보조 분석.
  가설: H1 β_S^F>0, H2 β_S^F−β_B^F>0, H4 β_B^R−β_S^R>0 (Holm), H3 기관 |β_S−β_B|<0.5%p (TOST),
        H5 β_S^j>0, β_B^j>0, H6 세 투자주체 신호를 함께 넣은 모형에서 β_S^F>0.

3단계 (평균 수익률, 계획서 5.3~5.4절)
  Fama-MacBeth: e^h_{i,d} = a_d + b_d q^j_{i,d} + δ KOSPI_i + c' Z_{i,d} + u  (h = 1, 5, 20), q = 그날·시장 백분위 − 0.5
  FLOW 팩터 시계열 회귀: FLOW_t = α + β' (MKT, SMB, HML, MOM, STR)_t + ε, NW 시차 5, 비용 차감 전/후.
  가설: H7 b^F>0 (h=1, 5), H8 비용 차감 후 α = 0 (양측, 기각되지 않으면 가설과 일치).

입력: data/paper/panel.parquet, data/paper/factors.csv (paper_variables.py 출력)
출력: data/paper/tests_tail.csv, tests_returns.csv, tests_factor.csv, hypotheses.csv, daily_coefs.parquet
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # 저장소 루트 (data/, .env)
OUT = ROOT / "data" / "paper"
INV = {"F": "외국인", "I": "기관", "R": "개인"}
CTRL = ["size", "bm", "mom", "str", "r_d", "r_d1", "vol20", "beta", "amihud", "turnover", "skew60_past"]
LAST_SIGNAL = "20260917"  # 20일 결과가 관측되는 마지막 신호일
COST_ONE_WAY = 0.00125
TOST_MARGIN = 0.005


# ---------------------------------------------------------------- 공통
def norm_sf(z: float) -> float:
    """표준정규 상단 꼬리확률 P(Z > z)."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def nw_mean(y: pd.Series, lag: int) -> dict:
    """시계열 평균과 Newey-West(바틀렛) 표준오차."""
    y = y.dropna().to_numpy(float)
    T = len(y)
    e = y - y.mean()
    s = e @ e / T
    for l in range(1, lag + 1):
        s += 2 * (1 - l / (lag + 1)) * (e[l:] @ e[:-l]) / T
    se = math.sqrt(s / T)
    return {"T": T, "평균": y.mean(), "se": se, "t": y.mean() / se}


def winsorize_by_day(p: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    g = p.groupby("일자")[cols]
    lo = g.quantile(0.01).reindex(p["일자"]).to_numpy()
    hi = g.quantile(0.99).reindex(p["일자"]).to_numpy()
    p[cols] = np.clip(p[cols].to_numpy(float), lo, hi)
    return p


def fm_daily(p: pd.DataFrame, y: str, xs: list[str]) -> pd.DataFrame:
    """날짜별 횡단면 OLS 계수 (상수 포함)."""
    rows = []
    for d, g in p.groupby("일자", sort=True):
        g = g.dropna(subset=[y, *xs])
        if len(g) < len(xs) + 30:
            continue
        X = np.column_stack([np.ones(len(g)), g[xs].to_numpy(float)])
        b = np.linalg.lstsq(X, g[y].to_numpy(float), rcond=None)[0]
        rows.append([d, len(g), *b])
    return pd.DataFrame(rows, columns=["일자", "N", "const", *xs]).set_index("일자")


def ols_hac(y: np.ndarray, X: np.ndarray, lag: int):
    """y = X b + e, Newey-West 공분산. (계수, 표준오차)"""
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X)
    u = X * e[:, None]
    S = u.T @ u
    for k in range(1, lag + 1):
        G = u[k:].T @ u[:-k]
        S += (1 - k / (lag + 1)) * (G + G.T)
    V = XtXi @ S @ XtXi
    return b, np.sqrt(np.diag(V))


# ---------------------------------------------------------------- 4단계: 꼬리 위험
def tail_tests(p: pd.DataFrame):
    rows, daily = [], {}
    outcomes = [("Y20", "Y = 1{e20 ≤ −20%}", 20), ("ncskew20", "NCSKEW 20일", 20), ("duvol20", "DUVOL 20일", 20),
                ("ncskew60", "NCSKEW 60일", 60), ("duvol60", "DUVOL 60일", 60)]
    for y, label, h in outcomes:
        lag = max(h - 1, 5)
        specs = [(c, [f"S_{c}", f"B_{c}"]) for c in INV] + [("결합", [f"{s}_{c}" for c in INV for s in "SB"])]
        for name, sig in specs:
            co = fm_daily(p, y, [*sig, "KOSPI", *CTRL])
            daily[(y, name)] = co
            terms = {v: co[v] for v in sig}
            if name != "결합":
                c = name
                terms[f"S_{c} − B_{c}"] = co[f"S_{c}"] - co[f"B_{c}"]
            for term, s in terms.items():
                r = nw_mean(s, lag)
                rows.append({"결과변수": label, "모형": "단독" if name != "결합" else "결합",
                             "투자자": INV.get(name, "세 주체"), "항": term, **r})
            if y == "Y20" and name != "결합":  # 상대 크기 계산용 기준 확률: 신호 없는 종목의 꼬리 사건 비율(일평균)
                sub = p[(p[f"S_{name}"] == 0) & (p[f"B_{name}"] == 0)].dropna(subset=[y, *CTRL])
                base = sub.groupby("일자")[y].mean().mean()
                for r in rows[-3:]:
                    r["기준확률"] = base
            print(f"  {label} / {INV.get(name, '결합')} 완료 ({len(co)}일, 평균 {co['N'].mean():.0f}종목)", flush=True)
    return pd.DataFrame(rows), daily


# ---------------------------------------------------------------- 3단계: 평균 수익률
def return_tests(p: pd.DataFrame):
    rows, daily = [], {}
    for h in [1, 5, 20]:
        lag = max(h - 1, 5)
        for c in INV:
            co = fm_daily(p, f"e_{h}", [f"q_{c}", "KOSPI", *CTRL])
            daily[(f"e_{h}", c)] = co
            rows.append({"보유기간": h, "투자자": INV[c], "항": f"q_{c}", **nw_mean(co[f"q_{c}"], lag)})
    return pd.DataFrame(rows), daily


def factor_tests(f: pd.DataFrame):
    rows = []
    base = ["MKT", "SMB", "HML", "MOM", "STR"]
    for c in INV:
        for flow, to, lab in [(f"FLOW_{c}", f"TO_{c}", "매일"), (f"FLOW5_{c}", f"TO5_{c}", "5일")]:
            d = f[[flow, to, *base]].dropna()
            X = np.column_stack([np.ones(len(d)), d[base].to_numpy()])
            for kind, y in [("비용 전", d[flow]), ("비용 후", d[flow] - d[to] * COST_ONE_WAY)]:
                b, se = ols_hac(y.to_numpy(), X, 5)
                m = nw_mean(y, 5)
                rows.append({"투자자": INV[c], "리밸런싱": lab, "구분": kind, "T": len(d),
                             "평균": m["평균"], "평균_t": m["t"], "alpha": b[0], "alpha_se": se[0], "alpha_t": b[0] / se[0],
                             **{f"β_{k}": v for k, v in zip(base, b[1:])},
                             "일평균매매비율": d[to].mean(),
                             "손익분기_편도비용": b[0] / d[to].mean() if kind == "비용 전" else np.nan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 가설 판정
def judge(tail: pd.DataFrame, ret: pd.DataFrame, fac: pd.DataFrame) -> pd.DataFrame:
    def get(term, model="단독", y="Y = 1{e20 ≤ −20%}"):
        return tail[(tail["결과변수"] == y) & (tail["모형"] == model) & (tail["항"] == term)].iloc[0]

    rows = []
    # 주 가설 (Holm)
    main = [("H1", "외국인 극단 순매도 → 꼬리 위험↑", get("S_F")),
            ("H2", "외국인 매도 − 매수 > 0", get("S_F − B_F"))]
    r = get("S_R − B_R")
    main.append(("H4", "개인 매수 − 매도 > 0", {**r, "평균": -r["평균"], "t": -r["t"]}))
    ps = [norm_sf(m[2]["t"]) for m in main]
    order = np.argsort(ps)
    reject, stop = {}, False
    for k, i in enumerate(order):
        thr = 0.05 / (len(ps) - k)
        ok = (not stop) and ps[i] <= thr
        stop = stop or not ok
        reject[i] = (ok, thr)
    for i, (hid, desc, m) in enumerate(main):
        rows.append({"가설": hid, "내용": desc, "추정치": m["평균"], "t": m["t"], "p(단측)": ps[i],
                     "판정기준": f"Holm {reject[i][1]:.4f}", "결과": "기각(지지)" if reject[i][0] else "기각 못함"})
    # H3 동등성 (TOST)
    m = get("S_I − B_I")
    p1 = norm_sf((m["평균"] + TOST_MARGIN) / m["se"])
    p2 = norm_sf((TOST_MARGIN - m["평균"]) / m["se"])
    p_two = 2 * norm_sf(abs(m["t"]))
    rows.append({"가설": "H3", "내용": f"기관 |매도 − 매수| < {TOST_MARGIN * 100:.1f}%p (TOST)", "추정치": m["평균"],
                 "t": m["t"], "p(단측)": max(p1, p2), "판정기준": "TOST 5%",
                 "결과": ("동등성 성립" if max(p1, p2) < 0.05 else "동등성 확인 못함") + f" (일반 양측 p {p_two:.3f})"})
    # 보조 가설 (본페로니: H5 6 + H6 1 + H7 2 + H8 3 = 12)
    n_sec = 12
    sec = []
    for c in INV:
        for s in "SB":
            sec.append(("H5", f"{INV[c]} {'극단 순매도' if s == 'S' else '극단 순매수'} → 꼬리 위험↑", get(f"{s}_{c}"), "단측"))
    sec.append(("H6", "결합 모형 외국인 극단 순매도", get("S_F", model="결합"), "단측"))
    for h in [1, 5]:
        r = ret[(ret["보유기간"] == h) & (ret["항"] == "q_F")].iloc[0]
        sec.append(("H7", f"외국인 순매수 순위 → {h}일 초과수익률", r, "단측"))
    for c in INV:
        r = fac[(fac["투자자"] == INV[c]) & (fac["리밸런싱"] == "매일") & (fac["구분"] == "비용 후")].iloc[0]
        sec.append(("H8", f"{INV[c]} FLOW 비용 후 α = 0", {"평균": r["alpha"], "t": r["alpha_t"]}, "양측"))
    for hid, desc, m, side in sec:
        p = norm_sf(m["t"]) if side == "단측" else 2 * norm_sf(abs(m["t"]))
        if hid == "H8":
            res = "α = 0 기각 못함 (가설과 일치)" if p > 0.05 else "α ≠ 0 (가설과 불일치)"
        else:
            res = ("유의(본페로니)" if p <= 0.05 / n_sec else "유의(보정 전)" if p <= 0.05 else "유의하지 않음")
        rows.append({"가설": hid, "내용": desc, "추정치": m["평균"], "t": m["t"], f"p({side})" if side == "양측" else "p(단측)": p,
                     "판정기준": f"본페로니 {0.05 / n_sec:.4f}" if hid != "H8" else "양측 5%", "결과": res})
    return pd.DataFrame(rows)


def show(tail, ret, fac, hyp):
    pd.set_option("display.width", 200)
    print("\n=== 4단계: 꼬리 위험 Fama-MacBeth 선형확률모형 (NW t, 시차 max(h−1,5))")
    t = tail.copy()
    t["값"] = [f"{v * 100:+.2f}%p" if y.startswith("Y") else f"{v:+.3f}" for v, y in zip(t["평균"], t["결과변수"])]
    t["t"] = t["t"].map(lambda v: f"{v:+.2f}")
    print(t[["결과변수", "모형", "투자자", "항", "값", "t", "T"]].to_string(index=False))
    base = tail.dropna(subset=["기준확률"]).drop_duplicates("투자자")
    print("\n기준 확률(신호 없는 종목의 꼬리 사건 비율, 일평균): "
          + ", ".join(f"{r.투자자} {r.기준확률 * 100:.2f}%" for r in base.itertuples()))

    print("\n=== 3단계-1: Fama-MacBeth 수익률 (q 계수 = 순매수 순위 최하위→최상위 시 초과수익률 차이)")
    r = ret.copy()
    r["값"] = r["평균"].map(lambda v: f"{v * 100:+.3f}%")
    r["t"] = r["t"].map(lambda v: f"{v:+.2f}")
    print(r[["보유기간", "투자자", "값", "t", "T"]].to_string(index=False))

    print("\n=== 3단계-2: FLOW 팩터 시계열 회귀 (일수익률, NW 시차 5)")
    fcols = ["투자자", "리밸런싱", "구분", "평균", "평균_t", "alpha", "alpha_t", "일평균매매비율", "손익분기_편도비용"]
    ff = fac[fcols].copy()
    for k in ["평균", "alpha", "손익분기_편도비용"]:
        ff[k] = ff[k].map(lambda v: "" if pd.isna(v) else f"{v * 100:+.3f}%")
    for k in ["평균_t", "alpha_t"]:
        ff[k] = ff[k].map(lambda v: f"{v:+.2f}")
    ff["일평균매매비율"] = ff["일평균매매비율"].map(lambda v: f"{v:.2f}")
    print(ff.to_string(index=False))
    print(fac[["투자자", "리밸런싱", "구분", *[c for c in fac.columns if c.startswith("β_")]]]
          .query("구분 == '비용 전'").round(3).to_string(index=False))

    print("\n=== 가설 판정")
    h = hyp.copy()
    h["추정치"] = [f"{v * 100:+.2f}%p" if g in ("H1", "H2", "H3", "H4", "H5", "H6") else f"{v * 100:+.3f}%"
                for v, g in zip(h["추정치"], h["가설"])]
    h["t"] = h["t"].map(lambda v: f"{v:+.2f}")
    pc = [c for c in h.columns if c.startswith("p(")]
    for c in pc:
        h[c] = h[c].map(lambda v: "" if pd.isna(v) else f"{v:.4f}")
    print(h[["가설", "내용", "추정치", "t", *pc, "판정기준", "결과"]].to_string(index=False))


def main():
    cols = ["일자", "종목코드", "KOSPI", "e_1", "e_5", "e_20", "ncskew20", "duvol20", "ncskew60", "duvol60", *CTRL,
            *[f"{s}_{c}" for c in INV for s in "SBq"]]
    p = pd.read_parquet(OUT / "panel.parquet", columns=cols)
    p = p[p["일자"] <= LAST_SIGNAL].copy()
    p["Y20"] = np.where(p["e_20"].notna(), (p["e_20"] <= -0.20).astype(float), np.nan)
    p = winsorize_by_day(p, CTRL)
    print(f"표본: 신호일 {p['일자'].nunique()}일 ({p['일자'].min()}~{p['일자'].max()}), {len(p):,}행", flush=True)

    tail, d_tail = tail_tests(p)
    ret, d_ret = return_tests(p)
    f = pd.read_csv(OUT / "factors.csv", encoding="utf-8-sig", dtype={"일자": str}).set_index("일자")
    fac = factor_tests(f)
    hyp = judge(tail, ret, fac)

    tail.to_csv(OUT / "tests_tail.csv", index=False, encoding="utf-8-sig")
    ret.to_csv(OUT / "tests_returns.csv", index=False, encoding="utf-8-sig")
    fac.to_csv(OUT / "tests_factor.csv", index=False, encoding="utf-8-sig")
    hyp.to_csv(OUT / "hypotheses.csv", index=False, encoding="utf-8-sig")
    dc = pd.concat({f"{k[0]}|{k[1]}": v for k, v in {**d_tail, **d_ret}.items()}, names=["모형"]).reset_index()
    dc.to_parquet(OUT / "daily_coefs.parquet", index=False)
    show(tail, ret, fac, hyp)
    print("\n저장: data/paper/tests_tail.csv, tests_returns.csv, tests_factor.csv, hypotheses.csv, daily_coefs.parquet")


if __name__ == "__main__":
    main()
