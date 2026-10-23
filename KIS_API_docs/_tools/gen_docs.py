"""Generate KIS_API_docs markdown from apis.json."""
import csv
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

PRODUCT_DIR = OrderedDict([
    ("인증", "01_인증"),
    ("국내주식", "02_국내주식"),
    ("국내선물옵션", "03_국내선물옵션"),
    ("해외주식", "04_해외주식"),
    ("해외선물옵션", "05_해외선물옵션"),
    ("장내채권", "06_장내채권"),
])
# examples_llm 폴더 → 상품 (헤더 표기가 들쭉날쭉해서 폴더 기준으로 보정)
DIR_PRODUCT = {
    "auth": "인증", "domestic_stock": "국내주식", "elw": "국내주식", "etfetn": "국내주식",
    "domestic_futureoption": "국내선물옵션", "overseas_stock": "해외주식",
    "overseas_futureoption": "해외선물옵션", "domestic_bond": "장내채권",
}
SUB_ORDER = ["OAuth인증", "주문/계좌", "기본시세", "ELW시세", "ETF/ETN", "업종/기타", "종목정보",
             "시세분석", "순위분석", "실시간시세", "기타"]

GH = "https://github.com/koreainvestment/open-trading-api/blob/main/"


def clean_name(name):
    return re.sub(r"\s+", " ", name).strip()


def simplify_when(when):
    if not when:
        return "공통"
    terms = [t for t in re.split(r"\s+and\s+", when) if not t.startswith("not (")]
    s = " and ".join(terms) if terms else when
    return s.replace("'", "")


