# [인증] OAuth인증

> 출처: 한국투자증권 공식 저장소 `koreainvestment/open-trading-api` (examples_llm) 자동 추출. 공통 규칙(도메인·헤더·토큰·연속조회·웹소켓)은 [공통 가이드](../00_공통_가이드.md) 참고.

## 목록

| API | Method | URL | TR_ID |
|---|---|---|---|
| [OAuth 접근토큰 발급](#auth_token) | POST | `/oauth2/tokenP` |  |
| [WebSocket 웹소켓 접속키 발급](#auth_ws_token) | POST | `/oauth2/Approval` |  |

<a id="auth_token"></a>
### OAuth 접근토큰 발급

- **함수/폴더**: `auth_token` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/auth/auth_token/auth_token.py)
- **Method / URL**: `POST /oauth2/tokenP`
- **예시**: `df = auth_token(grant_type="client_credentials", appkey=trenv.my_app, appsecret=trenv.my_sec, env_dv="real")`

**요청 파라미터** (Body(JSON))

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `grant_type` | Y | 권한부여 Type (client_credentials) |
| `appkey` | Y | 앱키 (한국투자증권 홈페이지에서 발급받은 appkey) |
| `appsecret` | Y | 앱시크릿키 (한국투자증권 홈페이지에서 발급받은 appsecret) |

**TR_ID/동작 결정 인자** (샘플 함수 인자)

- `env_dv` (필수): 환경구분 (real: 실전, demo: 모의)

<details><summary>응답 필드 (4개)</summary>

| 필드 | 설명 |
|---|---|
| `access_token` | 접근토큰 |
| `token_type` | 접근토큰유형 |
| `expires_in` | 접근토큰유효기간_초 |
| `access_token_token_expired` | 접근토큰유효기간_일시표시 |

</details>

---

<a id="auth_ws_token"></a>
### WebSocket 웹소켓 접속키 발급

- **함수/폴더**: `auth_ws_token` · [샘플코드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/auth/auth_ws_token/auth_ws_token.py)
- **Method / URL**: `POST /oauth2/Approval`
- **예시**: `df = auth_ws_token(grant_type="client_credentials", appkey=trenv.my_app, appsecret=trenv.my_sec, env_dv="real")`

**요청 파라미터** (Body(JSON))

| 필드 | 필수 | 설명 |
|---|:-:|---|
| `grant_type` | Y | 권한부여 Type (client_credentials) |
| `appkey` | Y | 고객 앱Key (한국투자증권 홈페이지에서 발급받은 appkey) |
| `secretkey` | Y | 웹소켓 접속키는 필드명이 secretkey — 고객 앱Secret (한국투자증권 홈페이지에서 발급받은 appsecret) |

**TR_ID/동작 결정 인자** (샘플 함수 인자)

- `env_dv` (필수): 환경구분 (real: 실전, demo: 모의)
- `token`: 접근토큰 (OAuth 토큰이 필요한 API 경우 발급한 Access token)

<details><summary>응답 필드 (3개)</summary>

| 필드 | 설명 |
|---|---|
| `code` | 응답코드 |
| `message` | 응답메세지 |
| `approval_key` | 웹소켓접속키 |

</details>

---
