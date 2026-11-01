"""strategy2 연구계획서 3.1절/4.4절: 종목별 일별 대차잔고 수집 (KIS Open API, 2014-01-01~).

KRX 시세 파일(data/ohlcv, data/lookback, data/history)에 한 번이라도 나온 보통주(코드 끝자리 0)를
대상으로, KIS '종목별 일별 대차거래추이'(HHPST074500C0)를 받아 종목별 파일로 저장한다.
상장폐지 종목도 조회된다(000060 등으로 확인).

  data/loan/loan_{종목코드}.csv.gz : 일자, 체결주수, 상환주수, 잔고주수, 잔고금액(백만원), 종가
                                     (조회 기간에 대차 기록이 없으면 헤더만 있는 파일)

한 번에 100일치씩 받으므로 종료일을 앞으로 옮겨 가며 반복 조회한다.
이미 파일이 있는 종목은 건너뛰므로, 시세 수집이 끝난 뒤 다시 실행하면 새로 나온 종목만 받는다.
.env 에 KIS_APP_KEY, KIS_APP_SECRET 이 있어야 한다. 접근 토큰은 data/.kis_token.json 에 캐시(24시간).

사용 예:
    python strategy2/code/fetch_loan_history.py
"""
import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

BASE = "https://openapi.koreainvestment.com:9443"
DATA = ROOT / "data"
OUTDIR = DATA / "loan"
TOKEN_PATH = DATA / ".kis_token.json"
REQUEST_INTERVAL = 0.12  # KIS 실전계좌 초당 20건 제한보다 충분히 느리게
RETRIES = 5
COLS = {"bsop_date": "일자", "new_stcn": "체결주수", "rdmp_stcn": "상환주수",
        "rmnd_stcn": "잔고주수", "rmnd_amt": "잔고금액_백만원", "stck_prpr": "종가"}


def get_token(renew: bool = False) -> str:
    """접근 토큰. 캐시가 있고 만료 1시간 전보다 이르면 재사용 (재발급은 1분에 1회 제한)."""
    if TOKEN_PATH.exists() and not renew:
        t = json.loads(TOKEN_PATH.read_text())
        if datetime.strptime(t["access_token_token_expired"], "%Y-%m-%d %H:%M:%S") - datetime.now() > timedelta(hours=1):
            return t["access_token"]
    r = requests.post(f"{BASE}/oauth2/tokenP", json={"grant_type": "client_credentials",
                      "appkey": os.environ["KIS_APP_KEY"], "appsecret": os.environ["KIS_APP_SECRET"]}, timeout=10)
    r.raise_for_status()
    TOKEN_PATH.write_text(r.text)
    return r.json()["access_token"]


class Kis:
    def __init__(self):
        self.token = get_token()

    def loan(self, code: str, start: str, end: str) -> list[dict]:
        """KIS 요청 + 대기 + 실패 시 재시도 (대기 시간을 늘려가며, 토큰 만료면 재발급)."""
        for i in range(RETRIES):
            try:
                r = requests.get(
                    f"{BASE}/uapi/domestic-stock/v1/quotations/daily-loan-trans", timeout=10,
                    headers={"authorization": f"Bearer {self.token}", "appkey": os.environ["KIS_APP_KEY"],
                             "appsecret": os.environ["KIS_APP_SECRET"], "tr_id": "HHPST074500C0", "custtype": "P"},
                    params={"MRKT_DIV_CLS_CODE": "3", "MKSC_SHRN_ISCD": code,
                            "START_DATE": start, "END_DATE": end, "CTS": ""})
                j = r.json()
                time.sleep(REQUEST_INTERVAL)
                if j.get("rt_cd") == "0":
                    return j.get("output1") or []
                if j.get("msg_cd") in ("EGW00123", "EGW00121"):  # 토큰 만료/무효
                    time.sleep(61)
                    self.token = get_token(renew=True)
                    continue
                raise RuntimeError(f"{j.get('msg_cd')} {j.get('msg1')}")
            except Exception as e:  # 네트워크 오류, 초당 건수 초과 등
                wait = 5 * (i + 1)
                print(f"  요청 실패 {code} ~{end} ({e.__class__.__name__}: {e}) → {wait}초 후 재시도", flush=True)
                time.sleep(wait)
        raise RuntimeError(f"{code} ~{end} 재시도 {RETRIES}회 실패")


def fetch_code(kis: Kis, code: str, start: str, end: str) -> pd.DataFrame:
    """최근 날짜부터 100일씩 거슬러 올라가며 start 까지 받는다."""
    rows = []
    while end >= start:
        out = kis.loan(code, start, end)
        if not out:
            break
        rows += out
        first = min(o["bsop_date"] for o in out)
        if len(out) < 100:
            break
        end = (datetime.strptime(first, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    df = pd.DataFrame(rows, columns=list(COLS)).rename(columns=COLS)
    return df.drop_duplicates("일자").sort_values("일자")


def codes_seen() -> list[str]:
    """KRX 시세 파일에 한 번이라도 나온 보통주 종목코드 + KRX 상폐 목록의 코스피·코스닥 종목.
    상폐 목록엔 폐지일이 없어 2014년 이전 폐지 종목도 섞이지만, 그런 종목은 빈 파일로 끝난다."""
    codes = set()
    for d in ("ohlcv", "lookback", "history"):
        for f in sorted((DATA / d).glob("ohlcv_*.csv.gz")):
            codes |= set(pd.read_csv(f, usecols=["종목코드"], dtype=str)["종목코드"])
    delisted = pd.read_csv(DATA / "master" / "delisted_list.csv", dtype=str)
    delisted = delisted[delisted["marketCode"].isin(["STK", "KSQ"]) & delisted["short_code"].str.len().eq(6)]
    codes |= set(delisted["short_code"])
    return sorted(c for c in codes if c.endswith("0"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="20140101")
    p.add_argument("--end", default="20261022")
    args = p.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    codes = codes_seen()
    todo = [c for c in codes if not (OUTDIR / f"loan_{c}.csv.gz").exists()]
    print(f"대상 {len(codes)}종목, 이미 받음 {len(codes) - len(todo)}, 남음 {len(todo)}", flush=True)

    kis, t0 = Kis(), time.time()
    for i, code in enumerate(todo, 1):
        fetch_code(kis, code, args.start, args.end).to_csv(OUTDIR / f"loan_{code}.csv.gz", index=False, encoding="utf-8-sig")
        if i % 50 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"{i}/{len(todo)} 완료 ({code}), 경과 {el / 60:.0f}분, 남은 예상 {el / i * (len(todo) - i) / 60:.0f}분", flush=True)
    print(f"저장 위치: {OUTDIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
