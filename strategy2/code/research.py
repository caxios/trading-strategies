"""strategy2 연구계획서 4·6·7·8·10절 공통 함수: 패널 적재, 점수, 포트폴리오 수익률, 검증 통계.

run_pilot.py(5절 파일럿)와 이후 전체 실행 스크립트가 같이 쓴다. 정제 패널(data/clean)만 읽는다.

  load_wide()        : 연도별 패널 → 날짜 × 종목 행렬 묶음
  indicators()       : 6절 지표와 4.1·4.3·4.4·6.1절 필터 재료 (행렬, 신호일 이하 자료만 사용)
  cross_sections()   : 신호일마다 필터 적용 → 은밀성 회귀 → 순위 표준화 → 점수 (긴 표)
  Engine             : 다음 날 시가 진입 · h거래일 보유 종목 수익률, 매도 결제일 세율
  signal_returns()   : 신호일 × 분위 단위 수익률과 왕복 비용 (7.3·7.4절)
  nw_t(), fama_macbeth() 등 : 8절 검증 통계
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"

# 2절 사전 고정 파라미터
W_MAIN, HOLD, NQ = 60, 20, 10
LIQ_MIN, LIQ_DAYS = 1e9, 20
PART_MIN, SC_RATIO = 0.05, 0.5
MIN_AGE, MIN_TRADED = 252, 0.8
NW_LAG = 4
FEE, FEE_HIGH = 0.00015, 0.0005       # 7.4절 편도 수수료 기본값, 민감도
SLIP_FIXED = (0.001, 0.003)           # 7.4절 슬리피지 고정값 민감도
SPREAD_DAYS = 60                      # Abdi–Ranaldo 추정 창
EVENT_DAYS = 60                       # 8.4절 (3) 신호일 이후 실적 발표를 찾는 범위

# FOR·INST 가 주 분석, PENS 는 2절 비고의 보조 분석(연기금 단독). 투신 단독은 생략(assumptions.md 7절)
GROUPS = {"FOR": ("FRGN", "OFRGN"), "INST": ("PENS", "IVTR"), "PENS": ("PENS",)}
INVESTORS = ("FRGN", "OFRGN", "PENS", "IVTR")
PX_FIELDS = ["exists", "halted", "in_liq", "kosdaq", "value", "mktcap", "ret", "close", "adj_open", "adj_close",
             "adj_high", "adj_low", "loan_known", "loan_avail"]


def calendar() -> pd.DataFrame:
    """KRX 거래일 전체(2014-01-02~)와 시장 지수 일간 수익률."""
    return pd.read_csv(CLEAN / "index_ret.csv", parse_dates=["date"]).set_index("date")


def eligible_master() -> pd.DataFrame:
    """4.1절의 정적 조건(우선주·스팩·리츠/펀드·외국 기업 제외)을 통과한 종목 마스터."""
    m = pd.read_csv(CLEAN / "master.csv", dtype=str)
    bad = m[["is_pref", "is_spac", "is_reit_fund", "is_foreign"]].eq("True").any(axis=1)
    return m[~bad].set_index("code")


def list_pos(master: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.Series:
    """종목별 상장일의 거래일 위치. 2014-01-02 이전 상장은 충분히 작은 값(-10000)."""
    ld = pd.to_datetime(master["list_date"], errors="coerce")
    first = pd.to_datetime(master["first_date"], format="%Y%m%d")
    ld = ld.where(master["list_date_src"] != "first_trade", first)
    pos = pd.Series(cal.searchsorted(ld.fillna(pd.Timestamp("1900-01-01"))), index=master.index).astype(float)
    pos[(master["list_date_src"] == "before_20140102") | (ld < cal[0])] = -10000
    return pos


def load_wide(years: list[int], codes: list[str], sector_dates=None) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """연도별 패널에서 codes 만 읽어 날짜 × 종목 행렬(float32, 메모리 절약)을 만든다. 행이 없는 날(상장 전·상폐 후)은 NaN.
    반환: (행렬 묶음, 업종 조회용 긴 표 date·code·sector). sector_dates 를 주면 그 날짜의 업종만 남긴다."""
    cols = ["date", "code", "market", "high", "low", "close", "value", "mktcap", "halted", "ret", "adj_close",
            "adj_open", *[f"{p}_{s}" for p in INVESTORS for s in ("buy", "sell", "net")],
            "loan_bal_known", "loan_avail", "sector", "in_liquidation"]
    parts, sectors = {}, []
    for y in years:
        p = pd.read_parquet(CLEAN / f"panel_{y}.parquet", columns=cols)
        p = p[p["code"].isin(codes)].copy()
        adj = p["adj_close"] / p["close"]
        p["adj_high"], p["adj_low"] = p["high"] * adj, p["low"] * adj
        p["exists"] = 1.0
        p["halted"] = p["halted"].astype(float)
        p["in_liq"] = p["in_liquidation"].astype(float)
        p["kosdaq"] = (p["market"] == "KOSDAQ").astype(float)
        p["loan_known"] = p["loan_bal_known"]
        p["loan_avail"] = p["loan_avail"].astype(float)
        for g, members in GROUPS.items():
            p[f"{g}_gross"] = sum(p[f"{m}_buy"] + p[f"{m}_sell"] for m in members)
            p[f"{g}_net"] = sum(p[f"{m}_net"] for m in members)
        sec = p[["date", "code", "sector"]]
        sectors.append(sec if sector_dates is None else sec[sec["date"].isin(sector_dates)])
        for c in PX_FIELDS + [f"{g}_{s}" for g in GROUPS for s in ("gross", "net")]:
            parts.setdefault(c, []).append(p.pivot(index="date", columns="code", values=c))
        del p
    cal = calendar().index
    first = min(v.index.min() for v in parts["exists"])
    last = max(v.index.max() for v in parts["exists"])
    days = cal[(cal >= first) & (cal <= last)]
    cols_all = sorted(set().union(*[set(v.columns) for v in parts["exists"]]))
    wide = {}
    for c in list(parts):
        wide[c] = pd.concat(parts.pop(c)).reindex(index=days, columns=cols_all).astype("float32")
    return wide, pd.concat(sectors, ignore_index=True)


def market_ret(wide: dict) -> pd.DataFrame:
    """종목별로 그날 속한 시장의 지수 수익률 r_{m(i),t} (행이 없는 날은 NaN)."""
    idx = calendar().reindex(wide["exists"].index)
    k = wide["kosdaq"]
    return k.mul(idx["KOSDAQ"], axis=0) + (1 - k).mul(idx["KOSPI"], axis=0)


TICK_UNIFIED = pd.Timestamp("2023-01-25")  # 호가가격단위 개편(코스피·코스닥 통일)


def tick_size(close: pd.DataFrame, kosdaq: pd.DataFrame) -> pd.DataFrame:
    """KRX 호가가격단위(원). 2023-01-25 이전은 시장별, 이후는 통일된 표."""
    c = close.to_numpy()
    old_kospi = np.select([c < 1000, c < 5000, c < 10000, c < 50000, c < 100000, c < 500000],
                          [1, 5, 10, 50, 100, 500], 1000)
    old_kosdaq = np.select([c < 1000, c < 5000, c < 10000, c < 50000], [1, 5, 10, 50], 100)
    new = np.select([c < 2000, c < 5000, c < 20000, c < 50000, c < 200000, c < 500000],
                    [1, 5, 10, 50, 100, 500], 1000)
    old = np.where(kosdaq.to_numpy() == 1, old_kosdaq, old_kospi)
    after = (close.index >= TICK_UNIFIED)[:, None]
    return pd.DataFrame(np.where(after, new, old), index=close.index, columns=close.columns).where(close.notna())


def half_spread(wide: dict) -> pd.DataFrame:
    """Abdi–Ranaldo(2017) 종가·고가·저가 스프레드 추정의 절반 (7.4절 s).
    η_t = (ln H_t + ln L_t)/2, 이틀 추정 s² = 4(ln C_t − η_t)(ln C_t − η_{t+1}).
    t일 값에는 (t−1, t) 쌍까지만 쓰도록 하루 밀고, 최근 SPREAD_DAYS일 평균의 음수는 0 으로 둔다.
    스프레드는 호가 단위보다 좁을 수 없으므로 최근 SPREAD_DAYS일 평균 (반 틱 / 종가)를 하한으로 둔다(파일럿에서 추가)."""
    lc, eta = np.log(wide["adj_close"]), (np.log(wide["adj_high"]) + np.log(wide["adj_low"])) / 2
    s2 = (4 * (lc - eta) * (lc - eta.shift(-1))).shift(1)
    m = s2.rolling(SPREAD_DAYS, min_periods=SPREAD_DAYS // 2).mean()
    floor = (0.5 * tick_size(wide["close"], wide["kosdaq"]) / wide["close"]).rolling(
        SPREAD_DAYS, min_periods=SPREAD_DAYS // 2).mean()
    return np.maximum(np.sqrt(m.clip(lower=0)) / 2, floor)


def indicators(wide: dict, W: int, groups=("FOR", "INST"), rows=None) -> dict[str, pd.DataFrame]:
    """6절 지표와 필터 재료. 모든 값은 t일까지의 행만 쓰는 뒤쪽 창(rolling)으로 계산한다.
    거래정지일의 순매수·수익률은 NaN 이라 합산에서 빠진다(4.3절). rows(신호일 목록)를 주면 그 날짜 행만 남긴다."""
    out = _indicators(wide, W, groups)
    return out if rows is None else {k: v.loc[rows] for k, v in out.items()}


def _indicators(wide: dict, W: int, groups) -> dict[str, pd.DataFrame]:
    ex, halted = wide["exists"], wide["halted"]
    traded = ((ex == 1) & (halted == 0)).astype(float).where(ex.notna())
    out = {"N": traded.rolling(W, min_periods=W).sum()}
    out["liq"] = wide["value"].rolling(LIQ_DAYS, min_periods=LIQ_DAYS).mean()
    sum_val = wide["value"].rolling(W, min_periods=1).sum()
    excess = (wide["ret"].fillna(0) - market_ret(wide)).where(ex.notna())
    # 거래정지일은 종목 수익률 0, 시장 수익률은 차감 → 재개일 수익률이 정지 기간 전체를 담으므로 기간이 맞는다
    out["CAR"] = excess.rolling(W, min_periods=1).sum()
    mcap_prev = wide["mktcap"].shift(1)
    for g in groups:
        net = wide[f"{g}_net"]
        sum_net = net.rolling(W, min_periods=1).sum()
        out[f"{g}_part"] = wide[f"{g}_gross"].rolling(W, min_periods=1).sum() / (2 * sum_val)
        out[f"{g}_C"] = (net / mcap_prev).rolling(W, min_periods=1).sum()
        out[f"{g}_P"] = (net > 0).astype(float).where(net.notna()).rolling(W, min_periods=1).sum() / out["N"]
        out[f"{g}_S"] = sum_net / sum_val
        out[f"{g}_sumnet"] = sum_net
    # 4.4절 + 부록 A-1: ΔLoan_t = Loan_{t-1} − Loan_{t-W}. loan_known_t = Loan_{t-1} 이므로 W-1 행 전과의 차
    out["dloan"] = wide["loan_known"] - wide["loan_known"].shift(W - 1)
    return out


def qassign(x: pd.Series, n: int) -> pd.Series:
    """동점은 순서대로 갈라 1..n 분위를 고르게 배정."""
    r = x.rank(method="first")
    return np.ceil(r * n / len(x)).astype(int)


def rank_z(x: pd.Series) -> pd.Series:
    """6.6절 z(X) = Φ⁻¹((rank − 0.5)/n), 동점은 평균 순위."""
    return pd.Series(norm.ppf((x.rank(method="average") - 0.5) / len(x)), index=x.index)


def winsor(x: pd.Series, lo=0.01, hi=0.99) -> pd.Series:
    return x.clip(x.quantile(lo), x.quantile(hi))


def signal_days(days: pd.DatetimeIndex, start: str, end: str) -> list[pd.Timestamp]:
    """2절: 매주 마지막 거래일. days 는 거래일 전체여야 한다(주 경계 판정용)."""
    s = pd.Series(days, index=days)
    iso = days.isocalendar()
    last = s.groupby([iso["year"].values, iso["week"].values]).max()
    return [d for d in last.sort_values() if pd.Timestamp(start) <= d <= pd.Timestamp(end)]


def cross_sections(wide: dict, ind: dict, master: pd.DataFrame, sectors: pd.DataFrame, sigs: list,
                   W: int, groups=("FOR", "INST")) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """신호일마다 6절 적용 순서대로 필터 → 지표 → 은밀성 회귀 → 표준화 → 점수.
    반환: (점수 긴 표, 기준 시장 종목 표, 필터 단계별 종목 수)."""
    days = wide["exists"].index
    cal = calendar().index
    lpos = list_pos(master, cal).reindex(wide["exists"].columns)
    # 신호일 행만 남긴 파생 값 (전체 행렬을 오래 들고 있지 않도록)
    hs = half_spread(wide).loc[sigs]
    ac = wide["adj_close"].ffill()
    mom = (ac.shift(21) / ac.shift(252) - 1).loc[sigs]
    rev = (ac / ac.shift(20) - 1).loc[sigs]
    del ac
    turn = (wide["value"].rolling(W_MAIN, min_periods=1).mean() / wide["mktcap"]).loc[sigs]
    sec = sectors.set_index(["date", "code"])["sector"]
    scores, bench, counts = [], [], []
    for t in sigs:
        j = days.get_loc(t)
        at = lambda f: f.loc[t]  # noqa: E731  (t일 행만 읽는다)
        cnt = {"date": t}
        sec_t = sec.xs(t, level="date") if t in sec.index.get_level_values("date") else pd.Series(dtype=object)
        ok = at(wide["exists"]) == 1
        cnt["상장·정적조건"] = int(ok.sum())
        ok &= (at(wide["halted"]) == 0) & (at(wide["in_liq"]) == 0)
        cnt["거래정지·정리매매 제외"] = int(ok.sum())
        ok &= (cal.get_loc(t) - lpos) >= MIN_AGE
        cnt["상장 252일"] = int(ok.sum())
        ok &= at(ind["liq"]) >= LIQ_MIN
        cnt["유동성"] = int(ok.sum())
        bench.append(pd.DataFrame({"date": t, "j": j, "code": ok.index[ok]}))
        ok &= at(ind["N"]) >= MIN_TRADED * W
        cnt["창 거래일 80%"] = int(ok.sum())

        base = pd.DataFrame({
            "CAR": at(ind["CAR"]), "mktcap": at(wide["mktcap"]), "kosdaq": at(wide["kosdaq"]),
            "MOM": at(mom), "REV": at(rev), "TURN": at(turn), "hs": at(hs)})
        base["SIZE"] = np.log(base["mktcap"])
        for g in groups:
            src = g.removesuffix("_NOSC")  # FOR_NOSC = 숏커버링 필터만 뺀 FOR (8.5절 보조 분석)
            keep = ok & (at(ind[f"{src}_part"]) >= PART_MIN)
            cnt[f"{g} 참여율"] = int(keep.sum())
            if g == "FOR":
                sn, dl = at(ind["FOR_sumnet"]), at(ind["dloan"])
                avail = (at(wide["loan_avail"]) == 1) & dl.notna()
                sc = avail & (sn > 0) & (-dl >= SC_RATIO * sn)  # 부록 A-2: 대차 기록이 없으면 필터 미적용
                keep &= ~sc
                cnt["FOR 숏커버링"] = int(keep.sum())
            d = base[keep].copy()
            for x in ("C", "P", "S"):
                d[x] = at(ind[f"{src}_{x}"])[keep]
            d = d.dropna(subset=["C", "P", "S", "CAR"])
            cnt[f"{g} 최종"] = len(d)
            if len(d) < NQ:
                continue
            s, c = winsor(d["S"]), winsor(d["C"])
            b = np.polyfit(c, s, 1)
            d["Stilde"] = -(s - np.polyval(b, c))
            d["score"] = rank_z(d["C"]) + rank_z(d["P"]) + rank_z(d["Stilde"]) - rank_z(d["CAR"])
            d["group"], d["date"], d["j"] = g, t, j
            d["sector"] = d.index.map(sec_t)
            scores.append(d.rename_axis("code").reset_index())
        counts.append(cnt)
    return (pd.concat(scores, ignore_index=True), pd.concat(bench, ignore_index=True), pd.DataFrame(counts))


class Engine:
    """7절 수익률. 신호일 위치 j 의 종목들을 j+lag 일 시가에 동일 가중으로 사서 hold 거래일 보유(매수 후 보유).
    진입일 수익률은 수정 시가 → 수정 종가, 이후는 일간 수정 수익률. 보유 중 거래정지·상장폐지 뒤의 날은
    수익률 0 (마지막 가격 유지 = 4.1절 청산 규칙). 진입일에 시가가 없으면(정지) 그 종목은 매수하지 않는다."""

    def __init__(self, wide: dict, hold: int = HOLD):
        self.days = wide["exists"].index
        self.codes = wide["exists"].columns
        self.col = pd.Series(np.arange(len(self.codes)), index=self.codes)
        self.ret = wide["ret"].to_numpy(dtype="float64")
        self.aopen = wide["adj_open"].to_numpy(dtype="float64")
        self.aclose = wide["adj_close"].to_numpy(dtype="float64")
        self.hold = hold
        cal = calendar().index
        tax = pd.read_csv(CLEAN / "ref" / "tax_rates.csv", parse_dates=["settle_from", "settle_to"])
        settle = cal[np.minimum(cal.searchsorted(self.days) + 2, len(cal) - 1)]  # 결제일 = 체결일 + 2거래일
        self.tax = np.array([tax.loc[(tax.settle_from <= s) & (s <= tax.settle_to), "kospi_total"].iloc[0] / 100
                             for s in settle])

    def paths(self, j: int, codes, lag: int = 1):
        """누적 가치 G (hold × 매수 가능 종목)와 그 종목 위치."""
        e = j + lag
        assert e > j, "진입일은 신호일 다음 거래일 이후여야 한다 (10절 4번)"
        if e + self.hold > len(self.days):
            return None, None
        idx = self.col.reindex(codes).dropna().to_numpy().astype(int)
        ao, ac = self.aopen[e, idx], self.aclose[e, idx]
        with np.errstate(invalid="ignore", divide="ignore"):
            r0 = np.where(ao > 0, ac / ao - 1, np.nan)
        ok = np.isfinite(r0)
        R = np.vstack([r0[ok], np.nan_to_num(self.ret[e + 1:e + self.hold][:, idx[ok]])])
        return np.cumprod(1 + R, axis=0), idx[ok]

    def stock_returns(self, j: int, codes, lag: int = 1) -> pd.Series:
        """7.1절 R_{i,t} = Close_{t+20}/Open_{t+1} − 1."""
        G, idx = self.paths(j, codes, lag)
        if G is None:
            return pd.Series(dtype=float)
        return pd.Series(G[-1] - 1, index=self.codes[idx])

    def sale_tax(self, j: int, lag: int = 1) -> float:
        """7.4절 τ_t: 보유 마지막 거래일(j+lag+hold−1)에 판 주식의 결제일 세율."""
        return float(self.tax[min(j + lag + self.hold - 1, len(self.tax) - 1)])


def signal_returns(d: pd.DataFrame, key: str, fee: float = FEE, slip: float | None = None) -> pd.DataFrame:
    """7.3·7.4절: 신호일 × key(분위 등) 단위의 동일 가중 수익률. d 는 종목 행(R, Rex, Rbar, hs, tax 포함).
    반환 열: R(비용 전), Rex(비용 전 초과), cost(왕복 비용 2c + τ + 2s̄), n(종목 수).
    slip 을 주면 Abdi–Ranaldo 대신 고정 반스프레드. 진입일 정지로 R 이 없는 종목은 뺀다."""
    d = d.dropna(subset=["R"])
    g = d.groupby(["date", key])
    out = g.agg(R=("R", "mean"), Rex=("Rex", "mean"), hs=("hs", "mean"), tax=("tax", "first"), n=("code", "size"))
    out["cost"] = 2 * fee + out["tax"] + 2 * (out["hs"] if slip is None else slip)
    return out


def nonoverlap_curve(r: pd.Series, step: int) -> pd.Series:
    """8.1절 1항 누적 곡선: step 신호일 간격으로 떨어진 신호일만 이어 붙인 누적 가치를, 가능한 시작점 step 개에
    대해 평균한다(시작점마다 날짜가 달라서 합집합 날짜에서 앞의 값을 이어 쓴 뒤 평균). r 은 신호일 순서."""
    r = r.dropna().sort_index()
    curves = [(1 + r.iloc[k::step]).cumprod() for k in range(step)]
    idx = r.index
    return pd.concat([c.reindex(idx).ffill().fillna(1.0) for c in curves], axis=1).mean(axis=1)


def nw_t(x, lag: int = NW_LAG) -> tuple[float, float, int]:
    """평균, Newey–West(Bartlett 커널) t-통계량, 관측 수."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < lag + 2:
        return np.nan, np.nan, n
    m = x.mean()
    e = x - m
    v = e @ e / n
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (e[l:] @ e[:-l]) / n
    return m, m / np.sqrt(v / n), n


