"""투자주체 수급 데이터의 리스크관리 활용 분석 (3부).

1부 — 10개 그룹 전부의 수익률 검정
    investor_flow_decile_backtest.py 와 같은 10분위(순매수거래대금 / 그날 시가총액) 포트폴리오의
    1~10그룹 전부와 '거래 없음'(그날 그 투자자 매수·매도 0) 그룹을 검정한다.
    기준 두 가지:
      시장 대비 : 종목 수익률 − 같은 날 같은 시장 유니버스 단순평균
      크기 통제 : 종목 수익률 − 같은 날 같은 시장 같은 시가총액 3분위 종목 단순평균
    H0: 날짜별 그룹 포트폴리오 평균 = 0 (양측), Newey-West t (시차 h−1).
    본페로니: 3투자자 × 10그룹 × 5보유기간 = 150회 → 양측 |t| > 3.59.

2부 — 시장 전체 수급이 지수 수익률을 예측하는가
    F_{m,i,d} = 시장 m 전 종목 투자자 i 순매수거래대금 합 / 시장 m 전 종목 시가총액 합
    F^k_{m,i,d} = 최근 k 영업일 F 의 합 (k = 1, 5, 20)
    지수 수익률 = 전일 시가총액 가중 전 종목 수익률 (KOSPI·KOSDAQ 지수 근사, pykrx 지수로 검증)
    회귀: R^h_{m,d} = a + b · z(F^k_{m,i,d}) + e   (R^h = d+1 ~ d+h 지수 누적수익률)
    b 의 t 값은 Newey-West (시차 h−1), 비중첩 표본 회귀 t 범위로 교차 검증.

3부 — 꼬리 위험
    신호(외국인 1그룹, 외국인 대량거래 순매도, 기관 1그룹, 기관 대량거래 순매도, 개인 10그룹,
    개인 대량거래 순매수, 손바뀜(외국인 1그룹 & 개인 10그룹), 기관 거래 없음)별로
      초과수익률 ≤ −10% / ≤ −20% 확률, 보유 중 최저 수익률 ≤ −10% / ≤ −20% 확률, 이후 20일 변동성,
      5% VaR / CVaR
    를 같은 날 같은 시장 전 종목(시장 기준), 같은 시가총액 3분위 종목(크기 통제 기준)과 비교한다.
    확률 차이 검정: 날짜별 (신호 종목 비율 − 기준 비율) 시계열의 Newey-West t (시차 h−1).

출력 (data/):
  investor_flow_risk_groups.csv   : 1부
  investor_flow_risk_market.csv   : 2부 회귀
  investor_flow_risk_market_q.csv : 2부 5분위 조건부 평균
  investor_flow_risk_tail.csv     : 3부

사용 예:
    python investor_flow_risk_analysis.py
    python investor_flow_risk_analysis.py --no-validate   # pykrx 지수 검증 생략
"""
import argparse
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from investor_flow_control_backtest import assign_cells
from investor_flow_decile_backtest import (INVESTORS, MARKETS, TESTED, assign_groups, attach_forward,
                                           build_universe, forward_returns, nonoverlap_t)
from netsell_reversal_backtest import load, nw_tstat

ROOT = Path(__file__).resolve().parent.parent  # 저장소 루트 (data/, .env)
OUT = ROOT / "data"
COST = 0.0025
BONF_Z_GROUP = NormalDist().inv_cdf(1 - 0.05 / 150 / 2)  # ≈ 3.59
FLOW_K = [1, 5, 20]
TAIL_H = [5, 20, 60]
PAIRS = [("외국인 1그룹", "(대조) 외국인 10그룹"),
         ("외국인 대량거래 순매도", "(대조) 외국인 대량거래 순매수"),
         ("기관 1그룹", "(대조) 기관 10그룹"),
         ("기관 대량거래 순매도", "(대조) 기관 대량거래 순매수"),
         ("(대조) 개인 1그룹", "개인 10그룹"),
         ("(대조) 개인 대량거래 순매도", "개인 대량거래 순매수")]


