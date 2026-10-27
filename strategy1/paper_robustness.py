"""사전등록 분석계획(strategy1/paper/사전등록_분석계획.md) 5단계 — 강건성 확인(7절)과 준 표본 밖 검증(8절).

주 분석(paper_main_tests.py 4단계)에서 한 가지씩만 바꿔 다시 추정한다. 보고 대상은 투자주체별 단독 모형의
  극단 순매도 계수 β_S, 극단 순매수 계수 β_B, 차이 β_S − β_B  (주 가설 H1: 외국인 β_S, H2: 외국인 차이,
  H4: 개인 β_B − β_S, H3: 기관 차이)

R1 진입 시점(d+1 시가 / d 종가 참고)  R2 누적 일수 k=5,20  R3 신호 정의(대량거래, 5%, 20%)
R4 꼬리 기준(−10%, 보유 중 최저 −20%)  R5 보유기간 10·60일  R6 KOSPI / KOSDAQ  R7 대형주(크기 상위 1/3), 1,000억 이상
R8 앞 1년 / 뒤 1년  R9 시장 직전 20일 상승 / 하락  R10 통합 LPM(날짜 고정효과, 날짜·종목 양방향 군집), 로짓(날짜 고정효과, 평균 한계효과)
R11 결측 통제변수 중앙값 대체 + 결측 표시  R12 B/M 60영업일 전 값
8.1 시간 분할 차이 검정, 8.2 종목 무작위 절반 분할 200회(시드 0~199), 8.3 시장 재현(R6 과 같은 계산)

출력: data/paper/tests_robustness.csv, tests_stocksplit.csv
"""
import time

import numpy as np
import pandas as pd

from paper_main_tests import CTRL, INV, LAST_SIGNAL, OUT, fm_daily, norm_sf, nw_mean, winsorize_by_day

N_SPLITS = 200


# ---------------------------------------------------------------- 공통: 한 설정의 투자주체별 결과
def run_fm(p, y, lag, sig=lambda c: (f"S_{c}", f"B_{c}"), ctrl=CTRL, kospi=True) -> list[dict]:
    rows = []
    for c in INV:
        s, b = sig(c)
        xs = [s, b, *(["KOSPI"] if kospi else []), *ctrl]
        co = fm_daily(p, y, xs)
        for term, ser in [("β_S", co[s]), ("β_B", co[b]), ("β_S − β_B", co[s] - co[b])]:
            rows.append({"투자자": INV[c], "항": term, "N평균": co["N"].mean(), **nw_mean(ser, lag)})
    return rows


def tail_flag(p, col, thr):
    return np.where(p[col].notna(), (p[col] <= thr).astype(float), np.nan)


# ---------------------------------------------------------------- R10: 통합 추정
def demean_by_day(a: np.ndarray, day: np.ndarray) -> np.ndarray:
    s = pd.DataFrame(a).groupby(day).transform("mean").to_numpy()
    return a - s


def cluster_meat(u: np.ndarray, groups: np.ndarray) -> np.ndarray:
    g = pd.DataFrame(u).groupby(groups).sum().to_numpy()
    return g.T @ g


def twoway_vcov(Q_inv, u, day, stock):
    meat = cluster_meat(u, day) + cluster_meat(u, stock) - u.T @ u  # 교집합 = 관측치 하나
    return Q_inv @ meat @ Q_inv


def pooled_lpm(p, y, sigcols) -> dict:
    d = p.dropna(subset=[y, *CTRL])
    xs = [*sigcols, "KOSPI", *CTRL]
    day = d["일자"].to_numpy()
    X = demean_by_day(d[xs].to_numpy(float), day)
    Y = demean_by_day(d[[y]].to_numpy(float), day)[:, 0]
    Q_inv = np.linalg.inv(X.T @ X)
    b = Q_inv @ X.T @ Y
    u = X * (Y - X @ b)[:, None]
    V = twoway_vcov(Q_inv, u, day, d["종목코드"].to_numpy())
    return {"b": b[:2], "V": V[:2, :2]}


