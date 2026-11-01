"""strategy2 연구계획서 3.1절: DART 공시 수집 (5% 대량보유 공시, 실적 발표일).

  data/dart/corp_code.csv                  : DART 고유번호 ↔ 종목코드 (corpCode.xml, 1회)
  data/dart/list/{유형}_{YYYY}Q{n}.csv.gz  : 분기별 공시 목록 (회사 구분 없이 기간 조회)
        D 지분공시 (대량보유상황보고 포함), I 거래소공시 (잠정실적 공정공시, 관리종목·거래정지 등 시장조치 포함),
        A 정기공시 (사업·반기·분기보고서)
        세부유형(pblntf_detail_ty) 필터는 API 가 무시하므로(2014Q1 로 확인) 상위 유형 전체를 받는다.
  data/dart/majorstock/{corp_code}.csv.gz  : 회사별 대량보유 상황보고 상세 (보고자, 보유비율, 증감, 사유)
        D 목록에 대량보유상황보고서가 한 번이라도 나온 상장 회사만 받는다.

DART 공시 목록 API 는 접수일(rcept_dt)만 주고 접수 시각은 주지 않는다 (공개 시점 규칙은 logs/assumptions.md).
이미 받은 파일은 건너뛰므로 끊기거나 일일 한도(2만 건)에 걸리면 다음 날 다시 실행하면 이어서 받는다.
.env 에 OPENDART_API_KEY 가 있어야 한다.

사용 예:
    python strategy2/code/fetch_dart.py
"""
import argparse
import io
import os
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

BASE = "https://opendart.fss.or.kr/api"
OUTDIR = ROOT / "data" / "dart"
TYPES = ["D", "I", "A"]
REQUEST_INTERVAL = 0.2
RETRIES = 4


class DailyLimit(Exception):
    pass


def get(path: str, **params) -> requests.Response:
    """DART 요청 + 대기 + 실패 시 재시도. 일일 한도 초과(020)면 DailyLimit."""
    params["crtfc_key"] = os.environ["OPENDART_API_KEY"]
    for i in range(RETRIES):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=60)
            time.sleep(REQUEST_INTERVAL)
            if path.endswith(".json"):
                status = r.json().get("status")
                if status == "020":
                    raise DailyLimit(r.json().get("message"))
                if status not in ("000", "013"):  # 013 = 조회된 데이터 없음
                    raise RuntimeError(f"{status} {r.json().get('message')}")
            return r
        except DailyLimit:
            raise
        except Exception as e:
            wait = 5 * (i + 1)
            print(f"  요청 실패 {path} {params.get('bgn_de', params.get('corp_code'))} ({e.__class__.__name__}: {e}) → {wait}초 후 재시도", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{path} 재시도 {RETRIES}회 실패")


def fetch_corp_codes() -> None:
    path = OUTDIR / "corp_code.csv"
    if path.exists():
        return
    z = zipfile.ZipFile(io.BytesIO(get("corpCode.xml").content))
    root = ET.fromstring(z.read(z.namelist()[0]))
    pd.DataFrame([{c.tag: (c.text or "").strip() for c in e} for e in root.iter("list")]).to_csv(
        path, index=False, encoding="utf-8-sig")


def quarters(start: str, end: str) -> list[tuple[str, str, str]]:
    """(라벨, 시작일, 종료일) 분기 목록. 회사 지정 없는 목록 조회는 기간 3개월 이내만 허용된다."""
    out = []
    for q in pd.period_range(pd.Timestamp(start), pd.Timestamp(end), freq="Q"):
        s = max(q.start_time, pd.Timestamp(start)).strftime("%Y%m%d")
        e = min(q.end_time, pd.Timestamp(end)).strftime("%Y%m%d")
        out.append((f"{q.year}Q{q.quarter}", s, e))
    return out


def fetch_list(ty: str, bgn: str, end: str) -> pd.DataFrame:
    rows, page = [], 1
    while True:
        j = get("list.json", bgn_de=bgn, end_de=end, pblntf_ty=ty, page_no=page, page_count=100).json()
        rows += j.get("list", [])
        if page >= int(j.get("total_page", 0) or 0):
            break
        page += 1
    if rows and len(rows) != int(j.get("total_count", 0)):
        print(f"  건수 불일치 {ty} {bgn}~{end}: 받음 {len(rows)}, 전체 {j.get('total_count')}", flush=True)
    return pd.DataFrame(rows)


def read_list(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str)
    except pd.errors.EmptyDataError:  # 그 분기에 해당 공시가 하나도 없음
        return pd.DataFrame()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="20140101")
    p.add_argument("--end", default="20261022")
    args = p.parse_args()

    (OUTDIR / "list").mkdir(parents=True, exist_ok=True)
    (OUTDIR / "majorstock").mkdir(parents=True, exist_ok=True)
    fetch_corp_codes()

    try:
        jobs = [(d, *q) for d in TYPES for q in quarters(args.start, args.end)
                if not (OUTDIR / "list" / f"{d}_{q[0]}.csv.gz").exists()]
        print(f"공시 목록: 남은 {len(jobs)}개 (유형 × 분기)", flush=True)
        for i, (d, label, s, e) in enumerate(jobs, 1):
            fetch_list(d, s, e).to_csv(OUTDIR / "list" / f"{d}_{label}.csv.gz", index=False, encoding="utf-8-sig")
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} 완료 ({d}_{label})", flush=True)

        d001 = pd.concat([read_list(f) for f in (OUTDIR / "list").glob("D_*.csv.gz")], ignore_index=True)
        d001 = d001[d001["report_nm"].str.contains("대량보유") & (d001["stock_code"].fillna("").str.len() == 6)]
        corps = sorted(d001["corp_code"].unique())
        todo = [c for c in corps if not (OUTDIR / "majorstock" / f"{c}.csv.gz").exists()]
        print(f"대량보유 상세: 대상 {len(corps)}개 회사, 남음 {len(todo)}", flush=True)
        for i, c in enumerate(todo, 1):
            j = get("majorstock.json", corp_code=c).json()
            pd.DataFrame(j.get("list", [])).to_csv(OUTDIR / "majorstock" / f"{c}.csv.gz", index=False, encoding="utf-8-sig")
            if i % 200 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} 완료", flush=True)
    except DailyLimit as e:
        print(f"DART 일일 요청 한도 초과 ({e}). 내일 다시 실행하면 이어서 받는다.")
        return
    print(f"저장 위치: {OUTDIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
