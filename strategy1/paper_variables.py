"""사전등록 분석계획(strategy1/paper/사전등록_분석계획.md) 2단계 — 변수와 팩터 구성.

입력
  data/history/ohlcv_*.csv.gz, netbuy_*.csv.gz : 분석 기간 시세·투자주체별 매매 (2024-10-22~2026-10-22)
  data/lookback/ohlcv_*.csv.gz                 : 과거 참조 시세 (2023-09-01~2024-10-21, 통제변수 계산에만 사용)
  data/fundamental/fund_*.csv.gz, cd91.csv     : BPS 등 재무지표, CD 91일물 금리

출력 (data/paper/)
  panel.parquet   : 신호일 × 유니버스 종목 패널. 통제변수(계획서 3.6절), 신호(3.1~3.2절), 결과변수(3.3~3.5절)
  factors.csv     : 일별 MKT, SMB, HML, MOM, STR, FLOW(외국인/기관/개인 × 매일/5일 리밸런싱), FLOW 회전율
  index_check.csv : 직접 만든 팩터와 KRX 지수 비교용 일별 수익률

진입 시점 (계획서 2.4절): 신호일 d 의 매매 데이터는 장 마감 후 공개 → d+1 종가 진입, 수익률은 d+2 일부터.
"""
import argparse
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # 저장소 루트 (data/, .env)
DATA = ROOT / "data"
OUT = DATA / "paper"
INVESTORS = {"외국인": "F", "기관": "I", "개인": "R"}
HORIZONS = [1, 5, 10, 20, 60]
MIN_CAP = 500e8
CSV = dict(encoding="utf-8-sig", dtype={"종목코드": str})


# ---------------------------------------------------------------- 원자료 → 일자 × 종목 행렬
def day_of(p: Path) -> str:
    return p.name.split("_")[1].split(".")[0]


def load_matrices():
    files = sorted([*(DATA / "lookback").glob("ohlcv_*.csv.gz"), *(DATA / "history").glob("ohlcv_*.csv.gz")], key=day_of)
    days = [day_of(p) for p in files]
    tickers = sorted(set().union(*(pd.read_csv(p, usecols=["종목코드"], **CSV)["종목코드"] for p in files)))
    tix = pd.Index(tickers)
    D, T = len(days), len(tickers)
    M = {k: np.full((D, T), np.nan) for k in ["open", "close", "vol", "value", "ret", "cap", "kospi"]}
    for i, p in enumerate(files):
        x = pd.read_csv(p, **CSV)
        j = tix.get_indexer(x["종목코드"])
        M["open"][i, j] = x["시가"]
        M["close"][i, j] = x["종가"]
        M["vol"][i, j] = x["거래량"]
        M["value"][i, j] = x["거래대금"]
        M["cap"][i, j] = x["시가총액"]
        M["kospi"][i, j] = (x["시장"] == "KOSPI").astype(float)
        M["ret"][i, j] = np.where(x["거래량"] > 0, x["등락률"] / 100, np.nan)  # 거래정지일 = 결측

    M["bps"] = np.full((D, T), np.nan)
    for i, d in enumerate(days):
        f = pd.read_csv(DATA / "fundamental" / f"fund_{d}.csv.gz", usecols=["종목코드", "BPS"], **CSV)
        f = f.drop_duplicates("종목코드")
        j = tix.get_indexer(f["종목코드"])
        M["bps"][i, j[j >= 0]] = f["BPS"].to_numpy()[j >= 0]

    hist = sorted((DATA / "history").glob("netbuy_*.csv.gz"), key=day_of)
    hdays = [day_of(p) for p in hist]
    h0 = days.index(hdays[0])
    assert days[h0:] == hdays, "시세와 매매 데이터 날짜가 다릅니다"
    names = {}
    for inv, c in INVESTORS.items():
        for k in ["buy", "sell", "net"]:
            M[f"{k}_{c}"] = np.zeros((len(hdays), T))  # 매매 기록이 없으면 0
    for i, p in enumerate(hist):
        x = pd.read_csv(p, **CSV)
        names.update(zip(x["종목코드"], x["종목명"]))
        for inv, c in INVESTORS.items():
            s = x[x["투자자"] == inv]
            j = tix.get_indexer(s["종목코드"])
            ok = j >= 0
            M[f"buy_{c}"][i, j[ok]] = s["매수거래대금"].to_numpy()[ok]
            M[f"sell_{c}"][i, j[ok]] = s["매도거래대금"].to_numpy()[ok]
            M[f"net_{c}"][i, j[ok]] = s["순매수거래대금"].to_numpy()[ok]
    sec = max((DATA / "history").glob("sectors_*.csv"))
    s = pd.read_csv(sec, **CSV)
    names = {**dict(zip(s["종목코드"], s["종목명"])), **names}

    cd = pd.read_csv(DATA / "fundamental" / "cd91.csv", encoding="utf-8-sig", dtype={"일자": str})
    cd["일자"] = cd["일자"].str.replace("-", "")
    rf_annual = cd.set_index("일자")["CD91"].reindex(days).ffill().to_numpy() / 100
    return days, h0, tix, M, names, rf_annual


