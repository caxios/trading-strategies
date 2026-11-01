"""strategy2 연구계획서 4절: 원본(data/ 하위 폴더)에서 정제 패널(data/clean/)을 새로 만든다.

원본은 읽기만 한다. 출력:
  data/clean/panel_YYYY.parquet : 일 × 종목 패널 (시세, 수정 수익률, 투자주체별 거래, 대차잔고, 업종)
  data/clean/master.csv          : 종목별 속성 (첫·마지막 거래일, 상장일, 종목 구분, 정리매매 시작일, 연속 이력 ID)
  data/clean/index_ret.csv       : KOSPI·KOSDAQ 일간 수익률
  data/clean/earnings_dates.csv  : 실적 발표일 (잠정실적 공정공시, 없으면 정기보고서)
  data/clean/ref/*.csv           : 증권거래세율, 공매도 금지 기간
  strategy2/logs/ticker_mapping.csv, strategy2/logs/clean_report.md

규칙의 근거는 strategy2/logs/assumptions.md 에 적는다.
메모리가 적은 환경이라 연도별로 나눠 처리한다.

사용 예:
    python strategy2/code/build_clean.py
"""
import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "clean"
LOGS = ROOT / "strategy2" / "logs"
END = "20261022"
PX_DIRS = ("ohlcv", "lookback", "history")
GROUPS = {"외국인": "FRGN", "기타외국인": "OFRGN", "연기금": "PENS", "투신": "IVTR"}
FLOW_COLS = [f"{g}_{k}" for g in GROUPS.values() for k in ("buy", "sell", "net")]
CHG_TOL = 0.006  # 종가로 계산한 수익률과 등락률이 이만큼 넘게 다르면 기준가 조정일로 보고 등락률을 쓴다
LOAN_FIRST_DELISTED = "20160128"  # KIS 대차 데이터가 있는 상폐 종목 중 가장 이른 마지막 날짜
LINK_GAP_DAYS = 10  # 이 거래일 수 안에 같은 이름으로 새 코드가 나타나면 같은 회사로 연결
LOAN_IDS: dict[str, int] = {}


def norm_name(s: str) -> str:
    return re.sub(r"\s+|\(주\)|㈜|주식회사", "", str(s))


def px_files() -> dict[str, Path]:
    """날짜 → 시세 파일. 같은 날짜가 여러 폴더에 있으면 앞 폴더 우선."""
    out = {}
    for d in reversed(PX_DIRS):
        for f in (DATA / d).glob("ohlcv_*.csv.gz"):
            out[f.name[6:14]] = f
    return dict(sorted(out.items()))


def read_px(day: str, f: Path) -> pd.DataFrame:
    t = pd.read_csv(f, dtype={"종목코드": str})
    t = t.rename(columns={"시장": "market", "종목코드": "code", "시가": "open", "고가": "high", "저가": "low",
                          "종가": "close", "거래량": "volume", "거래대금": "value", "등락률": "chg_pct",
                          "시가총액": "mktcap"})
    t.insert(0, "date", pd.Timestamp(day))
    return t


def read_flow(day: str) -> pd.DataFrame:
    """그날 투자주체별 매수·매도·순매수 (원). 외국인은 2024-10-22 이후 data/history/netbuy 에서."""
    parts = [pd.read_csv(DATA / "flow" / f"flow_{day}.csv.gz", dtype={"종목코드": str})]
    nb = DATA / "history" / f"netbuy_{day}.csv.gz"
    if nb.exists():
        h = pd.read_csv(nb, dtype={"종목코드": str})
        parts.append(h[h["투자자"] == "외국인"])
    f = pd.concat(parts, ignore_index=True)
    f = f[f["투자자"].isin(GROUPS)]
    f = f.assign(g=f["투자자"].map(GROUPS)).rename(columns={"종목코드": "code", "매수거래대금": "buy",
                                                            "매도거래대금": "sell", "순매수거래대금": "net"})
    w = f.pivot_table(index="code", columns="g", values=["buy", "sell", "net"], aggfunc="sum")
    w.columns = [f"{g}_{k}" for k, g in w.columns]
    return w.reindex(columns=FLOW_COLS)