# ================================================================ 공통
def add_size_bucket(u: pd.DataFrame) -> pd.DataFrame:
    u["크기"] = u.groupby(["일자", "시장"])["시가총액"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
    for h in TESTED:
        u[f"크기초과_{h}"] = u[f"수익_{h}"] - u.groupby(["일자", "시장", "크기"])[f"수익_{h}"].transform("mean")
    return u


def gross_trade(u: pd.DataFrame, nb: pd.DataFrame, inv: str) -> np.ndarray:
    g = nb.loc[nb["투자자"] == inv].set_index(["일자", "종목코드"])
    v = (g["매수거래대금"] + g["매도거래대금"]).reindex(list(zip(u["일자"], u["종목코드"])))
    return v.fillna(0).to_numpy()


# ================================================================ 1부
def part1(d: pd.DataFrame, inv: str, days) -> list[dict]:
    labels = [(f"G{g}", d["그룹"] == g) for g in range(1, 11)] + [("거래없음", d["총거래"] == 0)]
    rows = []
    for mkt in ["전체", *MARKETS]:
        dm = d if mkt == "전체" else d[d["시장"] == mkt]
        for label, mask in labels:
            sub = dm[mask.loc[dm.index]]
            if sub.empty:
                continue
            share = len(sub) / len(dm)
            for h in TESTED:
                p = sub.groupby("일자")[[f"초과_{h}", f"크기초과_{h}"]].mean().sort_index()
                for basis, col in [("시장 대비", f"초과_{h}"), ("크기 통제", f"크기초과_{h}")]:
                    y = p[col].dropna()
                    t = nw_tstat(y.to_numpy(), h - 1)
                    _, lo, hi, _ = nonoverlap_t(y, h, days)
                    row = {"투자자": inv, "시장": mkt, "그룹": label, "종목비율": share, "기준": basis, "보유기간": h,
                           "T": len(y), "평균": y.mean(), "t_NW": t, "유의_5%": abs(t) > 1.96,
                           "유의_본페로니": abs(t) > BONF_Z_GROUP, "비중첩_t_최소": lo, "비중첩_t_최대": hi}
                    if basis == "시장 대비":
                        yc = y - COST
                        row.update({"평균_비용후": yc.mean(), "t_NW_비용후": nw_tstat(yc.to_numpy(), h - 1)})
                    rows.append(row)
    return rows


# ================================================================ 2부
def index_returns(px: pd.DataFrame, days) -> pd.DataFrame:
    """시장별 전일 시가총액 가중 일별 수익률 (전 종목, 지수 근사)."""
    out = {}
    for m in MARKETS:
        p = px[px["시장"] == m]
        r = p.pivot(index="일자", columns="종목코드", values="등락률").reindex(days) / 100
        cap_prev = p.pivot(index="일자", columns="종목코드", values="시가총액").reindex(days).shift(1)
        w = cap_prev.where(r.notna())
        out[m] = (w * r).sum(axis=1) / w.sum(axis=1)
    return pd.DataFrame(out).iloc[1:]  # 첫날은 전일 시가총액 없음


def validate_index(idx: pd.DataFrame) -> dict:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from pykrx import stock
    res = {}
    for m, code in [("KOSPI", "1001"), ("KOSDAQ", "2001")]:
        o = stock.get_index_ohlcv(idx.index[0], idx.index[-1], code)
        real = o["종가"].pct_change()
        real.index = real.index.strftime("%Y%m%d")
        j = pd.concat([idx[m], real], axis=1, keys=["근사", "지수"]).dropna()
        res[m] = {"일수익률_상관": j["근사"].corr(j["지수"]),
                  "누적_근사": (1 + j["근사"]).prod() - 1, "누적_지수": (1 + j["지수"]).prod() - 1}
    return res


def ols_nw(y: np.ndarray, x: np.ndarray, lag: int):
    """y = a + b x 의 b, Newey-West t, R²."""
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X)
    u = X * e[:, None]
    S = u.T @ u
    for k in range(1, min(lag, len(y) - 1) + 1):
        G = u[k:].T @ u[:-k]
        S += (1 - k / (lag + 1)) * (G + G.T)
    V = XtXi @ S @ XtXi
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return b[1], b[1] / np.sqrt(V[1, 1]), r2


def ols_plain_t(y, x):
    X = np.column_stack([np.ones(len(x)), x])
    b, res, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    s2 = e @ e / (len(y) - 2)
    return b[1] / np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])