def max_drawdown(v: pd.Series) -> float:
    """누적 가치 곡선의 최대 낙폭."""
    return float((v / v.cummax() - 1).min())


def decile_monotonic(means: pd.Series) -> float:
    """8.1절 3: 분위 평균 수익률과 분위 번호의 스피어만 상관."""
    return float(spearmanr(means.index, means.values).statistic)


def fama_macbeth(df: pd.DataFrame, use_industry: bool = True) -> tuple[pd.DataFrame, int]:
    """8.2절 (2): 신호일별 R_ex ~ Score + MOM + REV + SIZE + TURN (+ 업종 더미).
    통제 변수는 신호일별 1·99% 절단 후 순위 표준화. 관측이 열 수 + 5 이하이면 업종 더미를 빼고 그 횟수를 센다."""
    rows, dropped = [], 0
    for t, d in df.dropna(subset=["Rex", "score", "MOM", "REV", "SIZE", "TURN"]).groupby("date"):
        X = pd.DataFrame({"const": 1.0, "score": d["score"]}, index=d.index)
        for v in ("MOM", "REV", "SIZE", "TURN"):
            X[v] = rank_z(winsor(d[v]))
        if use_industry:
            dum = pd.get_dummies(d["sector"].fillna("NA"), drop_first=True, dtype=float)
            if len(d) > X.shape[1] + dum.shape[1] + 5:
                X = pd.concat([X, dum], axis=1)
            else:
                dropped += 1
        if len(d) <= X.shape[1] + 1:
            continue
        coef = np.linalg.lstsq(X.to_numpy(), d["Rex"].to_numpy(), rcond=None)[0]
        rows.append({"date": t, **dict(zip(X.columns[:6], coef[:6]))})
    return pd.DataFrame(rows), dropped
