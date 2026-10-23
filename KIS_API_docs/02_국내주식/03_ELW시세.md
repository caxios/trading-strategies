# [국내주식] ELW시세

> 출처: 한국투자증권 공식 저장소 `koreainvestment/open-trading-api` (examples_llm) 자동 추출. 공통 규칙(도메인·헤더·토큰·연속조회·웹소켓)은 [공통 가이드](../00_공통_가이드.md) 참고.

## 목록

| API | Method | URL | TR_ID |
|---|---|---|---|
| [ELW 현재가 시세 [v1_국내주식-014]](#inquire_elw_price) | GET | `/uapi/domestic-stock/v1/quotations/inquire-elw-price` | FHKEW15010000 |
| [ELW 비교대상종목조회[국내주식-183]](#compare_stocks) | GET | `/uapi/elw/v1/quotations/compare-stocks` | FHKEW151701C0 |
| [ELW 종목검색[국내주식-166]](#cond_search) | GET | `/uapi/elw/v1/quotations/cond-search` | FHKEW15100000 |
| [ELW 만기예정/만기종목[국내주식-184]](#expiration_stocks) | GET | `/uapi/elw/v1/quotations/expiration-stocks` | FHKEW154700C0 |
| [ELW 지표순위[국내주식-169]](#indicator) | GET | `/uapi/elw/v1/ranking/indicator` | FHPEW02790000 |
| [ELW 투자지표추이(체결)[국내주식-172]](#indicator_trend_ccnl) | GET | `/uapi/elw/v1/quotations/indicator-trend-ccnl` | FHPEW02740100 |
| [ELW 투자지표추이(일별)[국내주식-173]](#indicator_trend_daily) | GET | `/uapi/elw/v1/quotations/indicator-trend-daily` | FHPEW02740200 |
| [ELW 투자지표추이(분별)[국내주식-174]](#indicator_trend_minute) | GET | `/uapi/elw/v1/quotations/indicator-trend-minute` | FHPEW02740300 |
| [ELW LP매매추이[국내주식-182]](#lp_trade_trend) | GET | `/uapi/elw/v1/quotations/lp-trade-trend` | FHPEW03760000 |
| [ELW 신규상장종목[국내주식-181]](#newly_listed) | GET | `/uapi/elw/v1/quotations/newly-listed` | FHKEW154800C0 |
| [ELW 당일급변종목[국내주식-171]](#quick_change) | GET | `/uapi/elw/v1/ranking/quick-change` | FHPEW02870000 |
| [ELW 민감도 순위[국내주식-170]](#sensitivity) | GET | `/uapi/elw/v1/ranking/sensitivity` | FHPEW02850000 |
| [ELW 민감도 추이(체결)[국내주식-175]](#sensitivity_trend_ccnl) | GET | `/uapi/elw/v1/quotations/sensitivity-trend-ccnl` | FHPEW02830100 |
| [ELW 민감도 추이(일별)[국내주식-176]](#sensitivity_trend_daily) | GET | `/uapi/elw/v1/quotations/sensitivity-trend-daily` | FHPEW02830200 |
| [ELW 기초자산 목록조회[국내주식-185]](#udrl_asset_list) | GET | `/uapi/elw/v1/quotations/udrl-asset-list` | FHKEW154100C0 |
| [ELW 기초자산별 종목시세](#udrl_asset_price) | GET | `/uapi/elw/v1/quotations/udrl-asset-price` | FHKEW154101C0 |
| [ELW 상승률순위[국내주식-167]](#updown_rate) | GET | `/uapi/elw/v1/ranking/updown-rate` | FHPEW02770000 |
| [ELW 변동성추이(체결)[국내주식-177]](#volatility_trend_ccnl) | GET | `/uapi/elw/v1/quotations/volatility-trend-ccnl` | FHPEW02840100 |
| [ELW 변동성추이(일별)[국내주식-178]](#volatility_trend_daily) | GET | `/uapi/elw/v1/quotations/volatility-trend-daily` | FHPEW02840200 |
| [ELW 변동성 추이(분별)](#volatility_trend_minute) | GET | `/uapi/elw/v1/quotations/volatility-trend-minute` | FHPEW02840300 |
| [ELW 변동성추이(틱)[국내주식-180]](#volatility_trend_tick) | GET | `/uapi/elw/v1/quotations/volatility-trend-tick` | FHPEW02840400 |
| [ELW 거래량순위[국내주식-168]](#volume_rank) | GET | `/uapi/elw/v1/ranking/volume-rank` | FHPEW02780000 |

<a id="inquire_elw_price"></a>
### ELW 현재가 시세 [v1_국내주식-014]

- **함수/폴더**: `inquire_elw_price` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_elw_price/inquire_elw_price.py)
- **Method / URL**: `GET /uapi/domestic-stock/v1/quotations/inquire-elw-price`
- **TR_ID**:
  - `FHKEW15010000` — env_dv == real or env_dv == demo
- **예시**: `df = inquire_elw_price('W', '000660', env_dv='real') # 실전투자`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | FID 조건 시장 분류 코드 (예: 'W') |
| `FID_INPUT_ISCD` | Y | FID 입력 종목코드 (예: '000660') |

**TR_ID/동작 결정 인자** (샘플 함수 인자)

- `env_dv`: [추가] 실전모의구분 (real:실전, demo:모의, 기본값: 'real')

<details><summary>응답 필드 (38개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW 단축 종목코드 |
| `hts_kor_isnm` | HTS 한글 종목명 |
| `elw_prpr` | ELW 현재가 |
| `prdy_vrss` | 전일 대비 |
| `prdy_vrss_sign` | 전일 대비 부호 |
| `prdy_ctrt` | 전일 대비율 |
| `acml_vol` | 누적 거래량 |
| `prdy_vrss_vol_rate` | 전일 대비 거래량 비율 |
| `unas_shrn_iscd` | 기초자산 단축 종목코드 |
| `unas_isnm` | 기초자산 종목명 |
| `unas_prpr` | 기초자산 현재가 |
| `unas_prdy_vrss` | 기초자산 전일 대비 |
| `unas_prdy_vrss_sign` | 기초자산 전일 대비 부호 |
| `unas_prdy_ctrt` | 기초자산 전일 대비율 |
| `bidp` | 매수호가 |
| `askp` | 매도호가 |
| `acml_tr_pbmn` | 누적 거래 대금 |
| `vol_tnrt` | 거래량 회전율 |
| `elw_oprc` | ELW 시가2 |
| `elw_hgpr` | ELW 최고가 |
| `elw_lwpr` | ELW 최저가 |
| `stck_prdy_clpr` | 주식 전일 종가 |
| `hts_thpr` | HTS 이론가 |
| `dprt` | 괴리율 |
| `atm_cls_name` | ATM구분명 |
| `hts_ints_vltl` | HTS 내재 변동성 |
| `acpr` | 행사가 |
| `pvt_scnd_dmrs_prc` | 피벗 2차 디저항 가격 |
| `pvt_frst_dmrs_prc` | 피벗 1차 디저항 가격 |
| `pvt_pont_val` | 피벗 포인트 값 |
| `pvt_frst_dmsp_prc` | 피벗 1차 디지지 가격 |
| `pvt_scnd_dmsp_prc` | 피벗 2차 디지지 가격 |
| `dmsp_val` | 디지지 값 |
| `dmrs_val` | 디저항 값 |
| `elw_sdpr` | ELW 기준가 |
| `apprch_rate` | 접근도 |
| `tick_conv_prc` | 틱환산가 |
| `invt_epmd_cntt` | 투자 유의 내용 |

</details>

---

<a id="compare_stocks"></a>
### ELW 비교대상종목조회[국내주식-183]

- **함수/폴더**: `compare_stocks` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/compare_stocks/compare_stocks.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/compare-stocks`
- **TR_ID**: `FHKEW151701C0`
- **예시**: `df = compare_stocks('11517', '005930')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드 (예: '11517') |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (예: '005930') |

<details><summary>응답 필드 (2개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW단축종목코드 |
| `elw_kor_isnm` | ELW한글종목명 |

</details>

---

<a id="cond_search"></a>
### ELW 종목검색[국내주식-166]

- **함수/폴더**: `cond_search` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/cond_search/cond_search.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/cond-search`
- **TR_ID**: `FHKEW15100000`
- **예시**: `# 기본 ELW 검색 (전체 종목)`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (ELW의 경우 "W" 입력) |
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드 (화면번호 "11510" 입력) |
| `FID_RANK_SORT_CLS_CODE` | Y | 순위정렬구분코드 |
| `FID_INPUT_CNT_1` | Y | 정렬1기준 (1: 상위, 2: 하위) |
| `FID_RANK_SORT_CLS_CODE_2` |  | 순위정렬구분코드2 (선택) |
| `FID_INPUT_CNT_2` |  | 입력수2 (선택) |
| `FID_RANK_SORT_CLS_CODE_3` |  | 순위정렬구분코드3 (선택) |
| `FID_INPUT_CNT_3` |  | 입력수3 (선택) |
| `FID_TRGT_CLS_CODE` |  | 대상구분코드 (선택) |
| `FID_INPUT_ISCD` |  | 입력종목코드 (선택 - 전체 허용) |
| `FID_UNAS_INPUT_ISCD` |  | 기초자산입력종목코드 (선택) |
| `FID_MRKT_CLS_CODE` |  | 시장구분코드 (선택 - 전체 허용) |
| `FID_INPUT_DATE_1` |  | 입력날짜1 (선택 - 전체 허용) |
| `FID_INPUT_DATE_2` |  | 입력날짜2 (선택 - 전체 허용) |
| `FID_INPUT_ISCD_2` |  | 입력종목코드2 (선택) |
| `FID_ETC_CLS_CODE` |  | 기타구분코드 (선택 - 전체 허용) |
| `FID_INPUT_RMNN_DYNU_1` |  | 입력잔존일수1 (선택 - 이상값) |
| `FID_INPUT_RMNN_DYNU_2` |  | 입력잔존일수2 (선택 - 이하값) |
| `FID_PRPR_CNT1` |  | 현재가수1 (선택 - 이상값) |
| `FID_PRPR_CNT2` |  | 현재가수2 (선택 - 이하값) |
| `FID_RSFL_RATE1` |  | 등락비율1 (선택 - 이상값) |
| `FID_RSFL_RATE2` |  | 등락비율2 (선택 - 이하값) |
| `FID_VOL1` |  | 거래량1 (선택 - 이상값) |
| `FID_VOL2` |  | 거래량2 (선택 - 이하값) |
| `FID_APLY_RANG_PRC_1` |  | 적용범위가격1 (선택) |
| `FID_APLY_RANG_PRC_2` |  | 적용범위가격2 (선택) |
| `FID_LVRG_VAL1` |  | 레버리지값1 (선택) |
| `FID_LVRG_VAL2` |  | 레버리지값2 (선택) |
| `FID_VOL3` |  | 거래량3 (선택) |
| `FID_VOL4` |  | 거래량4 (선택) |
| `FID_INTS_VLTL1` |  | 내재변동성1 (선택 - 이상값) |
| `FID_INTS_VLTL2` |  | 내재변동성2 (선택 - 이하값) |
| `FID_PRMM_VAL1` |  | 프리미엄값1 (선택 - 이상값) |
| `FID_PRMM_VAL2` |  | 프리미엄값2 (선택 - 이하값) |
| `FID_GEAR1` |  | 기어링1 (선택 - 이상값) |
| `FID_GEAR2` |  | 기어링2 (선택 - 이하값) |
| `FID_PRLS_QRYR_RATE1` |  | 손익분기비율1 (선택 - 이상값) |
| `FID_PRLS_QRYR_RATE2` |  | 손익분기비율2 (선택 - 이하값) |
| `FID_DELTA1` |  | 델타1 (선택 - 이상값) |
| `FID_DELTA2` |  | 델타2 (선택 - 이하값) |
| `FID_ACPR1` |  | 행사가1 (선택) |
| `FID_ACPR2` |  | 행사가2 (선택) |
| `FID_STCK_CNVR_RATE1` |  | 주식전환비율1 (선택 - 이상값) |
| `FID_STCK_CNVR_RATE2` |  | 주식전환비율2 (선택 - 이하값) |
| `FID_DIV_CLS_CODE` |  | 분류구분코드 (선택) |
| `FID_PRIT1` |  | 패리티1 (선택 - 이상값) |
| `FID_PRIT2` |  | 패리티2 (선택 - 이하값) |
| `FID_CFP1` |  | 자본지지점1 (선택 - 이상값) |
| `FID_CFP2` |  | 자본지지점2 (선택 - 이하값) |
| `FID_INPUT_NMIX_PRICE_1` |  | 지수가격1 (선택 - 이상값) |
| `FID_INPUT_NMIX_PRICE_2` |  | 지수가격2 (선택 - 이하값) |
| `FID_EGEA_VAL1` |  | E기어링값1 (선택 - 이상값) |
| `FID_EGEA_VAL2` |  | E기어링값2 (선택 - 이하값) |
| `FID_INPUT_DVDN_ERT` |  | 배당수익율 (선택 - 이상값) |
| `FID_INPUT_HIST_VLTL` |  | 역사적변동성 (선택 - 이하값) |
| `FID_THETA1` |  | 세타1 (선택 - 이상값) |
| `FID_THETA2` |  | 세타2 (선택 - 이하값) |

<details><summary>응답 필드 (43개)</summary>

| 필드 | 설명 |
|---|---|
| `bond_shrn_iscd` | 채권단축종목코드 |
| `hts_kor_isnm` | HTS한글종목명 |
| `rght_type_name` | 권리유형명 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `acpr` | 행사가 |
| `stck_cnvr_rate` | 주식전환비율 |
| `stck_lstn_date` | 주식상장일자 |
| `stck_last_tr_date` | 주식최종거래일자 |
| `hts_rmnn_dynu` | HTS잔존일수 |
| `unas_isnm` | 기초자산종목명 |
| `unas_prpr` | 기초자산현재가 |
| `unas_prdy_vrss` | 기초자산전일대비 |
| `unas_prdy_vrss_sign` | 기초자산전일대비부호 |
| `unas_prdy_ctrt` | 기초자산전일대비율 |
| `unas_acml_vol` | 기초자산누적거래량 |
| `moneyness` | MONEYNESS |
| `atm_cls_name` | ATM구분명 |
| `prit` | 패리티 |
| `delta_val` | 델타값 |
| `hts_ints_vltl` | HTS내재변동성 |
| `tmvl_val` | 시간가치값 |
| `gear` | 기어링 |
| `lvrg_val` | 레버리지값 |
| `prls_qryr_rate` | 손익분기비율 |
| `cfp` | 자본지지점 |
| `lstn_stcn` | 상장주수 |
| `pblc_co_name` | 발행회사명 |
| `lp_mbcr_name` | LP회원사명 |
| `lp_hldn_rate` | LP보유비율 |
| `elw_rght_form` | ELW권리형태 |
| `elw_ko_barrier` | 조기종료발생기준가격 |
| `apprch_rate` | 접근도 |
| `unas_shrn_iscd` | 기초자산단축종목코드 |
| `mtrt_date` | 만기일자 |
| `prmm_val` | 프리미엄값 |
| `stck_lp_fin_date` | 주식LP종료일자 |
| `tick_conv_prc` | 틱환산가 |
| `prls_qryr_stpr_prc` | 손익분기주가가격 |
| `lp_hvol` | LP보유량 |

</details>

---

<a id="expiration_stocks"></a>
### ELW 만기예정/만기종목[국내주식-184]

- **함수/폴더**: `expiration_stocks` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/expiration_stocks/expiration_stocks.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/expiration-stocks`
- **TR_ID**: `FHKEW154700C0`
- **예시**: `df = expiration_stocks(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='11547', fid_input_date_1='20240402', fid_input_date_2='20240408', fid_div_cls_code='0', fid_etc_cls_code='', fid_unas_input_iscd='000000', fid_input_iscd_2='00000', fid_blng_cls_code='0', fid_input_option_1='',)`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | W 입력 |
| `FID_COND_SCR_DIV_CODE` | Y | 11547 입력 |
| `FID_INPUT_DATE_1` | Y | 입력날짜 ~ (ex) 20240402) |
| `FID_INPUT_DATE_2` | Y | ~입력날짜 (ex) 20240408) |
| `FID_DIV_CLS_CODE` | Y | 0(콜),1(풋),2(전체) |
| `FID_ETC_CLS_CODE` | Y | 공백 입력 |
| `FID_UNAS_INPUT_ISCD` | Y | 000000(전체), 2001(KOSPI 200), 기초자산코드(종목코드 ex. 삼성전자-005930) |
| `FID_INPUT_ISCD_2` | Y | 00000(전체), 00003(한국투자증권), 00017(KB증권), 00005(미래에셋증권) |
| `FID_BLNG_CLS_CODE` | Y | 0(전체),1(일반),2(조기종료) |
| `FID_INPUT_OPTION_1` | Y | 공백 입력 |

<details><summary>응답 필드 (21개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW단축종목코드 |
| `elw_kor_isnm` | ELW한글종목명 |
| `unas_isnm` | 기초자산종목명 |
| `unas_prpr` | 기초자산현재가 |
| `acpr` | 행사가 |
| `stck_cnvr_rate` | 주식전환비율 |
| `elw_prpr` | ELW현재가 |
| `stck_lstn_date` | 주식상장일자 |
| `stck_last_tr_date` | 주식최종거래일자 |
| `total_rdmp_amt` | 총상환금액 |
| `rdmp_amt` | 상환금액 |
| `lstn_stcn` | 상장주수 |
| `lp_hvol` | LP보유량 |
| `ccls_paym_prc` | 확정지급2가격 |
| `mtrt_vltn_amt` | 만기평가금액 |
| `evnt_prd_fin_date` | 행사2기간종료일자 |
| `stlm_date` | 결제일자 |
| `pblc_prc` | 발행가격 |
| `unas_shrn_iscd` | 기초자산단축종목코드 |
| `stnd_iscd` | 표준종목코드 |
| `rdmp_ask_amt` | 상환청구금액 |

</details>

---

<a id="indicator"></a>
### ELW 지표순위[국내주식-169]

- **함수/폴더**: `indicator` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/indicator/indicator.py)
- **Method / URL**: `GET /uapi/elw/v1/ranking/indicator`
- **TR_ID**: `FHPEW02790000`
- **예시**: `df = indicator(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='20279', fid_unas_input_iscd='000000', fid_input_iscd='00000', fid_div_cls_code='0', fid_input_price_1='1000', fid_input_price_2='5000', fid_input_vol_1='100', fid_input_vol_2='1000', fid_rank_sort_cls_code='0', fid_blng_cls_code='0')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (필수) |
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드 (필수) |
| `FID_UNAS_INPUT_ISCD` | Y | 기초자산입력종목코드 (필수) |
| `FID_INPUT_ISCD` | Y | 발행사 (필수) |
| `FID_DIV_CLS_CODE` | Y | 콜풋구분코드 (필수) |
| `FID_INPUT_PRICE_1` | Y | 가격(이상) (필수) |
| `FID_INPUT_PRICE_2` | Y | 가격(이하) (필수) |
| `FID_INPUT_VOL_1` | Y | 거래량(이상) (필수) |
| `FID_INPUT_VOL_2` | Y | 거래량(이하) (필수) |
| `FID_RANK_SORT_CLS_CODE` | Y | 순위정렬구분코드 (필수) |
| `FID_BLNG_CLS_CODE` | Y | 결재방법 (필수) |

<details><summary>응답 필드 (13개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW단축종목코드 |
| `elw_kor_isnm` | ELW한글종목명 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `stck_cnvr_rate` | 주식전환비율 |
| `lvrg_val` | 레버리지값 |
| `acpr` | 행사가 |
| `tmvl_val` | 시간가치값 |
| `invl_val` | 내재가치값 |
| `elw_ko_barrier` | 조기종료발생기준가격 |

</details>

---

<a id="indicator_trend_ccnl"></a>
### ELW 투자지표추이(체결)[국내주식-172]

- **함수/폴더**: `indicator_trend_ccnl` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/indicator_trend_ccnl/indicator_trend_ccnl.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/indicator-trend-ccnl`
- **TR_ID**: `FHPEW02740100`
- **예시**: `df = indicator_trend_ccnl("W", "58J297")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (필수) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (필수) |

<details><summary>응답 필드 (12개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_cntg_hour` | 주식체결시간 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_vrss` | 전일대비 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `lvrg_val` | 레버리지값 |
| `gear` | 기어링 |
| `tmvl_val` | 시간가치값 |
| `invl_val` | 내재가치값 |
| `prit` | 패리티 |
| `apprch_rate` | 접근도 |

</details>

---

<a id="indicator_trend_daily"></a>
### ELW 투자지표추이(일별)[국내주식-173]

- **함수/폴더**: `indicator_trend_daily` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/indicator_trend_daily/indicator_trend_daily.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/indicator-trend-daily`
- **TR_ID**: `FHPEW02740200`
- **예시**: `df = indicator_trend_daily('W', '57K281')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 시장 분류 코드 (예: 'W') |
| `FID_INPUT_ISCD` | Y | 종목코드 (6자리, 예: '57K281') |

<details><summary>응답 필드 (15개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_bsop_date` | 주식영업일자 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_vrss` | 전일대비 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `lvrg_val` | 레버리지값 |
| `gear` | 기어링 |
| `tmvl_val` | 시간가치값 |
| `invl_val` | 내재가치값 |
| `prit` | 패리티 |
| `elw_oprc` | ELW시가2 |
| `elw_hgpr` | ELW최고가 |
| `elw_lwpr` | ELW최저가 |
| `apprch_rate` | 접근도 |

</details>

---

<a id="indicator_trend_minute"></a>
### ELW 투자지표추이(분별)[국내주식-174]

- **함수/폴더**: `indicator_trend_minute` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/indicator_trend_minute/indicator_trend_minute.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/indicator-trend-minute`
- **TR_ID**: `FHPEW02740300`
- **예시**: `df = indicator_trend_minute(fid_cond_mrkt_div_code='W', fid_input_iscd='58J297', fid_hour_cls_code='60', fid_pw_data_incu_yn='N')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 시장구분코드 (W) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 예시: 58J297(KBJ297삼성전자콜) |
| `FID_HOUR_CLS_CODE` | Y | 시간구분코드 예시: '60(1분), 180(3분), 300(5분), 600(10분), 1800(30분), 3600(60분), 7200(60분)' |
| `FID_PW_DATA_INCU_YN` | Y | 과거데이터 포함 여부 예시: N(과거데이터포함X), Y(과거데이터포함O) |

<details><summary>응답 필드 (13개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_bsop_date` | 주식영업일자 |
| `stck_cntg_hour` | 주식체결시간 |
| `elw_prpr` | ELW현재가 |
| `elw_oprc` | ELW시가2 |
| `elw_hgpr` | ELW최고가 |
| `elw_lwpr` | ELW최저가 |
| `lvrg_val` | 레버리지값 |
| `gear` | 기어링 |
| `prmm_val` | 프리미엄값 |
| `invl_val` | 내재가치값 |
| `prit` | 패리티 |
| `acml_vol` | 누적거래량 |
| `cntg_vol` | 체결거래량 |

</details>

---

<a id="lp_trade_trend"></a>
### ELW LP매매추이[국내주식-182]

- **함수/폴더**: `lp_trade_trend` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/lp_trade_trend/lp_trade_trend.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/lp-trade-trend`
- **TR_ID**: `FHPEW03760000`
- **예시**: `df1, df2 = lp_trade_trend("W", "52K577")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 시장구분(W) |
| `FID_INPUT_ISCD` | Y | 입력종목코드(ex 52K577(미래 K577KOSDAQ150콜) |

<details><summary>응답 필드 (17개)</summary>

| 필드 | 설명 |
|---|---|
| `cntg_hour` | 체결시간 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_vrss` | 전일대비 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `acml_tr_pbmn` | 누적거래대금 |
| `lp_buy_qty` | LP매수수량 |
| `lp_sell_qty` | LP매도수량 |
| `lp_ntby_qty` | LP순매수수량 |
| `lp_buy_amt` | LP매수금액 |
| `lp_sell_amt` | LP매도금액 |
| `lp_ntby_amt` | LP순매수금액 |
| `inst_deal_qty` | 기관매매수량 |
| `frgn_deal_qty` | 외국인매매수량 |
| `prsn_deal_qty` | 개인매매수량 |
| `apprch_rate` | 접근도 |

</details>

---

<a id="newly_listed"></a>
### ELW 신규상장종목[국내주식-181]

- **함수/폴더**: `newly_listed` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/newly_listed/newly_listed.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/newly-listed`
- **TR_ID**: `FHKEW154800C0`
- **예시**: `df = newly_listed(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='11548', fid_div_cls_code='02', fid_unas_input_iscd='000000', fid_input_iscd_2='00003', fid_input_date_1='20240402', fid_blng_cls_code='0')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 시장구분코드 (W) |
| `FID_COND_SCR_DIV_CODE` | Y | Unique key(11548) |
| `FID_DIV_CLS_CODE` | Y | 전체(02), 콜(00), 풋(01) |
| `FID_UNAS_INPUT_ISCD` | Y | 'ex) 000000(전체), 2001(코스피200) , 3003(코스닥150), 005930(삼성전자) ' |
| `FID_INPUT_ISCD_2` | Y | '00003(한국투자증권), 00017(KB증권),  00005(미래에셋증권)' |
| `FID_INPUT_DATE_1` | Y | 날짜 (ex) 20240402) |
| `FID_BLNG_CLS_CODE` | Y | 0(전체), 1(일반), 2(조기종료) |

<details><summary>응답 필드 (6개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW단축종목코드 |
| `unas_isnm` | 기초자산종목명 |
| `lstn_stcn` | 상장주수 |
| `acpr` | 행사가 |
| `stck_last_tr_date` | 주식최종거래일자 |
| `elw_ko_barrier` | 조기종료발생기준가격 |

</details>

---

<a id="quick_change"></a>
### ELW 당일급변종목[국내주식-171]

- **함수/폴더**: `quick_change` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/quick_change/quick_change.py)
- **Method / URL**: `GET /uapi/elw/v1/ranking/quick-change`
- **TR_ID**: `FHPEW02870000`
- **예시**: `df = quick_change(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='20287', fid_unas_input_iscd='000000', fid_input_iscd='00000', fid_mrkt_cls_code='A', fid_input_price_1='1000', fid_input_price_2='5000', fid_input_vol_1='10000', fid_input_vol_2='50000', fid_hour_cls_code='1', fid_input_hour_1='10', fid_input_hour_2='30', fid_rank_sort_cls_code='1', fid_blng_cls_code='0')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (필수) |
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드 (필수) |
| `FID_UNAS_INPUT_ISCD` | Y | 기초자산입력종목코드 (필수) |
| `FID_INPUT_ISCD` | Y | 발행사 (필수) |
| `FID_MRKT_CLS_CODE` | Y | 시장구분코드 (필수) |
| `FID_INPUT_PRICE_1` | Y | 가격(이상) (필수) |
| `FID_INPUT_PRICE_2` | Y | 가격(이하) (필수) |
| `FID_INPUT_VOL_1` | Y | 거래량(이상) (필수) |
| `FID_INPUT_VOL_2` | Y | 거래량(이하) (필수) |
| `FID_HOUR_CLS_CODE` | Y | 시간구분코드 (필수) |
| `FID_INPUT_HOUR_1` | Y | 입력 일 또는 분 (필수) |
| `FID_INPUT_HOUR_2` | Y | 기준시간(분 선택 시) (필수) |
| `FID_RANK_SORT_CLS_CODE` | Y | 순위정렬구분코드 (필수) |
| `FID_BLNG_CLS_CODE` | Y | 결재방법 (필수) |

<details><summary>응답 필드 (14개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW단축종목코드 |
| `elw_kor_isnm` | ELW한글종목명 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_vrss` | 전일대비 |
| `prdy_ctrt` | 전일대비율 |
| `askp` | 매도호가 |
| `bidp` | 매수호가 |
| `total_askp_rsqn` | 총매도호가잔량 |
| `total_bidp_rsqn` | 총매수호가잔량 |
| `acml_vol` | 누적거래량 |
| `stnd_val` | 기준값 |
| `stnd_val_vrss` | 기준값대비 |
| `stnd_val_ctrt` | 기준값대비율 |

</details>

---

<a id="sensitivity"></a>
### ELW 민감도 순위[국내주식-170]

- **함수/폴더**: `sensitivity` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/sensitivity/sensitivity.py)
- **Method / URL**: `GET /uapi/elw/v1/ranking/sensitivity`
- **TR_ID**: `FHPEW02850000`
- **예시**: `df = sensitivity(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='20285', fid_unas_input_iscd='000000', fid_input_iscd='00000', fid_div_cls_code='0', fid_input_price_1='0', fid_input_price_2='100000', fid_input_vol_1='0', fid_input_vol_2='1000000', fid_rank_sort_cls_code='0', fid_input_rmnn_dynu_1='0', fid_input_date_1='20230101', fid_blng_cls_code='0')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 |
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드 |
| `FID_UNAS_INPUT_ISCD` | Y | 기초자산입력종목코드 |
| `FID_INPUT_ISCD` | Y | 입력종목코드 |
| `FID_DIV_CLS_CODE` | Y | 콜풋구분코드 |
| `FID_INPUT_PRICE_1` | Y | 가격(이상) |
| `FID_INPUT_PRICE_2` | Y | 가격(이하) |
| `FID_INPUT_VOL_1` | Y | 거래량(이상) |
| `FID_INPUT_VOL_2` | Y | 거래량(이하) |
| `FID_RANK_SORT_CLS_CODE` | Y | 순위정렬구분코드 |
| `FID_INPUT_RMNN_DYNU_1` | Y | 잔존일수(이상) |
| `FID_INPUT_DATE_1` | Y | 조회기준일 |
| `FID_BLNG_CLS_CODE` | Y | 결재방법 |

<details><summary>응답 필드 (15개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW단축종목코드 |
| `elw_kor_isnm` | ELW한글종목명 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `hts_thpr` | HTS이론가 |
| `delta_val` | 델타값 |
| `gama` | 감마 |
| `theta` | 세타 |
| `vega` | 베가 |
| `rho` | 로우 |
| `hts_ints_vltl` | HTS내재변동성 |
| `d90_hist_vltl` | 90일역사적변동성 |

</details>

---

<a id="sensitivity_trend_ccnl"></a>
### ELW 민감도 추이(체결)[국내주식-175]

- **함수/폴더**: `sensitivity_trend_ccnl` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/sensitivity_trend_ccnl/sensitivity_trend_ccnl.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/sensitivity-trend-ccnl`
- **TR_ID**: `FHPEW02830100`
- **예시**: `df = sensitivity_trend_ccnl('W', '58J297')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (필수) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (필수) |

<details><summary>응답 필드 (11개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_cntg_hour` | 주식체결시간 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `hts_thpr` | hts 이론가 |
| `delta_val` | 델타 값 |
| `gama` | 감마 |
| `theta` | 세타 |
| `vega` | 베가 |
| `rho` | 로우 |

</details>

---

<a id="sensitivity_trend_daily"></a>
### ELW 민감도 추이(일별)[국내주식-176]

- **함수/폴더**: `sensitivity_trend_daily` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/sensitivity_trend_daily/sensitivity_trend_daily.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/sensitivity-trend-daily`
- **TR_ID**: `FHPEW02830200`
- **예시**: `df = sensitivity_trend_daily("W", "58J438")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (필수) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (필수) |

<details><summary>응답 필드 (11개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_bsop_date` | 주식영업일자 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `hts_thpr` | HTS이론가 |
| `delta_val` | 델타값 |
| `gama` | 감마 |
| `theta` | 세타 |
| `vega` | 베가 |
| `rho` | 로우 |

</details>

---

<a id="udrl_asset_list"></a>
### ELW 기초자산 목록조회[국내주식-185]

- **함수/폴더**: `udrl_asset_list` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/udrl_asset_list/udrl_asset_list.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/udrl-asset-list`
- **TR_ID**: `FHKEW154100C0`
- **예시**: `df = udrl_asset_list('11541', '0', '00000')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드, 예: '11541' |
| `FID_RANK_SORT_CLS_CODE` | Y | 순위정렬구분코드, 예: '0', '1', '2', '3', '4', '5', '6' |
| `FID_INPUT_ISCD` | Y | 입력종목코드, 예: '00000', '00003', '00017', '00005' |

<details><summary>응답 필드 (6개)</summary>

| 필드 | 설명 |
|---|---|
| `unas_shrn_iscd` | 기초자산단축종목코드 |
| `unas_isnm` | 기초자산종목명 |
| `unas_prpr` | 기초자산현재가 |
| `unas_prdy_vrss` | 기초자산전일대비 |
| `unas_prdy_vrss_sign` | 기초자산전일대비부호 |
| `unas_prdy_ctrt` | 기초자산전일대비율 |

</details>

---

<a id="udrl_asset_price"></a>
### ELW 기초자산별 종목시세

- **함수/폴더**: `udrl_asset_price` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/udrl_asset_price/udrl_asset_price.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/udrl-asset-price`
- **TR_ID**: `FHKEW154101C0`
- **예시**: `df = udrl_asset_price(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='11541', fid_mrkt_cls_code='A', fid_input_iscd='00000', fid_unas_input_iscd='005930', fid_vol_cnt='1000', fid_trgt_exls_cls_code='0', fid_input_price_1='1000', fid_input_price_2='5000', fid_input_vol_1='100', fid_input_vol_2='500', fid_input_rmnn_dynu_1='10', fid_input_rmnn_dynu_2='20', fid_option='0', fid_input_option_1='', fid_input_option_2='')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 시장구분(W) |
| `FID_COND_SCR_DIV_CODE` | Y | Uniquekey(11541) |
| `FID_MRKT_CLS_CODE` | Y | 전체(A),콜(C),풋(P) |
| `FID_INPUT_ISCD` | Y | '00000(전체), 00003(한국투자증권) , 00017(KB증권), 00005(미래에셋주식회사)' |
| `FID_UNAS_INPUT_ISCD` | Y | 기초자산입력종목코드 |
| `FID_VOL_CNT` | Y | 전일거래량(정수량미만) |
| `FID_TRGT_EXLS_CLS_CODE` | Y | 거래불가종목제외(0:미체크,1:체크) |
| `FID_INPUT_PRICE_1` | Y | 가격~원이상 |
| `FID_INPUT_PRICE_2` | Y | 가격~월이하 |
| `FID_INPUT_VOL_1` | Y | 거래량~계약이상 |
| `FID_INPUT_VOL_2` | Y | 거래량~계약이하 |
| `FID_INPUT_RMNN_DYNU_1` | Y | 잔존일(~일이상) |
| `FID_INPUT_RMNN_DYNU_2` | Y | 잔존일(~일이하) |
| `FID_OPTION` | Y | 옵션상태(0:없음,1:ATM,2:ITM,3:OTM) |
| `FID_INPUT_OPTION_1` | Y | 입력옵션1 |
| `FID_INPUT_OPTION_2` | Y | 입력옵션2 |

<details><summary>응답 필드 (29개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_shrn_iscd` | ELW단축종목코드 |
| `hts_kor_isnm` | HTS한글종목명 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `acpr` | 행사가 |
| `prls_qryr_stpr_prc` | 손익분기주가가격 |
| `hts_rmnn_dynu` | HTS잔존일수 |
| `hts_ints_vltl` | HTS내재변동성 |
| `stck_cnvr_rate` | 주식전환비율 |
| `lp_hvol` | LP보유량 |
| `lp_rlim` | LP비중 |
| `lvrg_val` | 레버리지값 |
| `gear` | 기어링 |
| `delta_val` | 델타값 |
| `gama` | 감마 |
| `vega` | 베가 |
| `theta` | 세타 |
| `prls_qryr_rate` | 손익분기비율 |
| `cfp` | 자본지지점 |
| `prit` | 패리티 |
| `invl_val` | 내재가치값 |
| `tmvl_val` | 시간가치값 |
| `hts_thpr` | HTS이론가 |
| `stck_lstn_date` | 주식상장일자 |
| `stck_last_tr_date` | 주식최종거래일자 |
| `lp_ntby_qty` | LP순매도량 |

</details>

---

<a id="updown_rate"></a>
### ELW 상승률순위[국내주식-167]

- **함수/폴더**: `updown_rate` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/updown_rate/updown_rate.py)
- **Method / URL**: `GET /uapi/elw/v1/ranking/updown-rate`
- **TR_ID**: `FHPEW02770000`
- **예시**: `df = updown_rate(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='20277', fid_unas_input_iscd='000000', fid_input_iscd='00000', fid_input_rmnn_dynu_1='0', fid_div_cls_code='0', fid_input_price_1='', fid_input_price_2='', fid_input_vol_1='', fid_input_vol_2='', fid_input_date_1='1', fid_rank_sort_cls_code='0', fid_blng_cls_code='0', fid_input_date_2='')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 시장구분코드 (W) |
| `FID_COND_SCR_DIV_CODE` | Y | Unique key(20277) |
| `FID_UNAS_INPUT_ISCD` | Y | '000000(전체), 2001(코스피200) , 3003(코스닥150), 005930(삼성전자) ' |
| `FID_INPUT_ISCD` | Y | '00000(전체), 00003(한국투자증권) , 00017(KB증권), 00005(미래에셋주식회사)' |
| `FID_INPUT_RMNN_DYNU_1` | Y | '0(전체), 1(1개월이하), 2(1개월~2개월),  3(2개월~3개월), 4(3개월~6개월), 5(6개월~9개월),6(9개월~12개월), 7(12개월이상)' |
| `FID_DIV_CLS_CODE` | Y | 0(전체), 1(콜), 2(풋) |
| `FID_INPUT_PRICE_1` | Y | 사용자권한정보 |
| `FID_INPUT_PRICE_2` | Y | 거래소코드 |
| `FID_INPUT_VOL_1` | Y | 상승율/하락율 구분 |
| `FID_INPUT_VOL_2` | Y | N일자값 |
| `FID_INPUT_DATE_1` | Y | 거래량조건 |
| `FID_RANK_SORT_CLS_CODE` | Y | '0(상승율), 1(하락율), 2(시가대비상승율) , 3(시가대비하락율), 4(변동율)' |
| `FID_BLNG_CLS_CODE` | Y | 0(전체) |
| `FID_INPUT_DATE_2` | Y | 거래소코드 |

<details><summary>응답 필드 (35개)</summary>

| 필드 | 설명 |
|---|---|
| `hts_kor_isnm` | HTS한글종목명 |
| `elw_shrn_iscd` | ELW단축종목코드 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `acml_vol` | 누적거래량 |
| `stck_sdpr` | 주식기준가 |
| `sdpr_vrss_prpr_sign` | 기준가대비현재가부호 |
| `sdpr_vrss_prpr` | 기준가대비현재가 |
| `sdpr_vrss_prpr_rate` | 기준가대비현재가비율 |
| `stck_oprc` | 주식시가2 |
| `oprc_vrss_prpr_sign` | 시가2대비현재가부호 |
| `oprc_vrss_prpr` | 시가2대비현재가 |
| `oprc_vrss_prpr_rate` | 시가2대비현재가비율 |
| `stck_hgpr` | 주식최고가 |
| `stck_lwpr` | 주식최저가 |
| `prd_rsfl_sign` | 기간등락부호 |
| `prd_rsfl` | 기간등락 |
| `prd_rsfl_rate` | 기간등락비율 |
| `stck_cnvr_rate` | 주식전환비율 |
| `hts_rmnn_dynu` | HTS잔존일수 |
| `acpr` | 행사가 |
| `unas_isnm` | 기초자산명 |
| `unas_shrn_iscd` | 기초자산코드 |
| `lp_hldn_rate` | LP보유비율 |
| `prit` | 패리티 |
| `prls_qryr_stpr_prc` | 손익분기주가가격 |
| `delta_val` | 델타값 |
| `theta` | 세타 |
| `prls_qryr_rate` | 손익분기비율 |
| `stck_lstn_date` | 주식상장일자 |
| `stck_last_tr_date` | 주식최종거래일자 |
| `hts_ints_vltl` | HTS내재변동성 |
| `lvrg_val` | 레버리지값 |

</details>

---

<a id="volatility_trend_ccnl"></a>
### ELW 변동성추이(체결)[국내주식-177]

- **함수/폴더**: `volatility_trend_ccnl` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/volatility_trend_ccnl/volatility_trend_ccnl.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/volatility-trend-ccnl`
- **TR_ID**: `FHPEW02840100`
- **예시**: `df = volatility_trend_ccnl("W", "58J297")`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (필수) |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (필수) |

<details><summary>응답 필드 (9개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_cntg_hour` | 주식체결시간 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `bidp` | 매수호가 |
| `askp` | 매도호가 |
| `acml_vol` | 누적거래량 |
| `hts_ints_vltl` | HTS내재변동성 |

</details>

---

<a id="volatility_trend_daily"></a>
### ELW 변동성추이(일별)[국내주식-178]

- **함수/폴더**: `volatility_trend_daily` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/volatility_trend_daily/volatility_trend_daily.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/volatility-trend-daily`
- **TR_ID**: `FHPEW02840200`
- **예시**: `df = volatility_trend_daily('W', '58J297')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (예: 'W') |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (예: '58J297') |

<details><summary>응답 필드 (15개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_bsop_date` | 주식 영업 일자 |
| `elw_prpr` | ELW 현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `elw_oprc` | elw 시가2 |
| `elw_hgpr` | elw 최고가 |
| `elw_lwpr` | elw 최저가 |
| `acml_vol` | 누적 거래량 |
| `d10_hist_vltl` | 10일 역사적 변동성 |
| `d20_hist_vltl` | 20일 역사적 변동성 |
| `d30_hist_vltl` | 30일 역사적 변동성 |
| `d60_hist_vltl` | 60일 역사적 변동성 |
| `d90_hist_vltl` | 90일 역사적 변동성 |
| `hts_ints_vltl` | HTS 내재 변동성 |

</details>

---

<a id="volatility_trend_minute"></a>
### ELW 변동성 추이(분별)

- **함수/폴더**: `volatility_trend_minute` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/volatility_trend_minute/volatility_trend_minute.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/volatility-trend-minute`
- **TR_ID**: `FHPEW02840300`
- **예시**: `df = volatility_trend_minute(fid_cond_mrkt_div_code='W', fid_input_iscd='58J297', fid_hour_cls_code='60', fid_pw_data_incu_yn='N')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (예: 'W') |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (예: '58J297') |
| `FID_HOUR_CLS_CODE` | Y | 시간구분코드 (예: '60', '180', '300', '600', '1800', '3600') |
| `FID_PW_DATA_INCU_YN` | Y | 과거데이터 포함 여부 ('N' 또는 'Y') |

<details><summary>응답 필드 (8개)</summary>

| 필드 | 설명 |
|---|---|
| `stck_bsop_date` | 주식 영업 일자 |
| `stck_cntg_hour` | 주식 체결 시간 |
| `stck_prpr` | 주식 현재가 |
| `elw_oprc` | ELW 시가2 |
| `elw_hgpr` | ELW 최고가 |
| `elw_lwpr` | ELW 최저가 |
| `hts_ints_vltl` | HTS 내재 변동성 |
| `hist_vltl` | 역사적 변동성 |

</details>

---

<a id="volatility_trend_tick"></a>
### ELW 변동성추이(틱)[국내주식-180]

- **함수/폴더**: `volatility_trend_tick` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/volatility_trend_tick/volatility_trend_tick.py)
- **Method / URL**: `GET /uapi/elw/v1/quotations/volatility-trend-tick`
- **TR_ID**: `FHPEW02840400`
- **예시**: `df = volatility_trend_tick('W', '58J297')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (예: 'W') |
| `FID_INPUT_ISCD` | Y | 입력종목코드 (예: '58J297') |

<details><summary>응답 필드 (4개)</summary>

| 필드 | 설명 |
|---|---|
| `bsop_date` | 주식영업일자 |
| `stck_cntg_hour` | ELW현재가 |
| `elw_prpr` | 전일대비 |
| `hts_ints_vltl` | 전일대비부호 |

</details>

---

<a id="volume_rank"></a>
### ELW 거래량순위[국내주식-168]

- **함수/폴더**: `volume_rank` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/elw/volume_rank/volume_rank.py)
- **Method / URL**: `GET /uapi/elw/v1/ranking/volume-rank`
- **TR_ID**: `FHPEW02780000`
- **예시**: `df = volume_rank(fid_cond_mrkt_div_code='W', fid_cond_scr_div_code='20278', fid_unas_input_iscd='000000', fid_input_iscd='00000', fid_input_rmnn_dynu_1='', fid_div_cls_code='0', fid_input_price_1='1000', fid_input_price_2='5000', fid_input_vol_1='100', fid_input_vol_2='1000', fid_input_date_1='20230101', fid_rank_sort_cls_code='0', fid_blng_cls_code='0', fid_input_iscd_2='0000', fid_input_date_2='')`

**요청 파라미터** (Query)

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `FID_COND_MRKT_DIV_CODE` | Y | 조건시장분류코드 (예: 'W') |
| `FID_COND_SCR_DIV_CODE` | Y | 조건화면분류코드 (예: '20278') |
| `FID_UNAS_INPUT_ISCD` | Y | 기초자산입력종목코드 (예: '000000') |
| `FID_INPUT_ISCD` | Y | 발행사 (예: '00000') |
| `FID_INPUT_RMNN_DYNU_1` | Y | 입력잔존일수 |
| `FID_DIV_CLS_CODE` | Y | 콜풋구분코드 (예: '0') |
| `FID_INPUT_PRICE_1` | Y | 가격(이상) |
| `FID_INPUT_PRICE_2` | Y | 가격(이하) |
| `FID_INPUT_VOL_1` | Y | 거래량(이상) |
| `FID_INPUT_VOL_2` | Y | 거래량(이하) |
| `FID_INPUT_DATE_1` | Y | 조회기준일 |
| `FID_RANK_SORT_CLS_CODE` | Y | 순위정렬구분코드 (예: '0') |
| `FID_BLNG_CLS_CODE` | Y | 소속구분코드 (예: '0') |
| `FID_INPUT_ISCD_2` | Y | LP발행사 (예: '0000') |
| `FID_INPUT_DATE_2` | Y | 만기일-최종거래일조회 |

<details><summary>응답 필드 (41개)</summary>

| 필드 | 설명 |
|---|---|
| `elw_kor_isnm` | ELW한글종목명 |
| `elw_shrn_iscd` | ELW단축종목코드 |
| `elw_prpr` | ELW현재가 |
| `prdy_vrss` | 전일대비 |
| `prdy_vrss_sign` | 전일대비부호 |
| `prdy_ctrt` | 전일대비율 |
| `lstn_stcn` | 상장주수 |
| `acml_vol` | 누적거래량 |
| `n_prdy_vol` | N전일거래량 |
| `n_prdy_vol_vrss` | N전일거래량대비 |
| `vol_inrt` | 거래량증가율 |
| `vol_tnrt` | 거래량회전율 |
| `nday_vol_tnrt` | N일거래량회전율 |
| `acml_tr_pbmn` | 누적거래대금 |
| `n_prdy_tr_pbmn` | N전일거래대금 |
| `n_prdy_tr_pbmn_vrss` | N전일거래대금대비 |
| `total_askp_rsqn` | 총매도호가잔량 |
| `total_bidp_rsqn` | 총매수호가잔량 |
| `ntsl_rsqn` | 순매도잔량 |
| `ntby_rsqn` | 순매수잔량 |
| `seln_rsqn_rate` | 매도잔량비율 |
| `shnu_rsqn_rate` | 매수2잔량비율 |
| `stck_cnvr_rate` | 주식전환비율 |
| `hts_rmnn_dynu` | HTS잔존일수 |
| `invl_val` | 내재가치값 |
| `tmvl_val` | 시간가치값 |
| `acpr` | 행사가 |
| `unas_isnm` | 기초자산명 |
| `stck_last_tr_date` | 최종거래일 |
| `unas_shrn_iscd` | 기초자산코드 |
| `prdy_vol` | 전일거래량 |
| `lp_hldn_rate` | LP보유비율 |
| `prit` | 패리티 |
| `prls_qryr_stpr_prc` | 손익분기주가가격 |
| `delta_val` | 델타값 |
| `theta` | 세타 |
| `prls_qryr_rate` | 손익분기비율 |
| `stck_lstn_date` | 주식상장일자 |
| `hts_ints_vltl` | HTS내재변동성 |
| `lvrg_val` | 레버리지값 |
| `lp_ntby_qty` | LP순매도량 |

</details>

---
