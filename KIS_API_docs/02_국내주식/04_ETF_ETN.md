# [국내주식] ETF/ETN

> 출처: 한국투자증권 공식 저장소 `koreainvestment/open-trading-api` (examples_llm) 자동 추출. 공통 규칙(도메인·헤더·토큰·연속조회·웹소켓)은 [공통 가이드](../00_공통_가이드.md) 참고.

## 목록

| API | Method | URL | TR_ID |
|---|---|---|---|
| [국내ETF NAV추이[실시간-051]](#etf_nav_trend) | WEBSOCKET | `-` | H0STNAV0 |
| [ETF 구성종목시세[국내주식-073]](#inquire_component_stock_price) | GET | `/uapi/etfetn/v1/quotations/inquire-component-stock-price` | FHKST121600C0 |
| [ETF/ETN 현재가[v1_국내주식-068]](#inquire_price) | GET | `/uapi/etfetn/v1/quotations/inquire-price` | FHPST02400000 |
| [NAV 비교추이(일)[v1_국내주식-071]](#nav_comparison_daily_trend) | GET | `/uapi/etfetn/v1/quotations/nav-comparison-daily-trend` | FHPST02440200 |
| [NAV 비교추이(분)[v1_국내주식-070]](#nav_comparison_time_trend) | GET | `/uapi/etfetn/v1/quotations/nav-comparison-time-trend` | FHPST02440100 |
| [NAV 비교추이(종목)[v1_국내주식-069]](#nav_comparison_trend) | GET | `/uapi/etfetn/v1/quotations/nav-comparison-trend` | FHPST02440000 |

<a id="etf_nav_trend"></a>
### 국내ETF NAV추이[실시간-051]

- **함수/폴더**: `etf_nav_trend` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/etfetn/etf_nav_trend/etf_nav_trend.py)
- **방식**: WebSocket 구독 (실전 `ws://ops.koreainvestment.com:21000`, 모의 `:31000`)
- **TR_ID**: `H0STNAV0`
- **예시**: `msg, columns = etf_nav_trend("1", "005930")`

**요청 파라미터** (body.input)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `tr_key` | Y | 종목코드 (빈 문자열 불가) |

**TR_ID/동작 결정 인자** (샘플 함수 인자)

- `tr_type` (필수): 구독 등록("1") 또는 해제("0") 여부를 나타내는 문자열

<details><summary>응답 필드 (10개)</summary>

| 필드 | 설명 |
|---|---|
| `rt_cd` | 성공 실패 여부 |
| `msg_cd` | 응답코드 |
| `mksc_shrn_iscd` | 유가증권단축종목코드 |
| `nav` | NAV |
| `nav_prdy_vrss_sign` | NAV전일대비부호 |
| `nav_prdy_vrss` | NAV전일대비 |
| `nav_prdy_ctrt` | NAV전일대비율 |
| `oprc_nav` | NAV시가 |
| `hprc_nav` | NAV고가 |
| `lprc_nav` | NAV저가 |

</details>

---

<a id="inquire_component_stock_price"></a>
### ETF 구성종목시세[국내주식-073]

- **함수/폴더**: `inquire_component_stock_price` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/etfetn/inquire_component_stock_price/inquire_component_stock_price.py)
- **Method / URL**: `GET /uapi/etfetn/v1/quotations/inquire-component-stock-price`
- **TR_ID**: `FHKST121600C0`
- **예시**: `df1, df2 = inquire_component_stock_price("J", "069500", "11216")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (ex. J: 주식/ETF/ETN) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (ex. 123456) |
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드 (ex. 11216) |

<details><summary>응답 필드 (26개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_prpr` | 매매 일자 |
| `prdy_vrss` | 주식 현재가 |
| `prdy_vrss_sign` | 전일 대비 부호 |
| `prdy_ctrt` | 전일 대비 |
| `etf_cnfg_issu_avls` | 전일 대비율 |
| `nav` | 누적 거래량 |
| `nav_prdy_vrss_sign` | 결제 일자 |
| `nav_prdy_vrss` | 전체 융자 신규 주수 |
| `nav_prdy_ctrt` | 전체 융자 상환 주수 |
| `etf_ntas_ttam` | 전체 융자 잔고 주수 |
| `prdy_clpr_nav` | 전체 융자 신규 금액 |
| `oprc_nav` | 전체 융자 상환 금액 |
| `hprc_nav` | 전체 융자 잔고 금액 |
| `lprc_nav` | 전체 융자 잔고 비율 |
| `etf_cu_unit_scrt_cnt` | 전체 융자 공여율 |
| `etf_cnfg_issu_cnt` | 전체 대주 신규 주수 |
| `stck_shrn_iscd` | 주식 단축 종목코드 |
| `hts_kor_isnm` | HTS 한글 종목명 |
| `acml_vol` | 누적 거래량 |
| `acml_tr_pbmn` | 누적 거래 대금 |
| `tday_rsfl_rate` | 당일 등락 비율 |
| `prdy_vrss_vol` | 전일 대비 거래량 |
| `tr_pbmn_tnrt` | 거래대금회전율 |
| `hts_avls` | HTS 시가총액 |
| `etf_vltn_amt` | ETF구성종목내평가금액 |
| `etf_cnfg_issu_rlim` | ETF구성종목비중 |

</details>

---

<a id="inquire_price"></a>
### ETF/ETN 현재가[v1_국내주식-068]

- **함수/폴더**: `inquire_price` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/etfetn/inquire_price/inquire_price.py)
- **Method / URL**: `GET /uapi/etfetn/v1/quotations/inquire-price`
- **TR_ID**: `FHPST02400000`
- **예시**: `df = inquire_price("J", "123456")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건 시장 분류 코드 (ex. J:KRX, NX:NXT, UN:통합) |
| `FID_INPUT_ISCD` | Y | 입력 종목코드 (ex. 123456) |

<details><summary>응답 필드 (59개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_prpr` | 주식 현재가 |
| `prdy_vrss_sign` | 전일 대비 부호 |
| `prdy_vrss` | 전일 대비 |
| `prdy_ctrt` | 전일 대비율 |
| `acml_vol` | 누적 거래량 |
| `prdy_vol` | 전일 거래량 |
| `stck_mxpr` | 주식 상한가 |
| `stck_llam` | 주식 하한가 |
| `stck_prdy_clpr` | 주식 전일 종가 |
| `stck_oprc` | 주식 시가2 |
| `prdy_clpr_vrss_oprc_rate` | 전일 종가 대비 시가2 비율 |
| `stck_hgpr` | 주식 최고가 |
| `prdy_clpr_vrss_hgpr_rate` | 전일 종가 대비 최고가 비율 |
| `stck_lwpr` | 주식 최저가 |
| `prdy_clpr_vrss_lwpr_rate` | 전일 종가 대비 최저가 비율 |
| `prdy_last_nav` | 전일 최종 NAV |
| `nav` | NAV |
| `nav_prdy_vrss` | NAV 전일 대비 |
| `nav_prdy_vrss_sign` | NAV 전일 대비 부호 |
| `nav_prdy_ctrt` | NAV 전일 대비율 |
| `trc_errt` | 추적 오차율 |
| `stck_sdpr` | 주식 기준가 |
| `stck_sspr` | 주식 대용가 |
| `nmix_ctrt` | 지수 대비율 |
| `etf_crcl_stcn` | ETF 유통 주수 |
| `etf_ntas_ttam` | ETF 순자산 총액 |
| `etf_frcr_ntas_ttam` | ETF 외화 순자산 총액 |
| `frgn_limt_rate` | 외국인 한도 비율 |
| `frgn_oder_able_qty` | 외국인 주문 가능 수량 |
| `etf_cu_unit_scrt_cnt` | ETF CU 단위 증권 수 |
| `etf_cnfg_issu_cnt` | ETF 구성 종목 수 |
| `etf_dvdn_cycl` | ETF 배당 주기 |
| `crcd` | 통화 코드 |
| `etf_crcl_ntas_ttam` | ETF 유통 순자산 총액 |
| `etf_frcr_crcl_ntas_ttam` | ETF 외화 유통 순자산 총액 |
| `etf_frcr_last_ntas_wrth_val` | ETF 외화 최종 순자산 가치 값 |
| `lp_oder_able_cls_code` | LP 주문 가능 구분 코드 |
| `stck_dryy_hgpr` | 주식 연중 최고가 |
| `dryy_hgpr_vrss_prpr_rate` | 연중 최고가 대비 현재가 비율 |
| `dryy_hgpr_date` | 연중 최고가 일자 |
| `stck_dryy_lwpr` | 주식 연중 최저가 |
| `dryy_lwpr_vrss_prpr_rate` | 연중 최저가 대비 현재가 비율 |
| `dryy_lwpr_date` | 연중 최저가 일자 |
| `bstp_kor_isnm` | 업종 한글 종목명 |
| `vi_cls_code` | VI적용구분코드 |
| `lstn_stcn` | 상장 주수 |
| `frgn_hldn_qty` | 외국인 보유 수량 |
| `frgn_hldn_qty_rate` | 외국인 보유 수량 비율 |
| `etf_trc_ert_mltp` | ETF 추적 수익률 배수 |
| `dprt` | 괴리율 |
| `mbcr_name` | 회원사 명 |
| `stck_lstn_date` | 주식 상장 일자 |
| `mtrt_date` | 만기 일자 |
| `shrg_type_code` | 분배금형태코드 |
| `lp_hldn_rate` | LP 보유 비율 |
| `etf_trgt_nmix_bstp_code` | ETF대상지수업종코드 |
| `etf_div_name` | ETF 분류 명 |
| `etf_rprs_bstp_kor_isnm` | ETF 대표 업종 한글 종목명 |
| `lp_hldn_vol` | ETN LP 보유량 |

</details>

---

<a id="nav_comparison_daily_trend"></a>
### NAV 비교추이(일)[v1_국내주식-071]

- **함수/폴더**: `nav_comparison_daily_trend` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/etfetn/nav_comparison_daily_trend/nav_comparison_daily_trend.py)
- **Method / URL**: `GET /uapi/etfetn/v1/quotations/nav-comparison-daily-trend`
- **TR_ID**: `FHPST02440200`
- **예시**: `df = nav_comparison_daily_trend("J", "069500", "20240101", "20240220")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (ex. J:주식) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (ex. 123456) |
| `FID_INPUT_DATE_1` | Y | 조회시작일자 (ex. 20240101) |
| `FID_INPUT_DATE_2` | Y | 조회종료일자 (ex. 20240220) |

<details><summary>응답 필드 (13개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_bsop_date` | 주식 영업 일자 |
| `stck_clpr` | 주식 종가 |
| `prdy_vrss` | 전일 대비 |
| `prdy_vrss_sign` | 전일 대비 부호 |
| `prdy_ctrt` | 전일 대비율 |
| `acml_vol` | 누적 거래량 |
| `cntg_vol` | 체결 거래량 |
| `dprt` | 괴리율 |
| `nav_vrss_prpr` | NAV 대비 현재가 |
| `nav` | NAV |
| `nav_prdy_vrss_sign` | NAV 전일 대비 부호 |
| `nav_prdy_vrss` | NAV 전일 대비 |
| `nav_prdy_ctrt` | NAV 전일 대비율 |

</details>

---

<a id="nav_comparison_time_trend"></a>
### NAV 비교추이(분)[v1_국내주식-070]

- **함수/폴더**: `nav_comparison_time_trend` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/etfetn/nav_comparison_time_trend/nav_comparison_time_trend.py)
- **Method / URL**: `GET /uapi/etfetn/v1/quotations/nav-comparison-time-trend`
- **TR_ID**: `FHPST02440100`
- **예시**: `df = nav_comparison_time_trend("E", "069500", "60")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (ex. E) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (ex. 123456) |
| `FID_HOUR_CLS_CODE` | Y | 시간구분코드 (ex. 60:1분,180:3분,...,7200:120분) |

<details><summary>응답 필드 (13개)</summary>

| 필드 | 설명 |
|---|---|
| `bsop_hour` | 영업 시간 |
| `nav` | NAV |
| `nav_prdy_vrss_sign` | NAV 전일 대비 부호 |
| `nav_prdy_vrss` | NAV 전일 대비 |
| `nav_prdy_ctrt` | NAV 전일 대비율 |
| `nav_vrss_prpr` | NAV 대비 현재가 |
| `dprt` | 괴리율 |
| `stck_prpr` | 주식 현재가 |
| `prdy_vrss` | 전일 대비 |
| `prdy_vrss_sign` | 전일 대비 부호 |
| `prdy_ctrt` | 전일 대비율 |
| `acml_vol` | 누적 거래량 |
| `cntg_vol` | 체결 거래량 |

</details>

---

<a id="nav_comparison_trend"></a>
### NAV 비교추이(종목)[v1_국내주식-069]

- **함수/폴더**: `nav_comparison_trend` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/etfetn/nav_comparison_trend/nav_comparison_trend.py)
- **Method / URL**: `GET /uapi/etfetn/v1/quotations/nav-comparison-trend`
- **TR_ID**: `FHPST02440000`
- **예시**: `output1, output2 = nav_comparison_trend("J", "069500")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건 시장 분류 코드 (ex. J) |
| `FID_INPUT_ISCD` | Y | 입력 종목코드 |

<details><summary>응답 필드 (20개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_prpr` | 주식 현재가 |
| `prdy_vrss` | 전일 대비 |
| `prdy_vrss_sign` | 전일 대비 부호 |
| `prdy_ctrt` | 전일 대비율 |
| `acml_vol` | 누적 거래량 |
| `acml_tr_pbmn` | 누적 거래 대금 |
| `stck_prdy_clpr` | 주식 전일 종가 |
| `stck_oprc` | 주식 시가2 |
| `stck_hgpr` | 주식 최고가 |
| `stck_lwpr` | 주식 최저가 |
| `stck_mxpr` | 주식 상한가 |
| `stck_llam` | 주식 하한가 |
| `nav` | NAV |
| `nav_prdy_vrss_sign` | NAV 전일 대비 부호 |
| `nav_prdy_vrss` | NAV 전일 대비 |
| `nav_prdy_ctrt` | NAV 전일 대비율 |
| `prdy_clpr_nav` | NAV전일종가 |
| `oprc_nav` | NAV시가 |
| `hprc_nav` | NAV고가 |
| `lprc_nav` | NAV저가 |

</details>

---