def esc(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def norm_sub(api):
    sub = (api["sub"] or "").strip()
    if api["category_dir"] == "auth":
        return "OAuth인증"
    if api["category_dir"] == "elw" and api["method"] != "WEBSOCKET":
        return "ELW시세"
    if api["category_dir"] == "etfetn":
        return "ETF/ETN"
    sub = sub.replace("ELW시세", "ELW시세")
    if sub in SUB_ORDER:
        return sub
    if "실시간" in sub:
        return "실시간시세"
    return sub or "기타"


def slug(s):
    return s.replace("/", "_")


def render_api(a):
    L = []
    L.append(f"### {esc(clean_name(a['name']))}")
    L.append("")
    L.append(f"- **함수/폴더**: `{a['folder']}` · [샘플코드]({GH}{a['source']})")
    if a["method"] == "WEBSOCKET":
        L.append("- **방식**: WebSocket 구독 (실전 `ws://ops.koreainvestment.com:21000`, 모의 `:31000`)")
    else:
        L.append(f"- **Method / URL**: `{a['method']} {a['url']}`")
    if a["tr_ids"]:
        if len(a["tr_ids"]) == 1 and not a["tr_ids"][0]["when"]:
            L.append(f"- **TR_ID**: `{a['tr_ids'][0]['tr_id']}`")
        else:
            L.append("- **TR_ID**:")
            merged = OrderedDict()
            for t in a["tr_ids"]:
                merged.setdefault(t["tr_id"], []).append(simplify_when(t["when"]))
            for tid, conds in merged.items():
                if set(conds) == {"env_dv == real", "env_dv == demo"}:
                    txt = "실전/모의 공통"
                else:
                    txt = " / ".join(conds)
                L.append(f"  - `{tid}` — {esc(txt)}")
    if a["example"]:
        L.append(f"- **예시**: `{a['example']}`")
    L.append("")

    argdesc = {x["name"]: x for x in a["args"]}
    if a["params"]:
        kind = "Body(JSON)" if a["method"] == "POST" else ("body.input" if a["method"] == "WEBSOCKET" else "Query")
        L.append(f"**요청 파라미터** ({kind})")
        L.append("")
        L.append("| 필드 | 필수 | 설명 |")
        L.append("|---|:-:|---|")
        for p in a["params"]:
            arg = argdesc.get(p["arg"])
            if arg:
                req = "Y" if arg["required"] else ""
                desc = arg["desc"] or p["comment"]
                if p["comment"] and p["comment"] not in desc:
                    desc = f"{p['comment']} — {desc}"
            else:
                req = ""
                desc = p["comment"] or f"고정값 `{p['arg']}`"
            L.append(f"| `{p['field']}` | {req} | {esc(desc)} |")
        L.append("")
    # 파라미터에 안 들어가는 함수 인자(env_dv, ord_dv 등 TR_ID 결정용)
    used = {p["arg"] for p in a["params"]}
    extra = [x for x in a["args"] if x["name"] not in used]
    if extra:
        L.append("**TR_ID/동작 결정 인자** (샘플 함수 인자)")
        L.append("")
        for x in extra:
            L.append(f"- `{x['name']}`{' (필수)' if x['required'] else ''}: {esc(x['desc'])}")
        L.append("")
    if a["outputs"]:
        L.append("<details><summary>응답 필드 ({}개)</summary>".format(len(a["outputs"])))
        L.append("")
        L.append("| 필드 | 설명 |")
        L.append("|---|---|")
        for k, v in a["outputs"].items():
            L.append(f"| `{k}` | {esc(v)} |")
        L.append("")
        L.append("</details>")
        L.append("")
    elif a["ws_columns"]:
        L.append("<details><summary>수신 컬럼 순서 ({}개, `^` 구분)</summary>".format(len(a["ws_columns"])))
        L.append("")
        L.append(", ".join(f"`{c}`" for c in a["ws_columns"]))
        L.append("")
        L.append("</details>")
        L.append("")
    L.append("---")
    L.append("")
    return "\n".join(L)


def main():
    apis = json.loads(SRC.read_text(encoding="utf-8"))
    groups = OrderedDict((p, OrderedDict()) for p in PRODUCT_DIR)
    for a in apis:
        # 인증 API는 requests.post 직접 호출이라 파서가 GET으로 잡음 → 보정
        if a["folder"] in ("auth_token", "auth_ws_token"):
            a["method"] = "POST"
            secret = "appsecret" if a["folder"] == "auth_token" else "secretkey"
            a["params"] = [
                {"field": "grant_type", "arg": "grant_type", "comment": ""},
                {"field": "appkey", "arg": "appkey", "comment": ""},
                {"field": secret, "arg": "appsecret", "comment": "웹소켓 접속키는 필드명이 secretkey" if secret == "secretkey" else ""},
            ]
        prod = DIR_PRODUCT[a["category_dir"]]
        sub = norm_sub(a)
        a["_product"], a["_sub"] = prod, sub
        groups[prod].setdefault(sub, []).append(a)

    index_rows = []
    readme_toc = []
    for prod, subs in groups.items():
        pdir = OUT / PRODUCT_DIR[prod]
        pdir.mkdir(parents=True, exist_ok=True)
        ordered = sorted(subs.items(), key=lambda kv: SUB_ORDER.index(kv[0]) if kv[0] in SUB_ORDER else 99)
        readme_toc.append(f"### {prod}")
        readme_toc.append("")
        for i, (sub, items) in enumerate(ordered, 1):
            fname = f"{i:02d}_{slug(sub)}.md"
            body = [f"# [{prod}] {sub}", "",
                    f"> 출처: 한국투자증권 공식 저장소 `koreainvestment/open-trading-api` (examples_llm) 자동 추출. "
                    f"공통 규칙(도메인·헤더·토큰·연속조회·웹소켓)은 [공통 가이드](../00_공통_가이드.md) 참고.", "",
                    "## 목록", "",
                    "| API | Method | URL | TR_ID |", "|---|---|---|---|"]
            for a in items:
                trs = ", ".join(sorted({t["tr_id"] for t in a["tr_ids"]}))
                anchor = a["folder"]
                body.append(f"| [{esc(clean_name(a['name']))}](#{anchor}) | {a['method']} | `{a['url'] or '-'}` | {trs} |")
            body.append("")
            for a in items:
                body.append(f'<a id="{a["folder"]}"></a>')
                body.append(render_api(a))
                index_rows.append({
                    "상품": prod, "분류": sub, "API명": clean_name(a["name"]), "method": a["method"],
                    "url": a["url"] or "", "tr_id": " ".join(t["tr_id"] for t in a["tr_ids"]),
                    "샘플함수": a["folder"], "문서": f"{PRODUCT_DIR[prod]}/{fname}",
                })
            (pdir / fname).write_text("\n".join(body), encoding="utf-8")
            readme_toc.append(f"- [{sub}]({PRODUCT_DIR[prod]}/{fname}) — {len(items)}개")
        readme_toc.append("")

    with open(OUT / "INDEX.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index_rows[0].keys()))
        w.writeheader()
        w.writerows(index_rows)
    (OUT / "apis.json").write_text(json.dumps(
        [{k: v for k, v in a.items() if not k.startswith("_")} for a in apis],
        ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "_toc.md").write_text("\n".join(readme_toc), encoding="utf-8")
    print(len(index_rows), "rows")


if __name__ == "__main__":
    main()