def build_loan_long() -> tuple[pd.DataFrame, set, set]:
    """대차 원본 → (date, cid, loan_shares, loan_bal 원). 빈 파일 코드와 받은 코드 집합도 돌려준다.
    메모리를 아끼려고 종목코드 대신 정수 cid(LOAN_IDS) 로 저장한다."""
    frames, empty, have = [], set(), set()
    for f in sorted((DATA / "loan").glob("loan_*.csv.gz")):
        code = f.name[5:11]
        have.add(code)
        t = pd.read_csv(f, dtype={"일자": str})
        if t.empty:
            empty.add(code)
            continue
        LOAN_IDS[code] = len(LOAN_IDS)
        frames.append(pd.DataFrame({"date": pd.to_datetime(t["일자"]), "cid": np.int32(LOAN_IDS[code]),
                                    "loan_shares": t["잔고주수"].astype("float64"),
                                    "loan_bal": t["잔고금액_백만원"].astype("float64") * 1e6}))
    return pd.concat(frames, ignore_index=True), empty, have


def sector_table() -> pd.DataFrame:
    rows = []
    for f in sorted((DATA / "sectors").glob("sectors_*.csv.gz")):
        t = pd.read_csv(f, dtype={"종목코드": str}, usecols=["종목코드", "업종명"])
        t["snap"] = pd.Timestamp(f.name[8:16])
        rows.append(t.rename(columns={"종목코드": "code", "업종명": "sector"}))
    # KRX 스냅샷에 한 종목이 두 업종으로 나오는 경우가 있다(예: 2014-01 솔본) → 먼저 나온 업종 하나만 쓴다
    return pd.concat(rows, ignore_index=True).drop_duplicates(["snap", "code"]).sort_values("snap")


def dart_list(kind: str) -> pd.DataFrame:
    d = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(str(DATA / "dart" / "list" / f"{kind}_*.csv.gz")))],
                  ignore_index=True)
    d["nm"] = d["report_nm"].str.replace(r"\s+", "", regex=True)
    return d.dropna(subset=["stock_code"])


# ---------------------------------------------------------------- 1차 패스: 종목별 속성
def pass_master(files: dict[str, Path]) -> pd.DataFrame:
    recs = {}
    for day, f in files.items():
        t = pd.read_csv(f, dtype={"종목코드": str}, usecols=["시장", "종목코드"])
        for code, mkt in zip(t["종목코드"], t["시장"]):
            r = recs.get(code)
            if r is None:
                recs[code] = [day, day, mkt, mkt, 1, [(day, mkt)]]
            else:
                r[1] = day
                r[4] += 1
                if mkt != r[3]:
                    r[5].append((day, mkt))
                r[3] = mkt
    m = pd.DataFrame([(c, *v[:5], v[5]) for c, v in recs.items()],
                     columns=["code", "first_date", "last_date", "market_first", "market_last", "n_days", "mkt_hist"])
    return m


def classify(m: pd.DataFrame) -> pd.DataFrame:
    lb = pd.read_csv(DATA / "master" / "listed_basic_20261030.csv", dtype=str)
    lb = lb.set_index("ISU_SRT_CD")
    dl = pd.read_csv(DATA / "master" / "delisted_list.csv", dtype=str).drop_duplicates("short_code").set_index("short_code")
    m["name"] = m["code"].map(lb["ISU_ABBRV"]).fillna(m["code"].map(dl["codeName"]))
    m["secu_grp"] = m["code"].map(lb["SECUGRP_NM"])
    m["kind"] = m["code"].map(lb["KIND_STKCERT_TP_NM"])
    m["list_date"] = pd.to_datetime(m["code"].map(lb["LIST_DD"]), format="%Y/%m/%d", errors="coerce")
    m["list_date_src"] = np.where(m["list_date"].notna(), "listed_basic", None)
    no_ld = m["list_date"].isna() & (m["first_date"] > "20140102")
    m.loc[no_ld, "list_date"] = pd.to_datetime(m.loc[no_ld, "first_date"])
    m.loc[no_ld, "list_date_src"] = "first_trade"
    m.loc[m["list_date"].isna(), "list_date_src"] = "before_20140102"
    nm = m["name"].fillna("")
    m["is_pref"] = ~m["code"].str.endswith("0") | m["kind"].isin(["구형우선주", "신형우선주", "종류주권"])
    # 상폐 종목은 증권구분이 없어 이름으로 판정한다(파일럿에서 발견). "N호"로 끝나는 이름은 KOSDAQ 이면 이름이 잘린 스팩,
    # KOSPI 이면 선박·부동산·자원 펀드(동북아N호, 아시아N호, 바다로N호, 하이골드N호, 코크렙N호, 트러스제7호 등)
    numbered = nm.str.contains(r"\d+호$") & m["secu_grp"].isna()
    m["is_spac"] = nm.str.contains("스팩|기업인수목적") | (numbered & (m["market_first"] == "KOSDAQ"))
    m["is_reit_fund"] = (m["secu_grp"].isin(["부동산투자회사", "투자회사", "사회간접자본투융자회사"])
                         | nm.str.contains("리츠|인프라|선박|맥쿼리|유전|베트남개발")
                         | (numbered & (m["market_first"] == "KOSPI")))
    m["is_foreign"] = m["code"].str.startswith("9") | m["secu_grp"].isin(["외국주권", "주식예탁증권"])
    m["delisted"] = m["last_date"] < END
    return m