def universe_mask(M, tix, names) -> np.ndarray:
    """계획서 2.3절: 거래량>0, 시가총액≥500억, 보통주(코드 끝 0), 스팩·리츠(메리츠 제외) 제외.
    과거 참조 기간에만 있던 종목은 이름을 모르므로 이름 조건은 적용하지 못한다(시가총액 조건으로 대부분 걸러짐)."""
    nm = pd.Series([names.get(t, "") for t in tix])
    col_ok = (tix.str.endswith("0") & ~nm.str.contains("스팩")
              & ~(nm.str.contains("리츠") & ~nm.str.contains("메리츠"))).to_numpy()
    return (M["vol"] > 0) & (M["cap"] >= MIN_CAP) & col_ok[None, :]


# ---------------------------------------------------------------- 시장 지수와 롤링 통계
def index_returns(M, U):
    """시장별 시가총액 가중 지수 일수익률. t 일 수익률 = 전날(t−1) 유니버스 종목을 전날 시가총액으로 가중."""
    D = M["ret"].shape[0]
    r = np.nan_to_num(M["ret"])
    out = {}
    for name, sel in [("KOSPI", 1.0), ("KOSDAQ", 0.0), ("ALL", None)]:
        w = np.where(U, M["cap"], 0.0)
        if sel is not None:
            w = np.where(M["kospi"] == sel, w, 0.0)
        rm = np.full(D, np.nan)
        rm[1:] = (w[:-1] * r[1:]).sum(1) / w[:-1].sum(1)
        out[name] = rm
    return out


def rolling_sum(a: np.ndarray, w: int) -> np.ndarray:
    """축 0 방향 w 일 합 (현재 날 포함). 앞부분 w−1 행은 NaN."""
    c = np.cumsum(np.vstack([np.zeros((1, a.shape[1])), a]), axis=0)
    out = np.full(a.shape, np.nan)
    out[w - 1:] = c[w:] - c[:-w]
    return out


