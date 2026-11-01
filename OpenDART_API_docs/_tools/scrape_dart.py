"""OpenDART(금융감독원 전자공시 오픈API) 개발가이드 수집 → 마크다운 문서 생성.

https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS001~DS006 의 API 목록과 각 상세 페이지
(/guide/detail.do?apiGrpCd=..&apiId=..)의 기본 정보, 요청 인자, 응답 결과, 테스트 예시값, 메시지 코드를 읽어
OpenDART_API_docs/ 아래에 분류별 md, INDEX.csv, apis.json 을 만든다.

받은 HTML 은 _tools/cache/ 에 저장해 두고 다시 실행하면 재사용한다 (--refresh 로 새로 받기).

사용 예:
    python OpenDART_API_docs/_tools/scrape_dart.py
    python OpenDART_API_docs/_tools/scrape_dart.py --refresh
"""
import argparse
import csv
import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup

BASE = "https://opendart.fss.or.kr"
DOCS = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / "cache"
GROUPS = {"DS001": "공시정보", "DS002": "정기보고서 주요정보", "DS003": "정기보고서 재무정보",
          "DS004": "지분공시 종합정보", "DS005": "주요사항보고서 주요정보", "DS006": "증권신고서 주요정보"}
INTERVAL = 0.5
STANDARD_TABLES = {"기본 정보", "요청 인자", "응답 결과", "OpenAPI 테스트", "메시지 설명"}


def fetch(path: str, refresh: bool) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_") + ".html"
    f = CACHE / name
    if f.exists() and not refresh:
        return f.read_text(encoding="utf-8")
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0 (docs builder)"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    f.write_text(html, encoding="utf-8")
    time.sleep(INTERVAL)
    return html


def text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def cell_md(s: str) -> str:
    return s.replace("|", "\\|")


def expand_table(t) -> list[list[str]]:
    """rowspan/colspan 을 펼친 셀 격자."""
    grid, carry = [], {}  # carry[col] = (남은 행 수, 값)
    for tr in t.find_all("tr"):
        row, col = [], 0
        cells = tr.find_all(["th", "td"])
        it = iter(cells)
        while True:
            if col in carry:
                n, v = carry[col]
                row.append(v)
                carry[col] = (n - 1, v)
                if n - 1 == 0:
                    del carry[col]
                col += 1
                continue
            c = next(it, None)
            if c is None:
                break
            v = text(c)
            for _ in range(int(c.get("colspan", 1))):
                row.append(v)
                rs = int(c.get("rowspan", 1))
                if rs > 1:
                    carry[col] = (rs - 1, v)
                col += 1
        while col in carry:  # 행 끝의 병합 셀
            n, v = carry[col]
            row.append(v)
            carry[col] = (n - 1, v)
            if n - 1 == 0:
                del carry[col]
            col += 1
        grid.append(row)
    return grid


def table_by_caption(soup, caption: str):
    for t in soup.find_all("table"):
        c = t.find("caption")
        if c and c.get_text(strip=True) == caption:
            return t
    return None