def fe_logit(p, y, sigcols, iters=25) -> dict:
    """날짜 고정효과 로짓. 날짜 효과는 블록 구조로 풀고(슈어 보완), 양방향 군집 샌드위치 공분산.
    평균 한계효과(AME)는 신호 0→1 이산 변화의 평균, 표준오차는 계수 표준오차 × 평균 밀도 p(1−p) 근사."""
    d = p.dropna(subset=[y, *CTRL])
    ev = d.groupby("일자")[y].transform("mean")
    d = d[(ev > 0) & (ev < 1)]  # 사건이 하나도 없는(또는 전부인) 날은 고정효과가 발산
    xs = [*sigcols, "KOSPI", *CTRL]
    X = d[xs].to_numpy(float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Xs = (X - mu) / sd  # 수치 안정용 표준화 (마지막에 되돌림)
    Y = d[y].to_numpy(float)
    day_codes, day = np.unique(d["일자"].to_numpy(), return_inverse=True)
    nd = len(day_codes)
    a = np.zeros(nd)
    b = np.zeros(Xs.shape[1])
    for _ in range(iters):
        eta = a[day] + Xs @ b
        pr = 1 / (1 + np.exp(-eta))
        w = pr * (1 - pr)
        r = Y - pr
        D = np.bincount(day, w, nd)
        C = np.vstack([np.bincount(day, w * Xs[:, k], nd) for k in range(Xs.shape[1])]).T
        G = Xs.T @ (Xs * w[:, None])
        ga = np.bincount(day, r, nd)
        gb = Xs.T @ r
        Sch = G - C.T @ (C / D[:, None])
        db = np.linalg.solve(Sch, gb - C.T @ (ga / D))
        da = (ga - C @ db) / D
        a += da
        b += db
        if np.abs(db).max() < 1e-8:
            break
    eta = a[day] + Xs @ b
    pr = 1 / (1 + np.exp(-eta))
    w = pr * (1 - pr)
    D = np.bincount(day, w, nd)
    C = np.vstack([np.bincount(day, w * Xs[:, k], nd) for k in range(Xs.shape[1])]).T
    Sch_inv = np.linalg.inv(Xs.T @ (Xs * w[:, None]) - C.T @ (C / D[:, None]))
    u = (Xs - (C / D[:, None])[day]) * (Y - pr)[:, None]  # 날짜 효과를 사영해 뺀 점수
    V = twoway_vcov(Sch_inv, u, day, d["종목코드"].to_numpy())
    beta = b / sd
    Vb = V / np.outer(sd, sd)
    ame = []
    for k in range(2):
        x = X[:, k]
        e0 = eta - beta[k] * x
        ame.append(np.mean(1 / (1 + np.exp(-(e0 + beta[k]))) - 1 / (1 + np.exp(-e0))))
    scale = w.mean()
    return {"b": np.array(ame), "V": Vb[:2, :2] * scale ** 2, "beta": beta[:2]}


def pooled_rows(fit_fn, p, y, label) -> list[dict]:
    rows = []
    for c in INV:
        r = fit_fn(p, y, [f"S_{c}", f"B_{c}"])
        b, V = r["b"], r["V"]
        for term, est, var in [("β_S", b[0], V[0, 0]), ("β_B", b[1], V[1, 1]),
                               ("β_S − β_B", b[0] - b[1], V[0, 0] + V[1, 1] - 2 * V[0, 1])]:
            se = np.sqrt(var)
            rows.append({"설정": label, "투자자": INV[c], "항": term, "평균": est, "se": se, "t": est / se})
        print(f"    {label} {INV[c]} 완료", flush=True)
    return rows


# ---------------------------------------------------------------- 8.2 종목 분할
def stock_split(p) -> pd.DataFrame:
    """종목을 무작위 절반으로 나눠 두 그룹 각각 외국인·개인 단독 모형을 추정 (시드 0~199)."""
    d = p.dropna(subset=["Y20", *CTRL])
    tick_codes, tick = np.unique(d["종목코드"].to_numpy(), return_inverse=True)
    days = []
    for _, g in d.groupby("일자", sort=True):
        idx = g.index
        base = np.column_stack([np.ones(len(g)), g[["KOSPI", *CTRL]].to_numpy(float)])
        days.append({"y": g["Y20"].to_numpy(float), "t": tick[d.index.get_indexer(idx)],
                     "XF": np.column_stack([g[["S_F", "B_F"]].to_numpy(float), base]),
                     "XR": np.column_stack([g[["S_R", "B_R"]].to_numpy(float), base])})
    out = []
    for seed in range(N_SPLITS):
        half = np.random.default_rng(seed).permutation(len(tick_codes)) < len(tick_codes) // 2
        res = {}
        for grp in [0, 1]:
            coefs = {"F": [], "R": []}
            for dd in days:
                m = half[dd["t"]] == (grp == 0)
                for c in ["F", "R"]:
                    X = dd[f"X{c}"][m]
                    coefs[c].append(np.linalg.lstsq(X, dd["y"][m], rcond=None)[0][:2])
            F, R = np.array(coefs["F"]), np.array(coefs["R"])
            for name, ser in [("H1", F[:, 0]), ("H2", F[:, 0] - F[:, 1]), ("H4", R[:, 1] - R[:, 0])]:
                res[(name, grp)] = nw_mean(pd.Series(ser), 19)
        for name in ["H1", "H2", "H4"]:
            a, b = res[(name, 0)], res[(name, 1)]
            out.append({"시드": seed, "가설": name, "그룹A_추정": a["평균"], "그룹A_t": a["t"],
                        "그룹B_추정": b["평균"], "그룹B_t": b["t"]})
        if seed % 20 == 19:
            print(f"    종목 분할 {seed + 1}/{N_SPLITS}", flush=True)
    return pd.DataFrame(out)


# ---------------------------------------------------------------- 실행
def main():
    t0 = time.time()
    cols = ["일자", "종목코드", "시장", "KOSPI", "시가총액", "크기3", "bm_lag60",
            "e_20", "e_open_20", "e_d0_20", "e_10", "e_60", "path_min_20", *CTRL,
            *[f"{s}_{c}" for c in INV for s in ["S", "B", "HS", "HB", "S5", "B5", "S20", "B20", "S_k5", "B_k5", "S_k20", "B_k20"]]]
    p0 = pd.read_parquet(OUT / "panel.parquet", columns=cols)
    p0 = p0[p0["일자"] <= LAST_SIGNAL].reset_index(drop=True)
    p = winsorize_by_day(p0.copy(), CTRL + ["bm_lag60"])
    p["Y20"] = tail_flag(p, "e_20", -0.20)
    p["Y_open"] = tail_flag(p, "e_open_20", -0.20)
    p["Y_d0"] = tail_flag(p, "e_d0_20", -0.20)
    p["Y_10pct"] = tail_flag(p, "e_20", -0.10)
    p["Y_path"] = tail_flag(p, "path_min_20", -0.20)
    p["Y_h10"] = tail_flag(p, "e_10", -0.20)
    p["Y_h60"] = tail_flag(p, "e_60", -0.20)
    print(f"표본 {len(p):,}행 — {time.time() - t0:.0f}초", flush=True)

    rows = []

    def add(label, r):
        for x in r:
            rows.append({"설정": label, **x})
        print(f"  {label} 완료 — {time.time() - t0:.0f}초", flush=True)

    add("주 분석", run_fm(p, "Y20", 19))
    # R1 진입 시점. d 종가 진입은 d+1 수익률을 아직 모르므로 그 통제변수를 뺀다
    add("R1 d+1 시가 진입", run_fm(p, "Y_open", 19))
    add("R1 (참고) d 종가 진입", run_fm(p, "Y_d0", 19, ctrl=[c for c in CTRL if c != "r_d1"]))
    # R2 누적 일수
    for k in [5, 20]:
        add(f"R2 누적 {k}일 신호", run_fm(p, "Y20", 19, sig=lambda c, k=k: (f"S_k{k}_{c}", f"B_k{k}_{c}")))
    # R3 신호 정의
    add("R3 대량거래 신호", run_fm(p, "Y20", 19, sig=lambda c: (f"HS_{c}", f"HB_{c}")))
    for k in [5, 20]:
        add(f"R3 하위·상위 {k}%", run_fm(p, "Y20", 19, sig=lambda c, k=k: (f"S{k}_{c}", f"B{k}_{c}")))
    # R4 꼬리 기준
    add("R4 초과수익률 −10%", run_fm(p, "Y_10pct", 19))
    add("R4 보유 중 최저 −20%", run_fm(p, "Y_path", 19))
    # R5 보유기간
    add("R5 보유 10일", run_fm(p, "Y_h10", 9))
    add("R5 보유 60일", run_fm(p, "Y_h60", 59))
    # R6 시장 (= 8.3 시장 재현)
    for m in ["KOSPI", "KOSDAQ"]:
        add(f"R6 {m}만", run_fm(p[p["시장"] == m], "Y20", 19, kospi=False))
    # R7 크기
    add("R7 크기 상위 1/3", run_fm(p[p["크기3"] == 2], "Y20", 19))
    add("R7 시가총액 1,000억 이상", run_fm(p[p["시가총액"] >= 1000e8], "Y20", 19))
    # R8 기간 (= 8.1 시간 분할)
    add("R8 앞 1년", run_fm(p[p["일자"] <= "20251022"], "Y20", 19))
    add("R8 뒤 1년", run_fm(p[p["일자"] >= "20251023"], "Y20", 19))
    # R9 시장 상황: 전 종목 시가총액 가중 지수의 직전 20일(d 포함) 수익률
    f = pd.read_csv(OUT / "factors.csv", encoding="utf-8-sig", dtype={"일자": str}).set_index("일자")
    idx = np.log1p(f["MKT"] + f["RF"]).rolling(20).sum()
    up = set(idx[idx > 0].index)
    add("R9 시장 직전 20일 상승", run_fm(p[p["일자"].isin(up)], "Y20", 19))
    add("R9 시장 직전 20일 하락", run_fm(p[~p["일자"].isin(up)], "Y20", 19))
    # R11 결측 대체
    q = p0.copy()
    for c in CTRL:
        q[f"miss_{c}"] = q[c].isna().astype(float)
        q[c] = q[c].fillna(q.groupby("일자")[c].transform("median"))
    q = winsorize_by_day(q, CTRL)
    q["Y20"] = p["Y20"]
    miss = [f"miss_{c}" for c in CTRL if q[f"miss_{c}"].any()]
    add("R11 결측 중앙값 대체", run_fm(q, "Y20", 19, ctrl=CTRL + miss))
    del q
    # R12 B/M 시점
    add("R12 B/M 60일 전 값", run_fm(p, "Y20", 19, ctrl=[c if c != "bm" else "bm_lag60" for c in CTRL]))
    # R10 추정 방법
    rows += pooled_rows(pooled_lpm, p, "Y20", "R10 통합 LPM (날짜 FE, 양방향 군집)")
    rows += pooled_rows(fe_logit, p, "Y20", "R10 로짓 평균 한계효과 (날짜 FE, 양방향 군집)")
    rob = pd.DataFrame(rows)
    rob.to_csv(OUT / "tests_robustness.csv", index=False, encoding="utf-8-sig")

    # 8.1 앞·뒤 1년 차이 검정
    print("\n=== 8.1 시간 분할: 앞 1년 − 뒤 1년 차이")
    for inv, term, h in [("외국인", "β_S", "H1"), ("외국인", "β_S − β_B", "H2"), ("개인", "β_S − β_B", "H4(부호 반대)"),
                         ("기관", "β_S − β_B", "H3")]:
        a = rob[(rob["설정"] == "R8 앞 1년") & (rob["투자자"] == inv) & (rob["항"] == term)].iloc[0]
        b = rob[(rob["설정"] == "R8 뒤 1년") & (rob["투자자"] == inv) & (rob["항"] == term)].iloc[0]
        z = (a["평균"] - b["평균"]) / np.sqrt(a["se"] ** 2 + b["se"] ** 2)
        print(f"  {h:12s} 앞 {a['평균'] * 100:+.2f}%p (t {a['t']:+.2f})  뒤 {b['평균'] * 100:+.2f}%p (t {b['t']:+.2f})"
              f"  차이 z {z:+.2f} (양측 p {2 * norm_sf(abs(z)):.3f})")

    # 결과표
    show = rob[((rob["투자자"] == "외국인") & rob["항"].isin(["β_S", "β_S − β_B"]))
               | ((rob["투자자"] == "개인") & (rob["항"] == "β_S − β_B"))
               | ((rob["투자자"] == "기관") & (rob["항"] == "β_S − β_B"))].copy()
    show["키"] = show["투자자"] + " " + show["항"]
    show["값"] = [f"{m * 100:+.2f} ({t:+.1f})" for m, t in zip(show["평균"], show["t"])]
    tab = show.pivot(index="설정", columns="키", values="값").reindex(rob["설정"].unique())
    tab = tab[["외국인 β_S", "외국인 β_S − β_B", "개인 β_S − β_B", "기관 β_S − β_B"]]
    pd.set_option("display.width", 220)
    print("\n=== 강건성: %p (t)   [H1 = 외국인 β_S > 0, H2 = 외국인 β_S − β_B > 0, H4 = 개인 β_S − β_B < 0, H3 = 기관 차이 ≈ 0]")
    print(tab.to_string())

    # 8.2 종목 분할
    print(f"\n=== 8.2 종목 무작위 절반 분할 {N_SPLITS}회", flush=True)
    ss = stock_split(p)
    ss.to_csv(OUT / "tests_stocksplit.csv", index=False, encoding="utf-8-sig")
    for h, g in ss.groupby("가설"):
        same = ((g["그룹A_추정"] > 0) & (g["그룹B_추정"] > 0)).mean()
        sig = ((g["그룹A_t"] > 1.645) & (g["그룹B_t"] > 1.645)).mean()
        tt = pd.concat([g["그룹A_t"], g["그룹B_t"]])
        print(f"  {h}: 두 그룹 모두 예상 부호 {same * 100:.1f}%, 두 그룹 모두 단측 5% 유의 {sig * 100:.1f}%,"
              f" t 분포 최소 {tt.min():+.2f} / 중앙 {tt.median():+.2f} / 최대 {tt.max():+.2f}")
    print(f"\n저장: data/paper/tests_robustness.csv, tests_stocksplit.csv — 총 {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()
