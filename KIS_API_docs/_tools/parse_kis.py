"""Parse koreainvestment/open-trading-api examples_llm into structured JSON."""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) / "examples_llm"
OUT = Path(sys.argv[2])

HDR_RE = re.compile(r"^#\s*\[([^\]]+)\]\s*(.*)$")
ARG_RE = re.compile(r"^\s*(\w+)\s*\(([^)]*)\)\s*:\s*(.*)$")
TR_RE = re.compile(r"^[A-Z0-9]{6,12}$")


def parse_header(src):
    for line in src.splitlines():
        m = HDR_RE.match(line.strip())
        if m and "#####" not in line:
            product, rest = m.group(1).strip(), m.group(2).strip()
            parts = re.split(r"\s+[>\-]\s+", rest, maxsplit=1)
            if len(parts) == 2:
                sub, name = parts
            else:
                sub, name = "", rest
            return product, sub.strip(), name.strip()
    return None, "", ""


def parse_doc_args(doc):
    args = {}
    if not doc:
        return args
    in_args = False
    for line in doc.splitlines():
        s = line.strip()
        if s.startswith("Args:"):
            in_args = True
            continue
        if in_args and re.match(r"^(Returns|Raises|Example|Examples|Note)s?:", s):
            break
        if in_args:
            m = ARG_RE.match(s)
            if m:
                args[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    return args


INTERNAL_ARGS = {"tr_cont", "dataframe", "depth", "max_depth", "dataframe1", "dataframe2",
                 "dataframe3", "FK100", "NK100", "FK200", "NK200", "FK50", "NK50"}


def cond_text(node, parents):
    conds = []
    p = parents.get(node)
    child = node
    while p is not None:
        if isinstance(p, ast.If):
            t = ast.unparse(p.test)
            if child in p.body:
                conds.append(t)
            else:
                conds.append(f"not ({t})")
        child, p = p, parents.get(p)
    return " and ".join(reversed(conds))


def analyze(main_py, chk_py):
    src = main_py.read_text(encoding="utf-8")
    tree = ast.parse(src)
    parents = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n

    product, sub, name = parse_header(src)
    api_url = None
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "API_URL" for t in n.targets):
            if isinstance(n.value, ast.Constant):
                api_url = n.value.value

    func = None
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == main_py.stem:
            func = n
    if func is None:
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        func = funcs[0] if funcs else None

    doc = ast.get_docstring(func) if func else ""
    doc_args = parse_doc_args(doc)

    # signature
    sig = []
    if func:
        a = func.args
        defaults = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
        for arg, d in zip(a.args, defaults):
            if arg.arg in INTERNAL_ARGS:
                continue
            typ, desc = doc_args.get(arg.arg, ("", ""))
            comment = ""
            line = src.splitlines()[arg.lineno - 1]
            if "#" in line:
                comment = line.split("#", 1)[1].strip()
            required = d is None or "[필수]" in desc
            sig.append({
                "name": arg.arg,
                "default": None if d is None else ast.unparse(d),
                "required": required,
                "desc": (desc.replace("[필수]", "").strip() or comment),
            })

    # tr_ids with conditions
    tr_ids = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "tr_id" for t in n.targets):
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                tr_ids.append({"tr_id": n.value.value, "when": cond_text(n, parents)})
    # dedupe
    seen, uniq = set(), []
    for t in tr_ids:
        k = (t["tr_id"], t["when"])
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    tr_ids = uniq

    # params dict (API field -> python arg)
    params = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("params", "body") for t in n.targets):
            if isinstance(n.value, ast.Dict):
                lines = src.splitlines()
                for k, v in zip(n.value.keys, n.value.values):
                    if isinstance(k, ast.Constant):
                        comment = ""
                        ln = lines[k.lineno - 1]
                        if "#" in ln:
                            comment = ln.split("#", 1)[1].strip()
                        params.append({
                            "field": k.value,
                            "arg": ast.unparse(v),
                            "comment": comment,
                        })
                break

    # method
    method = "GET"
    is_ws = "data_fetch(" in src and "_url_fetch(" not in src
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("_url_fetch"):
            for kw in n.keywords:
                if kw.arg == "postFlag" and isinstance(kw.value, ast.Constant) and kw.value.value:
                    method = "POST"
    if is_ws:
        method = "WEBSOCKET"

    # websocket columns
    ws_columns = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "columns" for t in n.targets):
            if isinstance(n.value, ast.List):
                ws_columns = [e.value for e in n.value.elts if isinstance(e, ast.Constant)]

    # output columns from chk file
    col_map = {}
    if chk_py and chk_py.exists():
        ctree = ast.parse(chk_py.read_text(encoding="utf-8"))
        for n in ast.walk(ctree):
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "COLUMN_MAPPING" for t in n.targets):
                if isinstance(n.value, ast.Dict):
                    for k, v in zip(n.value.keys, n.value.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            col_map[k.value] = v.value

    # docstring summary / example
    example = ""
    if doc:
        lines = doc.splitlines()
        for i, ln in enumerate(lines):
            if ln.strip().startswith(">>>"):
                buf = ln.strip()[3:].strip()
                j = i + 1
                while buf.count("(") > buf.count(")") and j < len(lines):
                    buf += " " + lines[j].strip().lstrip(".").strip()
                    j += 1
                example = re.sub(r"\s+", " ", buf).replace("( ", "(").replace(" )", ")").replace(", )", ")")
                break
    if not name and doc:
        name = doc.strip().splitlines()[0]

    return {
        "folder": main_py.parent.name,
        "product": product,
        "sub": sub,
        "name": name,
        "url": api_url,
        "method": method,
        "tr_ids": tr_ids,
        "args": sig,
        "params": params,
        "outputs": col_map,
        "ws_columns": ws_columns,
        "example": example,
        "source": str(main_py.relative_to(ROOT.parent)).replace("\\", "/"),
    }


def main():
    result = []
    for cat_dir in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        for api_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
            main_py = api_dir / f"{api_dir.name}.py"
            if not main_py.exists():
                cands = [p for p in api_dir.glob("*.py") if not p.name.startswith("chk_")]
                if not cands:
                    continue
                main_py = cands[0]
            chk = api_dir / f"chk_{main_py.stem}.py"
            try:
                info = analyze(main_py, chk)
            except Exception as e:  # noqa: BLE001
                print("FAIL", main_py, e, file=sys.stderr)
                continue
            info["category_dir"] = cat_dir.name
            result.append(info)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(result), "apis")


if __name__ == "__main__":
    main()