def link_codes(m: pd.DataFrame, days: list[str]) -> pd.DataFrame:
    """같은 이름으로 LINK_GAP_DAYS 거래일 안에 새 코드가 생기면 같은 회사로 본다 (계획서 4.2절)."""
    pos = {d: i for i, d in enumerate(days)}
    m["nname"] = m["name"].map(norm_name)
    ended = m[m["delisted"]]
    started = m[m["first_date"] > days[0]]
    by_name = started.groupby("nname")
    rows = []
    for _, a in ended.iterrows():
        if a["nname"] not in by_name.groups:
            continue
        for _, b in by_name.get_group(a["nname"]).iterrows():
            gap = pos[b["first_date"]] - pos[a["last_date"]]
            if b["code"] != a["code"] and 0 < gap <= LINK_GAP_DAYS:
                rows.append({"old_code": a["code"], "new_code": b["code"], "name": a["name"],
                             "old_last": a["last_date"], "new_first": b["first_date"], "gap_days": gap,
                             "type": "code_change", "rule": f"같은 이름, {LINK_GAP_DAYS}거래일 이내 재등장"})
    links = pd.DataFrame(rows, columns=["old_code", "new_code", "name", "old_last", "new_first", "gap_days", "type", "rule"])
    perm = dict(zip(m["code"], m["code"]))
    for _, r in links.sort_values("new_first").iterrows():
        perm[r["new_code"]] = perm[r["old_code"]]
    m["perm_id"] = m["code"].map(perm)
    transfers = []
    for _, r in m.iterrows():
        for (d0, m0), (d1, m1) in zip(r["mkt_hist"][:-1], r["mkt_hist"][1:]):
            transfers.append({"old_code": r["code"], "new_code": r["code"], "name": r["name"], "old_last": days[pos[d1] - 1],
                              "new_first": d1, "gap_days": 0, "type": f"market_transfer {m0}->{m1}",
                              "rule": "같은 코드 유지, 시장만 변경"})
    return m, pd.concat([links, pd.DataFrame(transfers)], ignore_index=True)


def liquidation_start(m: pd.DataFrame, days: list[str]) -> pd.Series:
    """정리매매 시작일: '정리매매 개시/재개' 공시 다음 거래일. 마지막 거래일 전 20거래일 안의 공시만 인정."""
    d = dart_list("I")
    d = d[d["nm"].str.contains("정리매매") & d["nm"].str.contains("개시|재개")]
    pos = {x: i for i, x in enumerate(days)}
    last = m.set_index("code")["last_date"]
    out = {}
    for code, g in d.groupby("stock_code"):
        if code not in last.index or last[code] >= END:
            continue
        li = pos[last[code]]
        for r in sorted(g["rcept_dt"], reverse=True):
            nxt = next((x for x in days if x > r), None)
            if nxt and 0 <= li - pos[nxt] <= 20:
                out[code] = nxt
                break
    return pd.Series(out, dtype=object)


