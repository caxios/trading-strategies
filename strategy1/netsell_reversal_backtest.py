"""투자주체(외국인·기관·개인)별 순매수/순매도 상위 종목의 이후 수익률 백테스트.

가설: 기관·외국인의 매도가 정보 없는 매도(리밸런싱, 환매, 바스켓 매도 등)라면
      매도로 빠진 가격은 이후 되돌아온다 → 순매도 상위 종목의 이후 초과수익률 > 0.

fetch_investor_history.py 가 받은 data/history/ 를 읽어서
  1) 매일 투자자(외국인/기관/개인) × 시장별 순매수·순매도 상위 N 종목(신호)을 뽑고
  2) 신호일 종가에 산 것으로 보고 이후 1·5·10·20·60·120·240·480(≈2년) 영업일 수익률을 계산한 뒤
  3) 매도의 성격을 가르는 조건별로 나눠 비교한다.

순위 기준 (--rank):
  금액 : 순매수거래대금 (대형주 위주)
  비율 : 순매수거래대금 / 시가총액 (시총 --min-cap 억 이상만, 종목 크기 대비 매도 강도)

조건:
  당일가격   : 신호일 초과수익률 < 0 (매도와 함께 가격이 빠짐) / >= 0
  업종       : 같은 업종(그 종목 제외)도 같은 주체가 순매도 / 순매수 — 업종 바스켓 매도인지
  시장전체   : 그날 그 주체가 시장 전체로 순매도 / 순매수 — 시장 단위 자금 이탈인지
  연속매도   : 신호일까지 그 주체가 그 종목을 연속 순매도한 일수
  진입시점   : 신호일 종가 즉시 / 매도가 멈춘 날(그 주체 순매수 >= 0, 10일 이내) 종가
  기간       : 전반 / 후반 (결과가 기간에 따라 뒤집히는지)

수익률은 KRX 공식 등락률을 복리로 누적, 시장평균은 같은 시장 전 종목 단순평균(거래정지 제외).
t값은 날짜별 평균 초과수익률의 시계열로 계산하고, 보유기간이 겹치는 문제는 Newey-West(시차 h-1)로 보정.

출력:
  data/netsell_reversal_signals.csv.gz : 신호 단위 상세
  data/netsell_reversal_summary.csv    : 조건별 요약

사용 예:
    python netsell_reversal_backtest.py
    python netsell_reversal_backtest.py --top 30 --min-cap 5000
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
HIST = ROOT / "data" / "history"
INVESTORS = ["외국인", "기관", "개인"]
HORIZONS = [1, 5, 10, 20, 60, 120, 240, 480]  # 480 영업일 ≈ 2년
SHOW_COND = [1, 5, 20, 60, 240]  # 조건별 표에 출력할 보유기간
STOP_WAIT = 10  # 매도 멈춤을 기다리는 최대 영업일


# ---------------------------------------------------------------- 데이터 로드
def load(kind: str) -> pd.DataFrame:
    files = sorted(HIST.glob(f"{kind}_*.csv.gz"))
    if not files:
        raise SystemExit(f"{HIST} 에 {kind} 파일이 없습니다. fetch_investor_history.py 를 먼저 실행하세요.")
    return pd.concat(
        [pd.read_csv(f, dtype={"종목코드": str}).assign(일자=f.name.split("_")[1][:8]) for f in files],
        ignore_index=True)


def load_sectors() -> pd.Series:
    f = max(HIST.glob("sectors_*.csv"))
    s = pd.read_csv(f, dtype={"종목코드": str}, encoding="utf-8-sig")
    return s.set_index("종목코드")["업종명"]


# ---------------------------------------------------------------- 수익률
def return_panel(px: pd.DataFrame):
    """일자 × 종목 수익률, 상장 여부, 시장별 평균 → 누적 로그수익률."""
    px = px.copy()
    px["수익률"] = np.where(px["거래량"] > 0, px["등락률"] / 100, np.nan)
    days = sorted(px["일자"].unique())
    R = px.pivot(index="일자", columns="종목코드", values="수익률").reindex(days)
    listed = px.pivot(index="일자", columns="종목코드", values="종가").reindex(days).notna()
    M = px.groupby(["일자", "시장"])["수익률"].mean().unstack().reindex(days)
    LR = np.log1p(R.fillna(0)).cumsum()   # 거래정지일은 0%
    LM = np.log1p(M.fillna(0)).cumsum()
    return days, R, M, LR, LM, listed


def forward_excess(sig: pd.DataFrame, entry_col: str, LR, LM, listed, prefix: str) -> pd.DataFrame:
    """entry_col(일자 인덱스 위치) 종가 진입 → h일 뒤 종가까지 종목/시장 누적수익률과 초과수익률."""
    n = len(LR)
    col = LR.columns.get_indexer(sig["종목코드"])
    mcol = LM.columns.get_indexer(sig["시장"])
    lr, lm, ls = LR.to_numpy(), LM.to_numpy(), listed.to_numpy()
    e = sig[entry_col].to_numpy()
    ok_e = (e >= 0) & (col >= 0)
    for h in HORIZONS:
        x = e + h
        ok = ok_e & (x < n)
        xi, ei, ci, mi = np.where(ok, x, 0), np.where(ok, e, 0), np.where(ok, col, 0), np.where(ok, mcol, 0)
        ok &= ls[xi, ci]  # h일 뒤에도 상장되어 있어야 함
        stock_r = np.expm1(lr[xi, ci] - lr[ei, ci])
        mkt_r = np.expm1(lm[xi, mi] - lm[ei, mi])
        sig[f"{prefix}초과_{h}d"] = np.where(ok, stock_r - mkt_r, np.nan)
        sig[f"{prefix}수익_{h}d"] = np.where(ok, stock_r, np.nan)
    return sig


# ---------------------------------------------------------------- 신호와 조건
def flow_matrix(nb: pd.DataFrame, investor: str, days) -> pd.DataFrame:
    g = nb[nb["투자자"] == investor]
    return g.pivot(index="일자", columns="종목코드", values="순매수거래대금").reindex(days).fillna(0)


def streak_and_stop(N: pd.DataFrame):
    """연속 순매도 일수, 다음으로 순매수>=0 인 날의 위치."""
    a = N.to_numpy()
    neg = a < 0
    streak = np.zeros_like(a, dtype=int)
    for i in range(len(a)):
        streak[i] = (streak[i - 1] + 1) * neg[i] if i else neg[i]
    nxt = np.full_like(a, -1, dtype=int)
    for i in range(len(a) - 2, -1, -1):
        nxt[i] = np.where(~neg[i + 1], i + 1, nxt[i + 1])
    return streak, nxt


def build_signals(nb, px, sectors, days, top, min_cap) -> pd.DataFrame:
    day_idx = {d: i for i, d in enumerate(days)}
    cap = px.set_index(["일자", "종목코드"])["시가총액"]
    nb = nb[nb["투자자"].isin(INVESTORS)].copy()
    nb["시가총액"] = cap.reindex(list(zip(nb["일자"], nb["종목코드"]))).to_numpy()
    nb["비율"] = nb["순매수거래대금"] / nb["시가총액"]
    nb["업종명"] = nb["종목코드"].map(sectors).fillna("미분류")

    # 업종(본인 제외) / 시장 전체 같은 주체 순매수
    sec_sum = nb.groupby(["일자", "시장", "투자자", "업종명"])["순매수거래대금"].transform("sum")
    nb["업종순매수_본인제외"] = sec_sum - nb["순매수거래대금"]
    nb["시장순매수"] = nb.groupby(["일자", "시장", "투자자"])["순매수거래대금"].transform("sum")

    frames = []
    for rank in ["금액", "비율"]:
        pool = nb if rank == "금액" else nb[nb["시가총액"] >= min_cap * 1e8]
        key = "순매수거래대금" if rank == "금액" else "비율"
        g = pool.sort_values(key).groupby(["일자", "시장", "투자자"], sort=False)
        sell = g.head(top).assign(그룹="순매도")
        buy = pool.sort_values(key, ascending=False).groupby(["일자", "시장", "투자자"], sort=False).head(top)
        buy = buy[buy["순매수거래대금"] > 0].assign(그룹="순매수")
        sell = sell[sell["순매수거래대금"] < 0]
        frames.append(pd.concat([sell, buy]).assign(순위기준=rank))
    sig = pd.concat(frames, ignore_index=True)
    sig["t"] = sig["일자"].map(day_idx)

    # 연속매도 / 매도 멈춤 시점 (주체별 행렬로 계산 후 신호에 매핑)
    sig["연속매도일수"], sig["멈춤t"] = 0, -1
    for inv in INVESTORS:
        N = flow_matrix(nb, inv, days)
        streak, nxt = streak_and_stop(N)
        m = sig["투자자"] == inv
        c = N.columns.get_indexer(sig.loc[m, "종목코드"])
        t = sig.loc[m, "t"].to_numpy()
        sig.loc[m, "연속매도일수"] = streak[t, c]
        sig.loc[m, "멈춤t"] = nxt[t, c]
    wait = sig["멈춤t"] - sig["t"]
    sig.loc[(sig["멈춤t"] < 0) | (wait > STOP_WAIT), "멈춤t"] = -1
    sig["멈춤대기일"] = np.where(sig["멈춤t"] >= 0, wait, np.nan)
    return sig


# ---------------------------------------------------------------- 통계
def nw_tstat(x: np.ndarray, lag: int) -> float:
    """Newey-West t값 (겹치는 보유기간 보정)."""
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 10:
        return np.nan
    d = x - x.mean()
    var = d @ d / n
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1)) * (d[k:] @ d[:-k]) / n
    return x.mean() / np.sqrt(var / n) if var > 0 else np.nan


def stats(g: pd.DataFrame, prefix: str) -> dict:
    out = {"신호수": len(g), "일수": g["일자"].nunique(),
           "당일초과": g["당일초과"].mean(), "t_당일": nw_tstat(g.groupby("일자")["당일초과"].mean().to_numpy(), 0)}
    for h in HORIZONS:
        c = f"{prefix}초과_{h}d"
        v = g[c].dropna()
        daily = g.groupby("일자")[c].mean().sort_index().to_numpy()
        out[f"평균_{h}d"] = v.mean()
        out[f"중앙값_{h}d"] = v.median()
        out[f"수익_{h}d"] = g[f"{prefix}수익_{h}d"].mean()
        out[f"표본일수_{h}d"] = g.loc[g[c].notna(), "일자"].nunique()
        out[f"승률_{h}d"] = (v > 0).mean()
        out[f"t_{h}d"] = nw_tstat(daily, h - 1)
    return out


def conditions(sig: pd.DataFrame, half: str):
    """(조건명, 값, 마스크, 진입 prefix) 목록."""
    s = sig
    yield "전체", "", s.index == s.index, "즉시"
    yield "시장", "KOSPI", s["시장"] == "KOSPI", "즉시"
    yield "시장", "KOSDAQ", s["시장"] == "KOSDAQ", "즉시"
    yield "당일가격", "하락(초과<0)", s["당일초과"] < 0, "즉시"
    yield "당일가격", "상승(초과>=0)", s["당일초과"] >= 0, "즉시"
    yield "업종", "업종 동반 순매도", s["업종순매수_본인제외"] < 0, "즉시"
    yield "업종", "그 종목만 순매도", s["업종순매수_본인제외"] >= 0, "즉시"
    yield "시장전체", "주체가 시장 순매도", s["시장순매수"] < 0, "즉시"
    yield "시장전체", "주체가 시장 순매수", s["시장순매수"] >= 0, "즉시"
    yield "연속매도", "1일", s["연속매도일수"] == 1, "즉시"
    yield "연속매도", "2~4일", s["연속매도일수"].between(2, 4), "즉시"
    yield "연속매도", "5일 이상", s["연속매도일수"] >= 5, "즉시"
    yield "업종+가격", "업종 동반 & 가격 하락", (s["업종순매수_본인제외"] < 0) & (s["당일초과"] < 0), "즉시"
    yield "업종+가격", "단독 & 가격 하락", (s["업종순매수_본인제외"] >= 0) & (s["당일초과"] < 0), "즉시"
    yield "진입시점", "즉시(신호일 종가)", s["멈춤t"] >= 0, "즉시"  # 같은 표본으로 비교
    yield "진입시점", "매도 멈춘 날 종가", s["멈춤t"] >= 0, "멈춤"
    yield "기간", f"전반(~{half})", s["일자"] <= half, "즉시"
    yield "기간", f"후반({half}~)", s["일자"] > half, "즉시"


def summarize(sig: pd.DataFrame, days) -> pd.DataFrame:
    half = days[len(days) // 2]
    rows = []
    for (rank, inv, grp), g in sig.groupby(["순위기준", "투자자", "그룹"], sort=False):
        conds = conditions(g, half) if grp == "순매도" else [("전체", "", g.index == g.index, "즉시")]
        for name, val, mask, entry in conds:
            rows.append({"순위기준": rank, "투자자": inv, "그룹": grp, "조건": name, "값": val,
                         **stats(g[mask], "즉시" if entry == "즉시" else "멈춤")})
    return pd.DataFrame(rows)


def print_summary(s: pd.DataFrame, top: int):
    pct = lambda v: "" if pd.isna(v) else f"{v * 100:+.2f}%"  # noqa: E731
    tv = lambda v: "" if pd.isna(v) else f"({v:+.1f})"  # noqa: E731

    # 1) 기본표: 순매수/순매도 상위 전체, 모든 보유기간
    base = s[s["조건"] == "전체"]
    for rank, g in base.groupby("순위기준", sort=False):
        print(f"\n=== {rank} 기준 상위 {top} 전체  (위: 시장 대비 초과수익률 평균(t값) / 아래: 중앙값, 절대수익률 평균)")
        rows = []
        for _, r in g.iterrows():
            rows.append([f"{r['투자자']} {r['그룹']}", "평균(t)", f"{pct(r['당일초과'])}{tv(r['t_당일'])}",
                         *[f"{pct(r[f'평균_{h}d'])}{tv(r[f't_{h}d'])}" for h in HORIZONS]])
            rows.append(["", "중앙값", "", *[pct(r[f"중앙값_{h}d"]) for h in HORIZONS]])
            rows.append(["", "절대수익", "", *[pct(r[f"수익_{h}d"]) for h in HORIZONS]])
        cols = ["구분", "", "당일", *[f"{h}일" for h in HORIZONS]]
        print(pd.DataFrame(rows, columns=cols).to_string(index=False))
        print("표본일수: " + ", ".join(f"{h}일 {int(g[f'표본일수_{h}d'].iloc[0])}" for h in HORIZONS))

    # 2) 순매도 조건별 (금액 기준만, 일부 보유기간)
    cond = s[(s["그룹"] == "순매도") & (s["순위기준"] == "금액") & (s["조건"] != "전체")]
    for inv, g in cond.groupby("투자자", sort=False):
        print(f"\n=== {inv} 순매도 상위 {top} 조건별 (금액 기준, 초과수익률 평균(t값))")
        rows = [[f"{r['조건']}: {r['값']}", f"{r['신호수']:,}",
                 *[f"{pct(r[f'평균_{h}d'])}{tv(r[f't_{h}d'])}" for h in SHOW_COND]] for _, r in g.iterrows()]
        print(pd.DataFrame(rows, columns=["조건", "신호수", *[f"{h}일" for h in SHOW_COND]]).to_string(index=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--min-cap", type=float, default=3000, help="비율 기준 최소 시가총액(억)")
    args = p.parse_args()

    nb, px, sectors = load("netbuy"), load("ohlcv"), load_sectors()
    days, R, M, LR, LM, listed = return_panel(px)
    print(f"기간 {days[0]}~{days[-1]} {len(days)}영업일, 종목 {R.shape[1]:,}개")

    sig = build_signals(nb, px, sectors, days, args.top, args.min_cap)
    rr = R.stack()
    sig["당일수익률"] = rr.reindex(list(zip(sig["일자"], sig["종목코드"]))).to_numpy()
    sig["당일초과"] = sig["당일수익률"] - M.stack().reindex(list(zip(sig["일자"], sig["시장"]))).to_numpy()
    sig = forward_excess(sig, "t", LR, LM, listed, "즉시")
    sig = forward_excess(sig, "멈춤t", LR, LM, listed, "멈춤")

    summary = summarize(sig, days)
    (ROOT / "data").mkdir(exist_ok=True)
    cols = ["순위기준", "일자", "시장", "투자자", "그룹", "종목코드", "종목명", "업종명", "순매수거래대금", "시가총액",
            "비율", "당일수익률", "당일초과", "업종순매수_본인제외", "시장순매수", "연속매도일수", "멈춤대기일",
            *[f"{p}{k}_{h}d" for p in ["즉시", "멈춤"] for k in ["초과", "수익"] for h in HORIZONS]]
    sig[cols].to_csv(ROOT / "data" / "netsell_reversal_signals.csv.gz", index=False, encoding="utf-8-sig")
    summary.to_csv(ROOT / "data" / "netsell_reversal_summary.csv", index=False, encoding="utf-8-sig")

    print_summary(summary, args.top)
    print("\n※ 순매도 '진입시점' 두 줄은 10일 안에 매도가 멈춘 같은 신호들만 비교 (멈춤 진입은 그날 종가부터 h일)")
    print("저장: data/netsell_reversal_signals.csv.gz, data/netsell_reversal_summary.csv")


if __name__ == "__main__":
    main()