# ---------------------------------------------------------------- 파싱
def parse_list(html: str, grp: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.select("table tbody tr"):
        tds = tr.find_all("td")
        a = tr.find("a", href=re.compile(r"detail\.do"))
        if len(tds) < 3 or not a:
            continue
        api_id = re.search(r"apiId=(\w+)", a["href"]).group(1)
        out.append({"group_code": grp, "group": GROUPS[grp], "no": text(tds[0]), "name": text(tds[1]),
                    "desc": text(tds[2]), "api_id": api_id,
                    "guide_url": f"{BASE}/guide/detail.do?apiGrpCd={grp}&apiId={api_id}"})
    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    d = {"endpoints": [], "request": [], "response": [], "example": {}, "notes": []}
    t = table_by_caption(soup, "기본 정보")
    if t:
        for tr in t.find_all("tr")[1:]:
            c = [text(x) for x in tr.find_all("td")]
            if len(c) >= 4:
                d["endpoints"].append({"method": c[0], "url": c[1], "encoding": c[2], "format": c[3]})
    t = table_by_caption(soup, "요청 인자")
    if t:
        for tr in t.find_all("tr")[1:]:
            c = [text(x) for x in tr.find_all("td")]
            if len(c) >= 5:
                d["request"].append({"key": c[0], "name": c[1], "type": c[2], "required": c[3], "desc": c[4]})
    t = table_by_caption(soup, "응답 결과")
    if t:
        for tr in t.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            sp = tds[0].find("span", class_=re.compile(r"mgl\d+"))
            lvl = 0
            if sp:
                m = re.search(r"mgl(\d+)", " ".join(sp.get("class")))
                lvl = {5: 0, 20: 1, 40: 2, 60: 3, 80: 4}.get(int(m.group(1)), 0) if m else 0
            is_group = bool(tds[0].find("i", class_="iconArrow"))
            d["response"].append({"key": text(tds[0]), "name": text(tds[1]), "desc": text(tds[2]),
                                  "level": lvl, "group": is_group})
    form = table_by_caption(soup, "OpenAPI 테스트")
    if form:
        for inp in soup.find_all("input"):
            if inp.get("title") and inp.get("name"):
                d["example"][inp["name"]] = inp.get("value", "")
        for sel in soup.find_all("select"):
            if sel.get("name") and sel.get("title"):
                opt = sel.find("option", selected=True) or sel.find("option")
                d["example"][sel["name"]] = opt.get("value", "") if opt else ""
    api_url = soup.find("input", id="apiUrl")
    d["api_url"] = api_url.get("value", "") if api_url else ""
    d["extra_tables"] = {}  # 일부 API 에만 있는 부가 표 (예: 공시 상세 유형 코드표)
    for t in soup.find_all("table"):
        cap = t.find("caption")
        cap = cap.get_text(strip=True) if cap else ""
        if cap and cap not in STANDARD_TABLES:
            d["extra_tables"][cap] = expand_table(t)
    t = table_by_caption(soup, "메시지 설명")
    d["messages"] = []
    if t:
        for tr in t.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                d["messages"].append({"code": text(th).strip("-: ").strip(), "desc": text(td)})
    return d


# ---------------------------------------------------------------- 출력
def slug(s: str) -> str:
    return re.sub(r"[\s/·()（）,]+", "_", s).strip("_")


def example_url(api: dict) -> str:
    ex = {k: v for k, v in api["example"].items() if v != ""}  # 비워 둔 선택 인자는 뺀다
    if "crtfc_key" in ex:
        ex["crtfc_key"] = "{API_KEY}"
    ep = next((e for e in api["endpoints"] if e["format"].upper() == "JSON"), api["endpoints"][0] if api["endpoints"] else None)
    url = ep["url"] if ep else api.get("api_url", "")
    q = urlencode(ex, safe="{}")
    return f"{url}?{q}" if q else url


def api_md(api: dict) -> list[str]:
    L = [f'<a id="{api["api_id"]}"></a>', f"### {api['name']}", "",
         f"- **설명**: {api['desc']}",
         f"- **apiId**: `{api['api_id']}` · [원문 개발가이드]({api['guide_url']})"]
    if api["endpoints"]:
        L += ["", "| Method | 요청 URL | 인코딩 | 출력 포맷 |", "|---|---|---|---|"]
        L += [f"| {e['method']} | `{e['url']}` | {e['encoding']} | {e['format']} |" for e in api["endpoints"]]
    if api["request"]:
        L += ["", "**요청 인자**", "", "| 요청키 | 명칭 | 타입 | 필수 | 값 설명 |", "|---|---|---|:-:|---|"]
        L += [f"| `{r['key']}` | {cell_md(r['name'])} | {r['type']} | {r['required']} | {cell_md(r['desc'])} |"
              for r in api["request"]]
    for cap, rows in api.get("extra_tables", {}).items():
        rows = [r for r in rows if any(r)]
        if not rows:
            continue
        w = max(len(r) for r in rows)
        rows = [r + [""] * (w - len(r)) for r in rows]
        L += ["", f"**{cap}**", "", "| " + " | ".join(cell_md(c) for c in rows[0]) + " |", "|" + "---|" * w]
        L += ["| " + " | ".join(cell_md(c) for c in r) + " |" for r in rows[1:]]
    if api["example"]:
        L += ["", "**요청 예시** (개발가이드 테스트 화면의 기본값, 인증키는 본인 키로 교체)", "", "```",
              example_url(api), "```"]
    if api["response"]:
        n = sum(1 for r in api["response"] if not r["group"])
        L += ["", f"<details><summary>응답 결과 ({n}개 필드)</summary>", "",
              "| 응답키 | 명칭 | 출력 설명 |", "|---|---|---|"]
        for r in api["response"]:
            ind = "&nbsp;&nbsp;" * 2 * r["level"]
            key = f"{ind}**{r['key']}**" if r["group"] else f"{ind}`{r['key']}`"
            L.append(f"| {key} | {cell_md(r['name'])} | {cell_md(r['desc'])} |")
        L += ["", "</details>"]
    L += ["", "---", ""]
    return L


def write_docs(apis: list[dict], messages: list[dict]):
    today = date.today().isoformat()
    by_grp = {}
    for a in apis:
        by_grp.setdefault(a["group_code"], []).append(a)
    toc = []
    for i, (grp, name) in enumerate(GROUPS.items(), 1):
        items = by_grp.get(grp, [])
        fn = f"{i:02d}_{slug(name)}.md"
        for a in items:
            a["doc"] = fn
        L = [f"# {name} ({len(items)}개)", "",
             f"> 출처: OpenDART 개발가이드 [{name}]({BASE}/guide/main.do?apiGrpCd={grp}) 자동 수집 ({today}). "
             "인증키·공통 응답·메시지 코드·호출 한도는 [공통 가이드](00_공통_가이드.md) 참고.", "",
             "## 목록", "", "| # | API | 설명 | 요청 URL (JSON) |", "|---|---|---|---|"]
        for a in items:
            ep = next((e["url"] for e in a["endpoints"] if e["format"].upper() == "JSON"),
                      a["endpoints"][0]["url"] if a["endpoints"] else "")
            L.append(f"| {a['no']} | [{a['name']}](#{a['api_id']}) | {cell_md(a['desc'])} | `{ep.replace(BASE, '')}` |")
        L += ["", "## 상세", ""]
        for a in items:
            L += api_md(a)
        (DOCS / fn).write_text("\n".join(L), encoding="utf-8")
        toc.append((fn, name, len(items)))

    with open(DOCS / "INDEX.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["분류", "번호", "API명", "설명", "method", "url_json", "url_xml", "필수인자", "apiId", "문서", "원문"])
        for a in apis:
            j = next((e["url"] for e in a["endpoints"] if e["format"].upper() == "JSON"), "")
            x = next((e["url"] for e in a["endpoints"] if e["format"].upper() == "XML"), "")
            other = "" if (j or x) else (a["endpoints"][0]["url"] if a["endpoints"] else "")
            req = " ".join(r["key"] for r in a["request"] if r["required"].upper() == "Y")
            w.writerow([a["group"], a["no"], a["name"], a["desc"], a["endpoints"][0]["method"] if a["endpoints"] else "",
                        j or other, x, req, a["api_id"], a["doc"], a["guide_url"]])
    (DOCS / "apis.json").write_text(json.dumps({"source": BASE + "/guide", "collected": today, "messages": messages,
                                                "apis": apis}, ensure_ascii=False, indent=1), encoding="utf-8")
    write_readme(apis, today)
    return toc


def write_readme(apis: list[dict], today: str):
    L = ["# OpenDART API 문서 (금융감독원 전자공시)", "",
         f"금융감독원 OpenDART 오픈API **전체 {len(apis)}개**를 분류별로 정리한 문서.", "",
         f"- **출처**: [OpenDART 개발가이드]({BASE}/guide/main.do?apiGrpCd=DS001) 6개 분류의 목록 페이지와 각 API 상세 "
         "페이지를 자동 수집 (기본 정보, 요청 인자, 응답 결과, 테스트 예시값, 메시지 코드, 부가 코드표)",
         f"- **수집 기준일**: {today}",
         "- **다시 만들기**: `python OpenDART_API_docs/_tools/scrape_dart.py --refresh` (받은 HTML은 `_tools/cache/`에 "
         "저장, `--refresh` 없이 실행하면 캐시로 문서만 다시 생성). `00_공통_가이드.md`는 직접 작성한 문서라 다시 만들지 않는다", "",
         "## 먼저 읽을 것", "",
         "👉 **[00_공통_가이드.md](00_공통_가이드.md)** — 인증키, 요청 형식, 공통 응답(status/message), 메시지 코드, "
         "호출 제한, 고유번호(corp_code) 얻기, 보고서 코드, 파이썬 예제", "",
         "## 찾는 방법", "",
         "- **API 이름이나 URL로 찾기**: [INDEX.csv](INDEX.csv) (엑셀로 열기 가능) 또는 "
         "`grep -r \"fnlttSinglAcntAll\" OpenDART_API_docs/`",
         "- **코드에서 쓰기**: [apis.json](apis.json) — 전체 명세를 기계가 읽기 좋은 JSON으로 저장",
         "- **각 문서 구성**: 분류별 목록 표 → API마다 설명, 원문 링크, Method/URL(JSON·XML), 요청 인자 표, 요청 예시 URL, "
         "응답 결과(접힘, 계층 표시)", "",
         "## 목차", ""]
    groups = {}
    for a in apis:
        groups.setdefault((a["doc"], a["group"]), []).append(a)
    for (doc, g), items in groups.items():
        L += [f"### [{g}]({doc}) — {len(items)}개", "",
              ", ".join(f"[{a['name']}]({doc}#{a['api_id']})" for a in items), ""]
    (DOCS / "README.md").write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    apis = []
    for grp in GROUPS:
        lst = parse_list(fetch(f"/guide/main.do?apiGrpCd={grp}", args.refresh), grp)
        print(f"{grp} {GROUPS[grp]}: {len(lst)}개", flush=True)
        for a in lst:
            a.update(parse_detail(fetch(f"/guide/detail.do?apiGrpCd={grp}&apiId={a['api_id']}", args.refresh)))
            apis.append(a)
    messages = next((a["messages"] for a in apis if a["messages"]), [])
    toc = write_docs(apis, messages)
    for a in apis:
        if not a["endpoints"] or not a["request"] or not a["response"]:
            print(f"  확인 필요: {a['group']} / {a['name']} (기본정보 {len(a['endpoints'])}, 요청 {len(a['request'])}, 응답 {len(a['response'])})")
    print(f"총 {len(apis)}개 API → {[t[0] for t in toc]}")


if __name__ == "__main__":
    main()