# ---------------------------------------------------------------- 2차 패스: 연도별 패널
def build_year(year: str, days: list[str], files: dict[str, Path], m: pd.DataFrame, loan: pd.DataFrame,
               loan_empty: set, loan_have: set, sectors: pd.DataFrame, carry: dict) -> dict:
    px = pd.concat([read_px(d, files[d]) for d in days], ignore_index=True)
    fl = []
    for d in days:
        w = read_flow(d)
        w["date"] = pd.Timestamp(d)
        fl.append(w.reset_index())
    px = px.merge(pd.concat(fl, ignore_index=True), on=["date", "code"], how="left")
    px = px.sort_values(["code", "date"]).reset_index(drop=True)

    px["halted"] = px["volume"] == 0
    traded = ~px["halted"]
    unmatched = int(px.loc[px["halted"], FLOW_COLS].notna().any(axis=1).sum())
    for c in FLOW_COLS:  # 거래가 있는데 투자자 행이 없으면 0, 거래정지일은 결측
        px[c] = px[c].where(px["halted"], px[c].fillna(0.0))
        px.loc[px["halted"], c] = np.nan

    # 수정 수익률: 앞 거래행 종가(거래정지 행의 종가는 직전 종가) 대비, 기준가 조정일은 등락률
    prev_close = px.groupby("code")["close"].shift(1)
    first_row = prev_close.isna()
    prev_close = prev_close.fillna(px["code"].map(carry["close"]))
    raw = px["close"] / prev_close - 1
    chg = px["chg_pct"] / 100
    use_chg = (raw - chg).abs() > CHG_TOL
    ret = raw.where(~use_chg, chg)
    new_listing = first_row & ~px["code"].isin(carry["close"].keys())
    ret[new_listing | px["halted"]] = np.nan
    px["ret"] = ret
    px["ret_from_chg"] = use_chg & traded & ~new_listing
    for c in ("open", "high", "low", "close"):  # 거래정지일 가격은 결측
        px[c + "_raw"] = px[c]
        px.loc[px["halted"], c] = np.nan
    px = px.drop(columns=["open_raw", "high_raw", "low_raw"])

    # 수정 종가 지수 (연도 간 이어 붙임), 수정 시가 = 시가 × 수정종가/종가
    lr = np.log1p(px["ret"].fillna(0.0))
    base = px["code"].map(carry["logidx"]).fillna(0.0)
    px["adj_close"] = np.exp(base + lr.groupby(px["code"]).cumsum())
    px["adj_open"] = px["open"] * px["adj_close"] / px["close"]

    # 대차잔고: 기록일 값, 없으면 직전 기록 이월, 첫 기록 전은 0
    ly = loan[(loan["date"] >= px["date"].min()) & (loan["date"] <= px["date"].max())]
    px["cid"] = px["code"].map(LOAN_IDS).fillna(-1).astype("int32")
    px = px.merge(ly, on=["date", "cid"], how="left").drop(columns="cid")
    for c in ("loan_shares", "loan_bal"):
        seed = px["code"].map(carry[c])
        px[c] = px[c].fillna(px.groupby("code")[c].ffill())
        px[c] = px[c].fillna(seed).fillna(0.0)
    last = px["code"].map(m.set_index("code")["last_date"])
    unavailable = ~px["code"].isin(loan_have) | (px["code"].isin(loan_empty) & (last < LOAN_FIRST_DELISTED))
    px.loc[unavailable, ["loan_shares", "loan_bal"]] = np.nan
    px["loan_avail"] = ~unavailable
    # 공개 시점: t일 잔고는 t+1일 13시 이후 공개 → t일 신호에는 t-1일 잔고 (assumptions.md 4절)
    prev_loan = px.groupby("code")["loan_bal"].shift(1)
    px["loan_bal_known"] = prev_loan.where(~first_row, px["code"].map(carry["loan_bal_last"]))

    # 업종: 그날 이전 가장 최근 월말 스냅샷
    px = px.sort_values("date")
    sec = sectors.rename(columns={"snap": "date"}).sort_values("date")
    px = pd.merge_asof(px, sec, on="date", by="code", direction="backward")
    # 스냅샷 이전에 상장한 신규 종목(월중 상장)과 첫 스냅샷 이전 날짜는 바로 다음 스냅샷 업종으로 채운다.
    # 업종은 거의 바뀌지 않는 속성이고, 이런 종목은 상장 후 252거래일 조건으로 신호에서 빠지므로 미래 정보 영향이 없다.
    nxt = pd.merge_asof(px[["date", "code"]], sec, on="date", by="code", direction="forward")["sector"]
    px["sector"] = px["sector"].fillna(nxt.set_axis(px.index))
    px = px.sort_values(["code", "date"]).reset_index(drop=True)

    liq = m.set_index("code")["liq_start"]
    px["in_liquidation"] = px["date"] >= pd.to_datetime(px["code"].map(liq))
    px["perm_id"] = px["code"].map(m.set_index("code")["perm_id"])

    # 다음 해로 넘길 값
    lastrow = px.groupby("code").tail(1)
    carry["close"].update(dict(zip(lastrow["code"], lastrow["close_raw"])))
    carry["logidx"].update(dict(zip(lastrow["code"], np.log(lastrow["adj_close"]))))
    for c in ("loan_shares", "loan_bal"):
        carry[c].update(dict(zip(lastrow["code"], lastrow[c])))
    carry["loan_bal_last"].update(dict(zip(lastrow["code"], lastrow["loan_bal"])))

    cols = ["date", "code", "perm_id", "market", "open", "high", "low", "close", "close_raw", "volume", "value",
            "mktcap", "chg_pct", "halted", "ret", "ret_from_chg", "adj_close", "adj_open", *FLOW_COLS,
            "loan_shares", "loan_bal", "loan_bal_known", "loan_avail", "sector", "in_liquidation"]
    px[cols].to_parquet(OUT / f"panel_{year}.parquet", index=False)

    big = px[px["ret"].abs() > 0.5][["date", "code", "close_raw", "chg_pct", "ret", "ret_from_chg", "in_liquidation"]]
    return {"year": year, "rows": len(px), "codes": px["code"].nunique(), "halted": int(px["halted"].sum()),
            "ret_from_chg": int(px["ret_from_chg"].sum()), "flow_on_halted": unmatched,
            "loan_nan_rows": int(px["loan_bal"].isna().sum()), "no_sector": int(px["sector"].isna().sum()),
            "big": big}