def part2(nb: pd.DataFrame, px: pd.DataFrame, days):
    idx = index_returns(px, days)
    cap = px.groupby(["일자", "시장"])["시가총액"].sum()
    flow = nb.groupby(["일자", "시장", "투자자"])["순매수거래대금"].sum().unstack("투자자")
    F = flow.div(cap, axis=0)  # (일자, 시장) × 투자자, 시가총액 대비 비율

    rows, qrows = [], []
    for m in MARKETS:
        LI = np.log1p(idx[m]).cumsum()
        fwd = {h: np.expm1(LI.shift(-h) - LI) for h in TESTED}  # d 종가 → d+h 종가
        Fm = F.xs(m, level="시장").reindex(idx.index)
        for inv in INVESTORS:
            for k in FLOW_K:
                sig = Fm[inv].rolling(k).sum()
                z = (sig - sig.mean()) / sig.std()
                same = z.corr(idx[m])  # 같은 날 (k=1 이면 당일 수급 vs 당일 지수)
                for h in TESTED:
                    j = pd.concat([z, fwd[h]], axis=1, keys=["z", "y"]).dropna()
                    b, t, r2 = ols_nw(j["y"].to_numpy(), j["z"].to_numpy(), h - 1)
                    ts = [ols_plain_t(j["y"].to_numpy()[o::h], j["z"].to_numpy()[o::h])
                          for o in range(h) if len(j) // h >= 5]
                    rows.append({"시장": m, "투자자": inv, "누적일수k": k, "보유기간": h, "T": len(j),
                                 "기울기_1표준편차당": b, "t_NW": t, "R2": r2, "유의_5%": abs(t) > 1.96,
                                 "비중첩_t_최소": min(ts) if ts else np.nan,
                                 "비중첩_t_최대": max(ts) if ts else np.nan,
                                 "당일상관(같은날 지수수익률)": same})
                if k == 5:
                    for h in [5, 20]:
                        j = pd.concat([sig, fwd[h]], axis=1, keys=["s", "y"]).dropna()
                        j["q"] = pd.qcut(j["s"].rank(method="first"), 5, labels=False) + 1
                        for q, g in j.groupby("q"):
                            qrows.append({"시장": m, "투자자": inv, "보유기간": h, "5분위": q,
                                          "F5_평균(bp)": g["s"].mean() * 1e4, "이후지수수익률": g["y"].mean(),
                                          "일수": len(g)})
    return idx, pd.DataFrame(rows), pd.DataFrame(qrows)


# ================================================================ 3부
def path_min_and_vol(px: pd.DataFrame, days):
    """보유 중 최저 수익률(d+1..d+h 중 최저 누적), 이후 20일 일별 수익률 표준편차."""
    px = px.assign(r=np.where(px["거래량"] > 0, px["등락률"] / 100, np.nan))
    R = px.pivot(index="일자", columns="종목코드", values="r").reindex(days)
    LR = np.log1p(R.fillna(0)).cumsum().to_numpy()
    n = len(days)
    mins = {}
    for h in TAIL_H:
        M = np.full_like(LR, np.nan)
        cur = np.full((n - h, LR.shape[1]), np.inf)
        for k in range(1, h + 1):
            cur = np.minimum(cur, LR[k:n - h + k] - LR[:n - h])
        M[:n - h] = np.expm1(cur)
        mins[h] = M
    roll = R.rolling(20, min_periods=15).std()
    vol = roll.shift(-20).to_numpy()  # d+1..d+20 (이후 변동성)
    past = roll.to_numpy()            # d-19..d (과거 변동성, 신호일까지 알 수 있는 값)
    return mins, vol, past, R.columns


def part3(u: pd.DataFrame, flags: dict, mins, vol, tickers, days) -> pd.DataFrame:
    di = pd.Index(days).get_indexer(u["일자"])
    ci = pd.Index(tickers).get_indexer(u["종목코드"])
    t = u[["일자", "시장", "크기", "변동성"]].copy()
    metrics = {}
    for h in TAIL_H:
        e = u[f"초과_{h}"]
        metrics[f"초과≤-10%_{h}"] = (e <= -0.10).where(e.notna())
        metrics[f"초과≤-20%_{h}"] = (e <= -0.20).where(e.notna())
        mn = pd.Series(mins[h][di, ci], index=u.index)
        metrics[f"보유중최저≤-10%_{h}"] = (mn <= -0.10).where(mn.notna())
        metrics[f"보유중최저≤-20%_{h}"] = (mn <= -0.20).where(mn.notna())
    metrics["이후20일변동성"] = pd.Series(vol[di, ci], index=u.index)
    for c, v in metrics.items():
        t[c] = v.astype(float)
        t[f"{c}__시장"] = t.groupby(["일자", "시장"])[c].transform("mean")
        t[f"{c}__크기"] = t.groupby(["일자", "시장", "크기"])[c].transform("mean")
        t[f"{c}__크기변동성"] = t.groupby(["일자", "시장", "크기", "변동성"])[c].transform("mean")

    rows = []
    for name, mask in flags.items():
        s = t[mask]
        for c in metrics:
            h = int(c.rsplit("_", 1)[1]) if c[-1].isdigit() else 20
            daily = s.groupby("일자")[[c, f"{c}__시장", f"{c}__크기", f"{c}__크기변동성"]].mean().sort_index()
            row = {"신호": name, "지표": c, "보유기간": h, "신호_관측수": int(s[c].notna().sum()),
                   "신호값": daily[c].mean(),
                   "시장기준값": daily[f"{c}__시장"].mean(), "크기통제기준값": daily[f"{c}__크기"].mean(),
                   "크기변동성통제기준값": daily[f"{c}__크기변동성"].mean()}
            for basis in ["시장", "크기", "크기변동성"]:
                diff = (daily[c] - daily[f"{c}__{basis}"]).dropna()
                row[f"차이_{basis}"] = diff.mean()
                row[f"t_NW_{basis}"] = nw_tstat(diff.to_numpy(), h - 1)
            rows.append(row)
        for h in TAIL_H:
            e_sig = u.loc[mask, f"초과_{h}"].dropna()
            e_all = u[f"초과_{h}"].dropna()
            for lab, e in [("신호", e_sig), ("전체", e_all)]:
                q = e.quantile(0.05)
                rows.append({"신호": name, "지표": f"VaR5%_{h}" if lab == "신호" else f"VaR5%_{h}_전체종목",
                             "보유기간": h, "신호값": q, "신호_관측수": len(e)})
                rows.append({"신호": name, "지표": f"CVaR5%_{h}" if lab == "신호" else f"CVaR5%_{h}_전체종목",
                             "보유기간": h, "신호값": e[e <= q].mean(), "신호_관측수": len(e)})

    # 방향 차이: 같은 '극단적 수급' 종목끼리 매도 신호 − 매수 신호 (각각 크기·변동성 통제 기준 대비 초과분의 차이)
    pair_rows = []
    for a, b in PAIRS:
        for c in metrics:
            h = int(c.rsplit("_", 1)[1]) if c[-1].isdigit() else 20
            ex = t[c] - t[f"{c}__크기변동성"]
            da = ex[flags[a]].groupby(t.loc[flags[a], "일자"]).mean()
            db = ex[flags[b]].groupby(t.loc[flags[b], "일자"]).mean()
            diff = (da - db).dropna().sort_index()
            pair_rows.append({"매도측": a, "매수측": b, "지표": c, "보유기간": h,
                              "매도측_초과": da.mean(), "매수측_초과": db.mean(),
                              "차이": diff.mean(), "t_NW": nw_tstat(diff.to_numpy(), h - 1)})
    return pd.DataFrame(rows), pd.DataFrame(pair_rows)


# ================================================================ 출력
def pct(v, d=2):
    return "" if pd.isna(v) else f"{v * 100:+.{d}f}%"


def tv(v):
    return "" if pd.isna(v) else f"({v:+.1f})"


def print_part1(g: pd.DataFrame):
    for basis in ["시장 대비", "크기 통제"]:
        print(f"\n=== 1부 [전체 시장] 그룹별 {basis} 초과수익률 (비용 전, NW t)  * |t|>1.96  ** 본페로니 |t|>{BONF_Z_GROUP:.2f}")
        s = g[(g["시장"] == "전체") & (g["기준"] == basis)]
        for inv, gi in s.groupby("투자자", sort=False):
            tab = {}
            for h in TESTED:
                gh = gi[gi["보유기간"] == h].set_index("그룹")
                tab[f"{h}일"] = [pct(r["평균"]) + tv(r["t_NW"]) + ("**" if r["유의_본페로니"] else "*" if r["유의_5%"] else "")
                                for _, r in gh.iterrows()]
                idx = gh.index
            tab = pd.DataFrame(tab, index=idx)
            tab.insert(0, "종목비율", [f"{v * 100:.0f}%" for v in gi[gi["보유기간"] == 1].set_index("그룹")["종목비율"]])
            print(f"\n[{inv}]")
            print(tab.to_string())


def print_part2(reg: pd.DataFrame, q: pd.DataFrame, val):
    if val:
        print("\n=== 2부 지수 근사 검증 (전일 시가총액 가중 전 종목 vs pykrx 지수)")
        for m, v in val.items():
            print(f"  {m}: 일수익률 상관 {v['일수익률_상관']:.4f}, 누적 근사 {pct(v['누적_근사'])} vs 지수 {pct(v['누적_지수'])}")
    print("\n=== 2부 시장 수급 z(F^k) 1표준편차당 이후 지수 수익률 (NW t)  * |t|>1.96   [비중첩 t 범위]")
    for (m, inv), g in reg.groupby(["시장", "투자자"], sort=False):
        lines = []
        for k, gk in g.groupby("누적일수k"):
            gk = gk.set_index("보유기간")
            cells = [f"{pct(r['기울기_1표준편차당'])}{tv(r['t_NW'])}{'*' if r['유의_5%'] else ''}"
                     + (f"[{r['비중첩_t_최소']:+.1f}~{r['비중첩_t_최대']:+.1f}]" if h > 1 else "")
                     for h, r in gk.iterrows()]
            lines.append([f"k={k}", f"{gk['당일상관(같은날 지수수익률)'].iloc[0]:+.2f}", *cells])
        print(f"\n[{m} · {inv}]")
        print(pd.DataFrame(lines, columns=["누적", "같은날상관", *[f"{h}일" for h in TESTED]]).to_string(index=False))
    print("\n=== 2부 최근 5일 누적 시장 수급 5분위별 이후 지수 수익률 평균 (1분위 = 가장 많이 순매도)")
    for (m, h), g in q.groupby(["시장", "보유기간"]):
        tab = g.pivot(index="투자자", columns="5분위", values="이후지수수익률").reindex(INVESTORS).map(pct)
        print(f"\n[{m} · 이후 {h}일]")
        print(tab.to_string())


def print_part3(t: pd.DataFrame):
    show = ["초과≤-10%_5", "초과≤-20%_20", "보유중최저≤-20%_20", "초과≤-20%_60", "보유중최저≤-20%_60", "이후20일변동성"]
    print("\n=== 3부 꼬리 위험  각 칸: 신호값 / 크기·변동성 통제 기준값 → 배율 (차이 NW t)   * |t|>1.96")
    lines = []
    for name, g in t.groupby("신호", sort=False):
        g = g.set_index("지표")
        cells = []
        for c in show:
            r = g.loc[c]
            f = (lambda v: f"{v * 100:.2f}") if "변동성" in c else (lambda v: f"{v * 100:.1f}")
            star = "*" if abs(r["t_NW_크기변동성"]) > 1.96 else ""
            cells.append(f"{f(r['신호값'])}/{f(r['크기변동성통제기준값'])}→{r['신호값'] / r['크기변동성통제기준값']:.2f}배"
                         f"({r['t_NW_크기변동성']:+.1f}){star}")
        lines.append([name, *cells])
    print(pd.DataFrame(lines, columns=["신호", *show]).to_string(index=False))
    print("\n=== 3부 같은 지표, 크기 통제만 했을 때 배율 (변동성 통제 전)")
    lines = [[name, *[f"{g.set_index('지표').loc[c, '신호값'] / g.set_index('지표').loc[c, '크기통제기준값']:.2f}배" for c in show]]
             for name, g in t.groupby("신호", sort=False)]
    print(pd.DataFrame(lines, columns=["신호", *show]).to_string(index=False))
    print("\n=== 3부 5% VaR / CVaR (시장 대비 초과수익률 분포, 전체 관측 합산)")
    lines = []
    for name, g in t.groupby("신호", sort=False):
        g = g.set_index("지표")
        lines.append([name, *[f"{pct(g.loc[f'VaR5%_{h}', '신호값'], 1)} / {pct(g.loc[f'CVaR5%_{h}', '신호값'], 1)}" for h in TAIL_H]])
    lines.append(["전체 종목", *[f"{pct(t[t['지표'] == f'VaR5%_{h}_전체종목']['신호값'].iloc[0], 1)} / "
                              f"{pct(t[t['지표'] == f'CVaR5%_{h}_전체종목']['신호값'].iloc[0], 1)}" for h in TAIL_H]])
    print(pd.DataFrame(lines, columns=["신호", *[f"{h}일 VaR/CVaR" for h in TAIL_H]]).to_string(index=False))


def print_pairs(pr: pd.DataFrame):
    show = ["초과≤-10%_5", "초과≤-20%_20", "보유중최저≤-20%_20", "초과≤-20%_60", "보유중최저≤-20%_60", "이후20일변동성"]
    print("\n=== 3부 방향 차이: (매도 쪽 − 매수 쪽) 크기·변동성 통제 초과 확률 차이 %p (NW t)  * |t|>1.96")
    lines = []
    for (a, b), g in pr.groupby(["매도측", "매수측"], sort=False):
        g = g.set_index("지표")
        lines.append([f"{a} − {b.replace('(대조) ', '')}",
                      *[f"{g.loc[c, '차이'] * 100:+.2f}({g.loc[c, 't_NW']:+.1f}){'*' if abs(g.loc[c, 't_NW']) > 1.96 else ''}"
                        for c in show]])
    print(pd.DataFrame(lines, columns=["비교", *show]).to_string(index=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--min-cap", type=float, default=500)
    p.add_argument("--no-validate", action="store_true")
    args = p.parse_args()

    nb, px = load("netbuy"), load("ohlcv")
    names = nb.drop_duplicates("종목코드", keep="last").set_index("종목코드")["종목명"]
    days = sorted(px["일자"].unique())
    u = build_universe(px, names, args.min_cap)
    fwd, tickers = forward_returns(px, days)
    u = add_size_bucket(attach_forward(u, fwd, tickers, days))
    mins, vol, past, tk = path_min_and_vol(px, days)
    u["과거변동성"] = past[pd.Index(days).get_indexer(u["일자"]), pd.Index(tk).get_indexer(u["종목코드"])]
    u["변동성"] = u.groupby(["일자", "시장", "크기"])["과거변동성"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) if s.notna().sum() >= 5 else np.nan)
    print(f"유니버스 하루 평균 {u.groupby('일자').size().mean():.0f}종목")

    # 1부 + 3부 신호 준비
    g_rows, flags = [], {}
    for inv in INVESTORS:
        d = assign_groups(u, nb, inv)
        d["총거래"] = gross_trade(d, nb, inv)
        g_rows += part1(d, inv, days)
        c = assign_cells(d, nb, inv)
        heavy = (c["규모"] == 2)
        if inv == "외국인":
            flags["외국인 1그룹"] = d["그룹"] == 1
            flags["외국인 대량거래 순매도"] = heavy & (c["방향"] == "순매도")
            flags["(대조) 외국인 10그룹"] = d["그룹"] == 10
            flags["(대조) 외국인 대량거래 순매수"] = heavy & (c["방향"] == "순매수")
            f1 = d["그룹"] == 1
        elif inv == "기관":
            flags["기관 1그룹"] = d["그룹"] == 1
            flags["기관 대량거래 순매도"] = heavy & (c["방향"] == "순매도")
            flags["(대조) 기관 10그룹"] = d["그룹"] == 10
            flags["(대조) 기관 대량거래 순매수"] = heavy & (c["방향"] == "순매수")
            flags["기관 거래없음"] = d["총거래"] == 0
        else:
            flags["개인 10그룹"] = d["그룹"] == 10
            flags["개인 대량거래 순매수"] = heavy & (c["방향"] == "순매수")
            flags["(대조) 개인 1그룹"] = d["그룹"] == 1
            flags["(대조) 개인 대량거래 순매도"] = heavy & (c["방향"] == "순매도")
            flags["손바뀜(외국인 1그룹 & 개인 10그룹)"] = f1 & (d["그룹"] == 10)
        print(f"  1부 {inv} 완료")
    groups = pd.DataFrame(g_rows)
    groups.to_csv(OUT / "investor_flow_risk_groups.csv", index=False, encoding="utf-8-sig")

    # 2부
    idx, reg, q = part2(nb, px, days)
    val = None
    if not args.no_validate:
        try:
            val = validate_index(idx)
        except Exception as e:  # 네트워크/로그인 문제는 분석과 무관
            print(f"  지수 검증 생략: {e}")
    reg.to_csv(OUT / "investor_flow_risk_market.csv", index=False, encoding="utf-8-sig")
    q.to_csv(OUT / "investor_flow_risk_market_q.csv", index=False, encoding="utf-8-sig")
    print("  2부 완료")

    # 3부
    tail, pairs = part3(u, flags, mins, vol, tk, days)
    tail.to_csv(OUT / "investor_flow_risk_tail.csv", index=False, encoding="utf-8-sig")
    pairs.to_csv(OUT / "investor_flow_risk_tail_pairs.csv", index=False, encoding="utf-8-sig")
    print("  3부 완료")

    print_part1(groups)
    print_part2(reg, q, val)
    print_part3(tail)
    print_pairs(pairs)
    print("\n저장: data/investor_flow_risk_groups.csv, investor_flow_risk_market.csv, "
          "investor_flow_risk_market_q.csv, investor_flow_risk_tail.csv")


if __name__ == "__main__":
    main()