def rolling_stats(M, RM):
    r = M["ret"]
    v = ~np.isnan(r)
    r0 = np.where(v, r, 0.0)
    S = {}
    # 과거 변동성: 직전 20영업일(d 포함) 표준편차, 최소 15일
    n = rolling_sum(v.astype(float), 20)
    s1, s2 = rolling_sum(r0, 20), rolling_sum(r0 ** 2, 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        S["vol20"] = np.where(n >= 15, np.sqrt(np.maximum(s2 - s1 ** 2 / n, 0) / (n - 1)), np.nan)
    # 베타: 직전 250영업일, 최소 120일 (지수 수익률이 없는 첫날은 제외)
    vb = v & np.isfinite(RM)
    r0 = np.where(vb, r, 0.0)
    x0 = np.where(vb, RM, 0.0)
    n = rolling_sum(vb.astype(float), 250)
    sx, sy = rolling_sum(x0, 250), rolling_sum(r0, 250)
    sxx, sxy = rolling_sum(x0 ** 2, 250), rolling_sum(x0 * r0, 250)
    with np.errstate(invalid="ignore", divide="ignore"):
        S["beta"] = np.where(n >= 120, (sxy - sx * sy / n) / (sxx - sx ** 2 / n), np.nan)
    # Amihud: |r| / 거래대금(억원) 의 20일 평균, 회전율: 거래대금/시가총액 20일 평균
    r0 = np.where(v, r, 0.0)
    val = M["value"]
    ok = v & (val > 0)
    n = rolling_sum(ok.astype(float), 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        S["amihud"] = np.where(n >= 15, rolling_sum(np.where(ok, np.abs(r0) / (val / 1e8), 0.0), 20) / n, np.nan)
        S["turnover"] = np.where(n >= 15, rolling_sum(np.where(ok, val / M["cap"], 0.0), 20) / n, np.nan)
    # 누적 로그수익률 (거래정지·상장폐지 이후 수익률 0) → 모멘텀, 단기 반전, 보유 수익률
    L = np.cumsum(np.log1p(r0), axis=0)
    listed = ~np.isnan(M["close"])
    first = np.where(listed.any(0), listed.argmax(0), 10 ** 9)
    D = r.shape[0]
    idx = np.arange(D)[:, None]
    mom = np.full(r.shape, np.nan)
    mom[252:] = np.expm1(L[231:-21] - L[:-252])  # t = d−251 … d−21
    nv = rolling_sum(v.astype(float), 231)
    nv_lag = np.full(r.shape, np.nan)
    nv_lag[21:] = nv[:-21]
    S["mom"] = np.where((first <= idx - 252) & (nv_lag >= 120), mom, np.nan)
    st = np.full(r.shape, np.nan)
    st[21:] = np.expm1(L[20:-1] - L[:-21])  # t = d−20 … d−1
    S["str"] = np.where(first <= idx - 21, st, np.nan)
    S["L"] = L
    return S


def ncskew_duvol(w: np.ndarray, min_n: int):
    """w: (기간 × 종목) 고유 로그수익률(결측 허용). 계획서 3.5절 식 그대로 (demean 없음, up/down 은 기간 평균 기준)."""
    v = ~np.isnan(w)
    n = v.sum(0).astype(float)
    w0 = np.where(v, w, 0.0)
    s2, s3 = (w0 ** 2).sum(0), (w0 ** 3).sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        nc = -(n * (n - 1) ** 1.5 * s3) / ((n - 1) * (n - 2) * s2 ** 1.5)
        mu = w0.sum(0) / n
        down = v & (w < mu)
        up = v & (w >= mu)
        nd, nu = down.sum(0), up.sum(0)
        du = np.log(((nu - 1) * np.where(down, w0 ** 2, 0).sum(0)) / ((nd - 1) * np.where(up, w0 ** 2, 0).sum(0)))
    bad = (n < min_n) | (s2 <= 0)
    nc[bad] = np.nan
    du[bad | (nd < 2) | (nu < 2)] = np.nan
    return nc, du


# ---------------------------------------------------------------- 패널
def build_panel(days, h0, tix, M, U, S, RM, names) -> pd.DataFrame:
    D, T = M["ret"].shape
    L = S["L"]
    di, ti = np.nonzero(U[h0:])
    di = di + h0
    p = pd.DataFrame({"일자": np.array(days)[di], "종목코드": tix[ti],
                      "시장": np.where(M["kospi"][di, ti] == 1, "KOSPI", "KOSDAQ")})
    g = lambda a: a[di, ti]  # noqa: E731
    with np.errstate(invalid="ignore", divide="ignore"):
        p["시가총액"] = g(M["cap"])
        p["size"] = np.log(g(M["cap"]))
        bps, close = g(M["bps"]), g(M["close"])
        p["bm"] = np.where(bps > 0, np.log(bps / close), np.nan)
        lag = np.maximum(di - 60, 0)
        bps60, close60 = M["bps"][lag, ti], M["close"][lag, ti]
        p["bm_lag60"] = np.where((bps60 > 0) & (di >= 60), np.log(bps60 / close60), np.nan)
    p["mom"], p["str"] = g(S["mom"]), g(S["str"])
    p["r_d"] = g(np.nan_to_num(M["ret"]))
    nxt = np.minimum(di + 1, D - 1)
    p["r_d1"] = np.where(di + 1 < D, np.nan_to_num(M["ret"])[nxt, ti], np.nan)
    for k in ["vol20", "beta", "amihud", "turnover"]:
        p[k] = g(S[k])

    # 결과변수: d+1 종가 진입 (주), d+1 시가 진입, d 종가 진입(참고)
    Ld1 = L[nxt, ti]
    with np.errstate(invalid="ignore", divide="ignore"):
        oc = M["close"][nxt, ti] / M["open"][nxt, ti] - 1
    oc = np.where((M["vol"][nxt, ti] > 0) & np.isfinite(oc), oc, 0.0)
    for h in HORIZONS:
        e = di + 1 + h
        ok = e < D
        R = np.where(ok, np.expm1(L[np.minimum(e, D - 1), ti] - Ld1), np.nan)
        p[f"R_{h}"] = R
        p[f"R_open_{h}"] = (1 + oc) * (1 + R) - 1
        e0 = di + h
        p[f"R_d0_{h}"] = np.where(e0 < D, np.expm1(L[np.minimum(e0, D - 1), ti] - L[di, ti]), np.nan)
    for c in [c for c in p.columns if c.startswith("R_")]:
        p["e" + c[1:]] = p[c] - p.groupby(["일자", "시장"])[c].transform("mean")

    # 보유 중 최저 누적수익률(20일, 절대), 고유수익률 기반 NCSKEW/DUVOL (과거 60일, 이후 20·60일)
    beta = S["beta"]
    path = np.full(len(p), np.nan)
    out = {k: np.full(len(p), np.nan) for k in ["skew60_past", "ncskew20", "duvol20", "ncskew60", "duvol60"]}
    rows_by_day = pd.Series(np.arange(len(p))).groupby(di).apply(np.array)
    for d, rows in rows_by_day.items():
        tt = ti[rows]
        b = beta[d, tt]
        if d + 21 < D:
            seg = L[d + 2:d + 22, tt] - L[d + 1, tt]
            path[rows] = np.expm1(seg.min(0))
        with np.errstate(invalid="ignore"):
            wp = np.log1p(M["ret"][d - 59:d + 1, tt] - b * RM[d - 59:d + 1, tt])
        out["skew60_past"][rows] = ncskew_duvol(wp, 45)[0]
        for H, mn in [(20, 15), (60, 45)]:
            if d + 1 + H < D:
                with np.errstate(invalid="ignore"):
                    wf = np.log1p(M["ret"][d + 2:d + 2 + H, tt] - b * RM[d + 2:d + 2 + H, tt])
                nc, du = ncskew_duvol(wf, mn)
                out[f"ncskew{H}"][rows], out[f"duvol{H}"][rows] = nc, du
    p["path_min_20"] = path
    for k, v in out.items():
        p[k] = v

    # 신호 (계획서 3.1~3.2절)
    hd = di - h0
    for inv, c in INVESTORS.items():
        net = M[f"net_{c}"]
        cap = M["cap"][h0:]
        for k in [1, 5, 20]:
            cum = net if k == 1 else rolling_sum(net, k)
            p[f"x{k}_{c}"] = (cum / cap)[hd, ti]
        p[f"a_{c}"] = ((M[f"buy_{c}"] + M[f"sell_{c}"]) / cap)[hd, ti]
    gm = p.groupby(["일자", "시장"])
    p["크기3"] = gm["시가총액"].transform(lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
    for c in INVESTORS.values():
        x = f"x1_{c}"
        r = gm[x].rank(method="first")
        n = gm[x].transform("size")
        grp = ((r - 1) * 10 // n + 1).astype(int)
        p[f"dec_{c}"] = grp
        p[f"S_{c}"] = (grp == 1).astype(np.int8)
        p[f"B_{c}"] = (grp == 10).astype(np.int8)
        p[f"q_{c}"] = gm[x].rank(pct=True) - 0.5
        for k, s in [(5, 0.05), (20, 0.20)]:  # 강건성 R3: 하위·상위 5%, 20%
            p[f"S{k}_{c}"] = (r <= s * n).astype(np.int8)
            p[f"B{k}_{c}"] = (r > (1 - s) * n).astype(np.int8)
        for k in [5, 20]:  # 강건성 R2: 누적 k 일 신호 (그날 하위·상위 10%)
            xk = f"x{k}_{c}"
            rk = gm[xk].rank(method="first")
            nk = gm[xk].transform("count")
            p[f"S_k{k}_{c}"] = np.where(p[xk].notna(), rk <= 0.1 * nk, False).astype(np.int8)
            p[f"B_k{k}_{c}"] = np.where(p[xk].notna(), rk > 0.9 * nk, False).astype(np.int8)
        # 대량거래 버전: 크기 3분위 → 그 안에서 총거래 강도 3분위 → 셀 안 x 하위/상위 30%
        act = p.groupby(["일자", "시장", "크기3"])[f"a_{c}"].transform(
            lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
        cell = p.groupby([p["일자"], p["시장"], p["크기3"], act])[x].rank(pct=True)
        heavy = act == 2
        p[f"HS_{c}"] = (heavy & (cell <= 0.3)).astype(np.int8)
        p[f"HB_{c}"] = (heavy & (cell > 0.7)).astype(np.int8)

    p["KOSPI"] = (p["시장"] == "KOSPI").astype(np.int8)
    f64 = p.select_dtypes("float64").columns
    p[f64] = p[f64].astype(np.float32)
    p["종목명"] = p["종목코드"].map(names).fillna("")
    return p


# ---------------------------------------------------------------- 팩터
def vw_series(member: np.ndarray, M, lag: int) -> np.ndarray:
    """member[f] 로 f 일 종가 기준 구성 → t = f+lag 일 수익률 (가중치 = t−1 일 시가총액)."""
    D = member.shape[0]
    r = np.nan_to_num(M["ret"])
    out = np.full(D, np.nan)
    m = np.zeros_like(member)
    m[lag:] = member[:-lag]
    w = np.where(m[1:], np.nan_to_num(M["cap"][:-1]), 0.0)
    den = w.sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[1:] = np.where(den > 0, (w * r[1:]).sum(1) / den, np.nan)
    return out


def hold_membership(member: np.ndarray, form_days: np.ndarray) -> np.ndarray:
    """form_days 에서 정한 구성을 다음 구성일 전까지 유지."""
    out = np.zeros_like(member)
    last = None
    for d in range(member.shape[0]):
        if form_days[d]:
            last = member[d]
        if last is not None:
            out[d] = last
    return out


def two_by_three(U, cap, var, lo=0.3, hi=0.7):
    """날짜마다 유니버스에서 시가총액 중앙값으로 S/B, var 의 30/70% 분위수로 L/M/H. (6개 bool 행렬)"""
    capu = np.where(U, cap, np.nan)
    varu = np.where(U & np.isfinite(var), var, np.nan)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # 값이 없는 날(신호 이전)은 분위수가 NaN
        med = np.nanmedian(capu, axis=1, keepdims=True)
        q_lo = np.nanquantile(varu, lo, axis=1, keepdims=True)
        q_hi = np.nanquantile(varu, hi, axis=1, keepdims=True)
        ok = U & np.isfinite(var)
        small, big = ok & (capu <= med), ok & (capu > med)
        L_, H_ = ok & (varu <= q_lo), ok & (varu > q_hi)
        M_ = ok & ~L_ & ~H_
    return {"SL": small & L_, "SM": small & M_, "SH": small & H_, "BL": big & L_, "BM": big & M_, "BH": big & H_}


def flow_turnover(legs: dict, M, lag: int) -> np.ndarray:
    """FLOW 하루 매매 금액 비율: 4개 다리(SH, BH, SL, BL) 각각 τ = Σ|새 비중 − 전날 비중의 가격 변화 반영값|,
    롱 1원·숏 1원 기준 매매 금액 = ½(τ_SH + τ_BH) + ½(τ_SL + τ_BL)."""
    D = M["ret"].shape[0]
    r = np.nan_to_num(M["ret"])
    cap = np.nan_to_num(M["cap"])
    tot = np.zeros(D)
    for k in ["SH", "BH", "SL", "BL"]:
        m = np.zeros_like(legs[k])
        m[lag:] = legs[k][:-lag]
        w = np.zeros((D, cap.shape[1]))
        w[1:] = np.where(m[1:], cap[:-1], 0.0)
        s = w.sum(1, keepdims=True)
        w = np.divide(w, s, out=np.zeros_like(w), where=s > 0)
        drift = np.zeros_like(w)
        drift[1:] = w[:-1] * (1 + r[:-1])
        ds = drift.sum(1, keepdims=True)
        drift = np.divide(drift, ds, out=np.zeros_like(drift), where=ds > 0)
        tau = np.abs(w - drift).sum(1)
        tau[(s[:, 0] == 0)] = np.nan
        tot += 0.5 * tau
    return tot


def build_factors(days, h0, M, U, S, rm, rf_annual) -> pd.DataFrame:
    D = len(days)
    f = pd.DataFrame(index=pd.Index(days, name="일자"))
    rf = np.full(D, np.nan)
    rf[1:] = rf_annual[:-1] / 252
    f["RF"] = rf
    f["MKT"] = rm["ALL"] - rf
    month_end = np.array([days[i][:6] != days[i + 1][:6] for i in range(D - 1)] + [True])
    with np.errstate(invalid="ignore", divide="ignore"):
        bm = np.where(M["bps"] > 0, np.log(M["bps"] / M["close"]), np.nan)
    sb = {k: hold_membership(v, month_end) for k, v in two_by_three(U, M["cap"], bm).items()}
    R = {k: vw_series(v, M, 1) for k, v in sb.items()}
    f["SMB"] = (R["SL"] + R["SM"] + R["SH"]) / 3 - (R["BL"] + R["BM"] + R["BH"]) / 3
    f["HML"] = (R["SH"] + R["BH"]) / 2 - (R["SL"] + R["BL"]) / 2
    sm = {k: hold_membership(v, month_end) for k, v in two_by_three(U, M["cap"], S["mom"]).items()}
    R = {k: vw_series(v, M, 1) for k, v in sm.items()}
    f["MOM"] = (R["SH"] + R["BH"]) / 2 - (R["SL"] + R["BL"]) / 2
    # 단기 반전: d 일까지 직전 20일 수익률(d 포함)로 매일 구성 → d+1 일 수익률
    L = S["L"]
    r20 = np.full(L.shape, np.nan)
    r20[20:] = np.expm1(L[20:] - L[:-20])
    R = {k: vw_series(v, M, 1) for k, v in two_by_three(U, M["cap"], r20).items()}
    f["STR"] = (R["SL"] + R["BL"]) / 2 - (R["SH"] + R["BH"]) / 2

    # FLOW: 신호일 d 의 순매수 강도로 구성, d+1 종가 진입 → d+2 일 수익률 (lag 2)
    Uh = np.zeros_like(U)
    Uh[h0:] = U[h0:]
    form5 = np.zeros(D, bool)
    form5[h0::5] = True
    for c in INVESTORS.values():
        x = np.full(M["cap"].shape, np.nan)
        x[h0:] = M[f"net_{c}"] / M["cap"][h0:]
        legs = two_by_three(Uh, M["cap"], x)
        R = {k: vw_series(legs[k], M, 2) for k in ["SH", "BH", "SL", "BL"]}
        f[f"FLOW_{c}"] = (R["SH"] + R["BH"]) / 2 - (R["SL"] + R["BL"]) / 2
        f[f"TO_{c}"] = flow_turnover(legs, M, 2)
        legs5 = {k: hold_membership(v, form5) for k, v in legs.items()}
        R = {k: vw_series(legs5[k], M, 2) for k in ["SH", "BH", "SL", "BL"]}
        f[f"FLOW5_{c}"] = (R["SH"] + R["BH"]) / 2 - (R["SL"] + R["BL"]) / 2
        f[f"TO5_{c}"] = flow_turnover(legs5, M, 2)
    for c in INVESTORS.values():  # 신호가 없는 과거 참조 기간은 결측
        for k in [f"FLOW_{c}", f"TO_{c}", f"FLOW5_{c}", f"TO5_{c}"]:
            f.iloc[:h0 + 2, f.columns.get_loc(k)] = np.nan
    return f


# ---------------------------------------------------------------- 점검
def krx_index_check(days, rm, f) -> pd.DataFrame:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from pykrx import stock
    codes = {"KOSPI": "1001", "KOSPI_대형": "1002", "KOSPI_소형": "1004",
             "KOSDAQ": "2001", "KOSDAQ_대형": "2002", "KOSDAQ_소형": "2004"}
    out = pd.DataFrame(index=pd.Index(days, name="일자"))
    for k, code in codes.items():
        x = stock.get_index_ohlcv(days[0], days[-1], code)["종가"]
        x.index = x.index.strftime("%Y%m%d")
        out[k] = x.reindex(days).pct_change()
        time.sleep(0.5)
    out["우리_KOSPI"], out["우리_KOSDAQ"] = rm["KOSPI"], rm["KOSDAQ"]
    out["우리_SMB"] = f["SMB"].to_numpy()
    out["KRX_소형-대형"] = ((out["KOSPI_소형"] - out["KOSPI_대형"]) + (out["KOSDAQ_소형"] - out["KOSDAQ_대형"])) / 2
    return out


def nw_t(y: np.ndarray, lag: int) -> float:
    y = y[~np.isnan(y)]
    T = len(y)
    e = y - y.mean()
    s = e @ e / T
    for l in range(1, lag + 1):
        s += 2 * (1 - l / (lag + 1)) * (e[l:] @ e[:-l]) / T
    return y.mean() / np.sqrt(s / T)


def report(p: pd.DataFrame, f: pd.DataFrame, chk: pd.DataFrame | None, h0: int, days):
    print(f"\n=== 패널: {len(p):,}행, 신호일 {p['일자'].nunique()}일, 하루 평균 {len(p) / p['일자'].nunique():.0f}종목")
    sig = p[p["일자"] <= "20260917"]
    ctrl = ["size", "bm", "mom", "str", "r_d", "r_d1", "vol20", "beta", "amihud", "turnover", "skew60_past"]
    rows = []
    for c in ctrl:
        v = sig[c]
        q = v.quantile([0.01, 0.25, 0.5, 0.75, 0.99])
        rows.append([c, f"{v.isna().mean() * 100:.1f}%", *[f"{x:.4g}" for x in q]])
    print("\n통제변수 (주 분석 신호일 2024-10-22~2026-09-17): 결측 비율과 분위수")
    print(pd.DataFrame(rows, columns=["변수", "결측", "1%", "25%", "50%", "75%", "99%"]).to_string(index=False))
    allc = sig[ctrl].notna().all(1)
    print(f"통제변수 11개 모두 있는 행: {allc.mean() * 100:.1f}%")

    print("\n결과변수 (주 분석 신호일)")
    e = sig["e_20"]
    print(f"  Y = 1{{e_20 ≤ −20%}} 비율 {(e <= -0.2).mean() * 100:.2f}%,  e_20 ≤ −10% {(e <= -0.1).mean() * 100:.2f}%,"
          f"  보유중 최저 ≤ −20% {(sig['path_min_20'] <= -0.2).mean() * 100:.2f}%")
    print(f"  NCSKEW20 결측 {sig['ncskew20'].isna().mean() * 100:.1f}% 평균 {sig['ncskew20'].mean():.3f},"
          f"  DUVOL20 평균 {sig['duvol20'].mean():.3f}")
    for c in INVESTORS.values():  # 신호별 결과 비율은 출력하지 않는다 (3·4단계 전에 결과를 보지 않기 위해)
        print(f"  {c}: S 비율 {sig[f'S_{c}'].mean() * 100:.1f}%  B {sig[f'B_{c}'].mean() * 100:.1f}%"
              f"  HS {sig[f'HS_{c}'].mean() * 100:.1f}%  HB {sig[f'HB_{c}'].mean() * 100:.1f}%")

    s = f.iloc[h0 + 2:]
    cols = ["MKT", "SMB", "HML", "MOM", "STR", *[f"FLOW_{c}" for c in INVESTORS.values()],
            *[f"FLOW5_{c}" for c in INVESTORS.values()]]
    rows = [[k, s[k].notna().sum(), f"{s[k].mean() * 100:+.3f}", f"{s[k].std() * np.sqrt(252) * 100:.1f}",
             f"{nw_t(s[k].to_numpy(), 5):+.2f}"] for k in cols]
    print("\n팩터 (분석 기간 일수익률): 일평균 %, 연환산 변동성 %, NW t(시차 5)")
    print(pd.DataFrame(rows, columns=["팩터", "일수", "일평균%", "연변동성%", "t"]).to_string(index=False))
    for c in INVESTORS.values():
        print(f"  FLOW_{c} 일평균 매매비율 {s[f'TO_{c}'].mean():.2f}, 5일 리밸런싱 {s[f'TO5_{c}'].mean():.2f}"
              f"  → 편도 0.125% 비용 차감 일평균 {(s[f'FLOW_{c}'] - s[f'TO_{c}'] * 0.00125).mean() * 100:+.3f}%,"
              f" 5일 {(s[f'FLOW5_{c}'] - s[f'TO5_{c}'] * 0.00125).mean() * 100:+.3f}%")
    print("\n팩터 상관")
    print(s[cols].corr().round(2).to_string())
    if chk is not None:
        c = chk.iloc[h0 + 1:]
        print("\nKRX 지수와 비교 (분석 기간 일수익률 상관)")
        print(f"  우리 KOSPI 지수 vs KRX KOSPI   : {c['우리_KOSPI'].corr(c['KOSPI']):.4f}")
        print(f"  우리 KOSDAQ 지수 vs KRX KOSDAQ : {c['우리_KOSDAQ'].corr(c['KOSDAQ']):.4f}")
        print(f"  우리 SMB vs KRX (소형−대형 지수 평균): {c['우리_SMB'].corr(c['KRX_소형-대형']):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-index-check", action="store_true")
    args = ap.parse_args()
    warnings.simplefilter("ignore", pd.errors.PerformanceWarning)
    t0 = time.time()
    days, h0, tix, M, names, rf_annual = load_matrices()
    print(f"원자료: {len(days)}일 ({days[0]}~{days[-1]}), 분석 시작 {days[h0]}, 종목 {len(tix)} — {time.time() - t0:.0f}초")
    U = universe_mask(M, tix, names)
    rm = index_returns(M, U)
    RM = np.where(M["kospi"] == 1, rm["KOSPI"][:, None], rm["KOSDAQ"][:, None])
    S = rolling_stats(M, RM)
    print(f"통제변수 행렬 완료 — {time.time() - t0:.0f}초")
    f = build_factors(days, h0, M, U, S, rm, rf_annual)
    print(f"팩터 완료 — {time.time() - t0:.0f}초")
    p = build_panel(days, h0, tix, M, U, S, RM, names)
    print(f"패널 완료 — {time.time() - t0:.0f}초")
    OUT.mkdir(parents=True, exist_ok=True)
    p.to_parquet(OUT / "panel.parquet", index=False)
    f.to_csv(OUT / "factors.csv", encoding="utf-8-sig")
    chk = None
    if not args.no_index_check:
        chk = krx_index_check(days, rm, f)
        chk.to_csv(OUT / "index_check.csv", encoding="utf-8-sig")
    report(p, f, chk, h0, days)
    print(f"\n저장: {OUT.relative_to(ROOT)} (panel.parquet, factors.csv, index_check.csv) — 총 {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()