def earnings_dates(days: list[str]) -> pd.DataFrame:
    """잠정실적 공정공시 접수일. 그 회사의 정기보고서 중 직전 45일 안에 잠정실적이 없는 것은 정기보고서 접수일."""
    i = dart_list("I")
    prelim = i[i["nm"].str.contains(r"영업\(잠정\)실적\(공정공시\)") & ~i["nm"].str.contains("자회사|월별")
               & ~i["nm"].str.startswith("[")]
    a = dart_list("A")
    reg = a[a["nm"].str.contains("사업보고서|반기보고서|분기보고서") & ~a["nm"].str.startswith("[")]
    e1 = prelim.assign(source="잠정실적")[["stock_code", "rcept_dt", "source", "report_nm"]]
    e2 = reg.assign(source="정기보고서")[["stock_code", "rcept_dt", "source", "report_nm"]]
    e1d = e1.assign(dt=pd.to_datetime(e1["rcept_dt"]))
    keep = []
    for code, g in e2.groupby("stock_code"):
        p = e1d.loc[e1d["stock_code"] == code, "dt"].values
        for _, r in g.iterrows():
            d = np.datetime64(pd.Timestamp(r["rcept_dt"]))
            if not ((p <= d) & (p >= d - np.timedelta64(45, "D"))).any():
                keep.append(r)
    e = pd.concat([e1, pd.DataFrame(keep)], ignore_index=True).drop_duplicates(["stock_code", "rcept_dt"])
    tdays = np.array(days)
    idx = np.searchsorted(tdays, e["rcept_dt"].values)  # 접수일이 거래일이면 그날, 아니면 다음 거래일
    e = e[idx < len(tdays)].copy()
    e["event_date"] = tdays[idx[idx < len(tdays)]]
    return e.rename(columns={"stock_code": "code"}).sort_values(["code", "rcept_dt"])


