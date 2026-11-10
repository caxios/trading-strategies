# KRX 데이터 수집 문서 (한국거래소 & pykrx)

한국거래소 정보데이터시스템([data.krx.co.kr](http://data.krx.co.kr))의 시세·수급·마스터 데이터를 `pykrx` 오픈소스 라이브러리를 통해 스크래핑/크롤링하여 장기 백테스트 데이터셋을 구축하는 개발 가이드 문서.

- **데이터 제공처**: 한국거래소 정보데이터시스템 (KRX Data Marketplace)
- **스크래핑 엔진**: `pykrx` 라이브러리 (버전 1.2.9 기준)
- **구축 데이터 기간**: 2014-01-02 ~ 최신 (13년치 전 종목)
- **수집 대상 자산**: KOSPI, KOSDAQ 상장 보통주 전 종목 및 상장폐지 종목

---

## 📖 먼저 읽을 것

👉 **[00_공통_가이드.md](00_공통_가이드.md)**  
- KRX 스크래핑 아키텍처 개요
- `.env` 계정 인증 및 **단일 세션 제약** 주의사항
- `pykrx` 핵심 함수 명세 (`get_market_ohlcv`, `get_market_net_purchases_of_equities_by_ticker` 등)
- 투자주체 코드 매핑 (외국인+기타외국인, 연기금+투신)
- IP 차단 방지 레이트 리미팅 및 재시도(Retry) 기법
- 수집 스크립트 실행 가이드

---

## 📁 관련 스크립트 및 저장 경로

| 스크립트 | 설명 | 결과 저장 경로 |
|---|---|---|
| `strategy2/code/fetch_flow_history.py` | 2014년~최신 전 종목 일별 시세 및 투자주체별 거래대금 일괄 수집 | `data/ohlcv/`, `data/flow/` |
| `strategy2/code/fetch_krx_meta.py` | 시장 지수 시세, 월별 업종 스냅샷, 상폐 및 기본정보 마스터 수집 | `data/index/`, `data/sectors/`, `data/master/` |
| `fetch_investor_history.py` | 최근 2년 히스토리 수집용 베이스라인 스크립트 | `data/history/` |
| `strategy2/code/build_clean.py` | 수집된 원본 파일들을 압축 파케이 패널(`data/clean/panel_YYYY.parquet`)로 결합/정제 | `data/clean/` |