def ref_tables() -> None:
    (OUT / "ref").mkdir(exist_ok=True)
    # 결제일(양도일) 기준 세율, % (증권거래세 + 농어촌특별세). 근거: assumptions.md 8절
    pd.DataFrame([
        ("2014-01-01", "2019-06-02", 0.15, 0.15, 0.30, 0.00, 0.30),
        ("2019-06-03", "2020-12-31", 0.10, 0.15, 0.25, 0.00, 0.25),
        ("2021-01-01", "2022-12-31", 0.08, 0.15, 0.23, 0.00, 0.23),
        ("2023-01-01", "2023-12-31", 0.05, 0.15, 0.20, 0.00, 0.20),
        ("2024-01-01", "2024-12-31", 0.03, 0.15, 0.18, 0.00, 0.18),
        ("2025-01-01", "2025-12-31", 0.00, 0.15, 0.15, 0.00, 0.15),
        ("2026-01-01", "2099-12-31", 0.05, 0.15, 0.20, 0.00, 0.20),
    ], columns=["settle_from", "settle_to", "kospi_stt", "kospi_rural", "kospi_total", "kosdaq_rural", "kosdaq_total"]
    ).to_csv(OUT / "ref" / "tax_rates.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([
        ("2020-03-16", "2021-05-02", "전 종목 금지"),
        ("2021-05-03", "2023-11-05", "KOSPI200·KOSDAQ150 종목만 허용"),
        ("2023-11-06", "2025-03-30", "전 종목 금지"),
        ("2025-03-31", "2099-12-31", "전 종목 허용"),
    ], columns=["from", "to", "regime"]).to_csv(OUT / "ref" / "short_sale_ban.csv", index=False, encoding="utf-8-sig")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = px_files()
    days = [d for d in files if d <= END]
    print(f"시세 {len(days)}일 ({days[0]}~{days[-1]})", flush=True)

    m = classify(pass_master({d: files[d] for d in days}))
    m, mapping = link_codes(m, days)
    m["liq_start"] = m["code"].map(liquidation_start(m, days))
    m.drop(columns=["mkt_hist", "nname"]).to_csv(OUT / "master.csv", index=False, encoding="utf-8-sig")
    mapping.to_csv(LOGS / "ticker_mapping.csv", index=False, encoding="utf-8-sig")
    print(f"종목 {len(m)}개, 코드 연결 {int((mapping['type'] == 'code_change').sum())}건, "
          f"시장 이전 {int(mapping['type'].str.startswith('market').sum())}건, 정리매매 {int(m['liq_start'].notna().sum())}종목", flush=True)

    loan, loan_empty, loan_have = build_loan_long()
    sectors = sector_table()
    carry = {k: {} for k in ("close", "logidx", "loan_shares", "loan_bal", "loan_bal_last")}
    stats, bigs = [], []
    for year in sorted({d[:4] for d in days}):
        s = build_year(year, [d for d in days if d[:4] == year], files, m, loan, loan_empty, loan_have, sectors, carry)
        bigs.append(s.pop("big"))
        stats.append(s)
        print(f"  {year}: {s}", flush=True)
    del loan

    idx = pd.read_csv(DATA / "index" / "index_daily.csv")
    idx["date"] = pd.to_datetime(idx["일자"])
    ir = idx.pivot(index="date", columns="지수", values="종가").pct_change()
    ir.to_csv(OUT / "index_ret.csv", encoding="utf-8-sig")

    ed = earnings_dates(days)
    ed.to_csv(OUT / "earnings_dates.csv", index=False, encoding="utf-8-sig")
    ref_tables()

    big = pd.concat(bigs, ignore_index=True)
    big.to_csv(LOGS / "big_returns.csv", index=False, encoding="utf-8-sig")
    st = pd.DataFrame(stats)
    st.to_csv(LOGS / "clean_stats.csv", index=False, encoding="utf-8-sig")
    print(f"일간 |수익률|>50%: {len(big)}건 (정리매매 중 {int(big['in_liquidation'].sum())}건)")
    print(f"실적 발표일 {len(ed)}건 (잠정 {int((ed['source'] == '잠정실적').sum())}, 정기 {int((ed['source'] == '정기보고서').sum())})")
    print(f"저장 위치: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
