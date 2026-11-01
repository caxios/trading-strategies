"""6단계 — 논문(영어) 표와 그림을 결과 파일에서 직접 생성한다 (숫자를 손으로 옮기지 않기 위해).

입력: data/paper/ (paper_variables.py, paper_main_tests.py, paper_robustness.py 출력)
출력: strategy1/paper/manuscript/tables/*.tex, strategy1/paper/manuscript/figures/*.pdf
"""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from paper_main_tests import CTRL, LAST_SIGNAL, winsorize_by_day  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "paper"
MS = Path(__file__).resolve().parent / "paper" / "manuscript"
TAB, FIG = MS / "tables", MS / "figures"
CSV = dict(encoding="utf-8-sig")
INV_EN = {"외국인": "Foreign", "기관": "Institutional", "개인": "Individual"}
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1f1f1e", "#898781", "#e1e0d9"


def pp(x, d=2):  # 확률 → 퍼센트포인트 문자열
    return f"{x * 100:.{d}f}"


def tt(x):
    return f"({x:.2f})"


def write(name, body):
    (TAB / f"{name}.tex").write_text(body, encoding="utf-8")


# ---------------------------------------------------------------- Table 1: 기술통계
def table_summary():
    cols = ["일자", "e_20", "path_min_20", "ncskew20", "duvol20", *CTRL, "x1_F", "x1_I", "x1_R"]
    p = pd.read_parquet(DATA / "panel.parquet", columns=cols)
    p = p[p["일자"] <= LAST_SIGNAL].copy()
    p = winsorize_by_day(p, CTRL)
    p["Y20"] = (p["e_20"] <= -0.2).astype(float).where(p["e_20"].notna())
    p["Ypath"] = (p["path_min_20"] <= -0.2).astype(float).where(p["path_min_20"].notna())
    for c in ["x1_F", "x1_I", "x1_R"]:
        p[c] = p[c] * 1e4  # basis points of market cap
    rows = [
        ("Tail event $Y$ ($e^{20}\\le-20\\%$)", "Y20"), ("Path minimum $\\le-20\\%$", "Ypath"),
        ("20-day excess return $e^{20}$", "e_20"), ("NCSKEW (20 days)", "ncskew20"), ("DUVOL (20 days)", "duvol20"),
        ("Foreign net buying $x^F$ (bp of cap)", "x1_F"), ("Institutional net buying $x^I$ (bp)", "x1_I"),
        ("Individual net buying $x^R$ (bp)", "x1_R"),
        ("Log market cap", "size"), ("Log book-to-market", "bm"), ("Momentum (12--1)", "mom"),
        ("Short-term reversal (20 days)", "str"), ("Signal-day return", "r_d"), ("Entry-day return", "r_d1"),
        ("Volatility (20 days)", "vol20"), ("Beta (250 days)", "beta"), ("Amihud illiquidity", "amihud"),
        ("Turnover (20 days)", "turnover"), ("Past NCSKEW (60 days)", "skew60_past"),
    ]
    lines = []
    for lab, c in rows:
        v = p[c].dropna()
        q = v.quantile([0.25, 0.5, 0.75])
        lines.append(f"{lab} & {len(v):,} & {v.mean():.4f} & {v.std():.4f} & {q[0.25]:.4f} & {q[0.5]:.4f} & {q[0.75]:.4f} \\\\")
    n_days, n = p["일자"].nunique(), len(p)
    write("t1_summary", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Summary statistics}\\label{tab:summary}",
        "\\footnotesize",
        "\\begin{tabular}{lrrrrrr}\\toprule",
        "Variable & Obs. & Mean & Std. dev. & P25 & Median & P75 \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.95\\textwidth}\\vspace{0.5em}\\scriptsize",
        f"\\textit{{Notes:}} The sample covers {n_days} signal days (22 October 2024 to 17 September 2026) and {n:,} "
        "stock-days. Returns are measured from the close of day $d+1$. Control variables are winsorized at the 1st and "
        "99th percentiles each day. Net buying is the investor group's net purchase value on day $d$ divided by the "
        "stock's market capitalization, in basis points. Variable definitions are in Appendix~\\ref{app:vars}.",
        "\\end{minipage}\\end{table}"]))


# ---------------------------------------------------------------- Table 2: 꼬리 위험 본 결과
def table_tail():
    t = pd.read_csv(DATA / "tests_tail.csv", **CSV)
    y = t[t["결과변수"].str.startswith("Y")]
    get = lambda m, inv, term: y[(y["모형"] == m) & (y["투자자"] == inv) & (y["항"] == term)].iloc[0]  # noqa: E731
    lines = []
    for key, inv in [("F", "외국인"), ("I", "기관"), ("R", "개인")]:
        s, b, d = get("단독", inv, f"S_{key}"), get("단독", inv, f"B_{key}"), get("단독", inv, f"S_{key} − B_{key}")
        js, jb = get("결합", "세 주체", f"S_{key}"), get("결합", "세 주체", f"B_{key}")
        lines.append(f"{INV_EN[inv]} & {pp(s['평균'])} & {pp(b['평균'])} & {pp(d['평균'])} & {pp(s['기준확률'])} "
                     f"& {pp(js['평균'])} & {pp(jb['평균'])} \\\\")
        lines.append(f" & {tt(s['t'])} & {tt(b['t'])} & {tt(d['t'])} & & {tt(js['t'])} & {tt(jb['t'])} \\\\[2pt]")
    write("t2_tail", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Extreme investor flows and the probability of a large 20-day underperformance}\\label{tab:tail}",
        "\\small",
        "\\begin{tabular}{lccccccc}\\toprule",
        " & \\multicolumn{4}{c}{Separate regressions} & \\multicolumn{2}{c}{Joint regression} \\\\",
        "\\cmidrule(lr){2-5}\\cmidrule(lr){6-7}",
        "Investor group & $\\beta_S$ & $\\beta_B$ & $\\beta_S-\\beta_B$ & Base rate & $\\beta_S$ & $\\beta_B$ \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.95\\textwidth}\\vspace{0.5em}\\scriptsize",
        "\\textit{Notes:} Each day $d$ we estimate the cross-sectional linear probability model "
        "$Y_{i,d}=a_d+\\beta_S S^j_{i,d}+\\beta_B B^j_{i,d}+\\delta\\,\\mathrm{KOSPI}_i+\\gamma'Z_{i,d}+\\varepsilon_{i,d}$, "
        "where $Y_{i,d}=1$ if the stock's market-adjusted return over the 20 trading days after the close of $d+1$ is "
        "$-20\\%$ or worse, $S^j$ ($B^j$) flags the bottom (top) decile of investor group $j$'s net buying scaled by "
        "market capitalization on day $d$ within the stock's market, and $Z$ contains the eleven controls of "
        "Table~\\ref{tab:summary}. Coefficients are time-series averages of the daily estimates, in percentage points. "
        "Newey--West $t$-statistics with 19 lags are in parentheses ($T=466$ days). The base rate is the average daily "
        "frequency of $Y=1$ among stocks with neither signal. The joint regression includes all six signals.",
        "\\end{minipage}\\end{table}"]))


# ---------------------------------------------------------------- Table 3: 가설 판정
HYP_EN = {
    "H1": "Foreign extreme selling raises tail risk ($\\beta^F_S>0$)",
    "H2": "Foreign selling riskier than buying ($\\beta^F_S-\\beta^F_B>0$)",
    "H4": "Individual buying riskier than selling ($\\beta^R_B-\\beta^R_S>0$)",
    "H3": "Institutional equivalence ($|\\beta^I_S-\\beta^I_B|<0.5$pp, TOST)",
    "H6": "Foreign extreme selling, joint model ($\\beta^F_S>0$)",
}


def table_hyp():
    h = pd.read_csv(DATA / "hypotheses.csv", **CSV)
    lines = []
    for hid in ["H1", "H2", "H4", "H3"]:
        r = h[h["가설"] == hid].iloc[0]
        if hid == "H3":
            res = "Not established"
            rule, p = "TOST, 5\\%", f"{r['p(단측)']:.3f}"
        else:
            res = "Supported" if "지지" in r["결과"] else "Not supported"
            rule, p = f"Holm, {r['판정기준'].split()[-1]}", "$<$0.0001" if r["p(단측)"] < 1e-4 else f"{r['p(단측)']:.4f}"
        lines.append(f"{hid} & {HYP_EN[hid]} & {pp(r['추정치'])} & {r['t']:.2f} & {p} & {rule} & {res} \\\\")
    lines.append("\\midrule")
    sec = h[h["가설"].isin(["H5", "H6"])]
    names = ["Foreign selling", "Foreign buying", "Institutional selling", "Institutional buying",
             "Individual selling", "Individual buying"]
    for (i, r), nm in zip(sec[sec["가설"] == "H5"].iterrows(), names):
        p = "$<$0.0001" if r["p(단측)"] < 1e-4 else f"{r['p(단측)']:.4f}"
        res = "Significant" if r["p(단측)"] <= 0.05 / 12 else "Not significant"
        lines.append(f"H5 & {nm} coefficient $>0$ & {pp(r['추정치'])} & {r['t']:.2f} & {p} & Bonferroni, 0.0042 & {res} \\\\")
    r = sec[sec["가설"] == "H6"].iloc[0]
    lines.append(f"H6 & {HYP_EN['H6']} & {pp(r['추정치'])} & {r['t']:.2f} & {r['p(단측)']:.4f} & Bonferroni, 0.0042 & "
                 f"{'Significant' if r['p(단측)'] <= 0.05 / 12 else 'Not significant'} \\\\")
    write("t3_hyp", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Pre-specified hypothesis tests: tail risk}\\label{tab:hyp}",
        "\\scriptsize\\setlength{\\tabcolsep}{3pt}",
        "\\begin{tabular}{llrrlll}\\toprule",
        " & Hypothesis & Estimate (pp) & $t$ & $p$ & Decision rule & Result \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.95\\textwidth}\\vspace{0.5em}\\scriptsize",
        "\\textit{Notes:} Estimates and Newey--West $t$-statistics come from Table~\\ref{tab:tail}. $p$-values are one-sided "
        "under the normal approximation. The primary family (H1, H2, H4) is controlled at 5\\% with Holm's step-down "
        "procedure; the threshold shown is the one applied to each hypothesis. H3 is a two one-sided tests (TOST) "
        "equivalence test with margin $\\pm0.5$ percentage points; the ordinary two-sided $p$-value for "
        "$\\beta^I_S-\\beta^I_B=0$ is 0.049. Secondary hypotheses use a Bonferroni threshold of $0.05/12$.",
        "\\end{minipage}\\end{table}"]))


# ---------------------------------------------------------------- Table 4: 평균 수익률
def table_returns():
    r = pd.read_csv(DATA / "tests_returns.csv", **CSV)
    lines = []
    for inv in ["외국인", "기관", "개인"]:
        s = r[r["투자자"] == inv].set_index("보유기간")
        lines.append(f"{INV_EN[inv]} & " + " & ".join(f"{s.loc[h, '평균'] * 100:.3f}" for h in [1, 5, 20]) + " \\\\")
        lines.append(" & " + " & ".join(tt(s.loc[h, "t"]) for h in [1, 5, 20]) + " \\\\[2pt]")
    f = pd.read_csv(DATA / "tests_factor.csv", **CSV)
    flines = []
    for inv in ["외국인", "기관", "개인"]:
        for reb, lab in [("매일", "Daily"), ("5일", "5-day")]:
            g = f[(f["투자자"] == inv) & (f["리밸런싱"] == reb)].set_index("구분")
            a, n = g.loc["비용 전"], g.loc["비용 후"]
            be = a["손익분기_편도비용"]
            flines.append(f"{INV_EN[inv]} & {lab} & {a['평균'] * 100:.3f} {tt(a['평균_t'])} & {a['alpha'] * 100:.3f} {tt(a['alpha_t'])} "
                          f"& {n['alpha'] * 100:.3f} {tt(n['alpha_t'])} & {a['일평균매매비율']:.2f} & "
                          f"{be * 100:.3f} \\\\" if be > 0 else
                          f"{INV_EN[inv]} & {lab} & {a['평균'] * 100:.3f} {tt(a['평균_t'])} & {a['alpha'] * 100:.3f} {tt(a['alpha_t'])} "
                          f"& {n['alpha'] * 100:.3f} {tt(n['alpha_t'])} & {a['일평균매매비율']:.2f} & -- \\\\")
    write("t4_returns", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Investor flows and average returns}\\label{tab:returns}",
        "\\small",
        "\\textit{Panel A: Fama--MacBeth regressions of market-adjusted returns on the net-buying rank}\\\\[3pt]",
        "\\begin{tabular}{lccc}\\toprule",
        "Investor group & $h=1$ & $h=5$ & $h=20$ \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}\\\\[8pt]",
        "\\textit{Panel B: Size-neutral flow factors (daily returns, \\%)}\\\\[3pt]",
        "\\footnotesize\\setlength{\\tabcolsep}{4pt}",
        "\\begin{tabular}{llccccc}\\toprule",
        "Investor group & Rebalancing & Mean & $\\alpha$ before costs & $\\alpha$ after costs & Turnover & Break-even cost \\\\\\midrule",
        *flines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.95\\textwidth}\\vspace{0.5em}\\scriptsize",
        "\\textit{Notes:} Panel A reports time-series averages (in \\%) of daily cross-sectional slopes from "
        "$e^h_{i,d}=a_d+b_d q^j_{i,d}+\\delta\\,\\mathrm{KOSPI}_i+c'Z_{i,d}+u_{i,d}$, where $q^j$ is the within-market "
        "percentile rank of net buying minus 0.5, so $b$ is the return difference between the most-bought and the "
        "most-sold stock. Newey--West $t$-statistics with $\\max(h-1,5)$ lags are in parentheses. Panel B reports "
        "$\\mathrm{FLOW}^j=\\tfrac12(R_{SH}+R_{BH})-\\tfrac12(R_{SL}+R_{BL})$ from a $2\\times3$ sort on size and net "
        "buying (30/70 breakpoints), formed with day-$d$ flows at the close of $d+1$, value weighted. $\\alpha$ is the "
        "intercept from regressing FLOW on MKT, SMB, HML, MOM and STR (Newey--West, 5 lags). Turnover is traded value "
        "per unit of long and short capital per day; after-cost returns deduct turnover times a one-way cost of "
        "0.125\\%. Break-even cost is the one-way cost that sets the before-cost $\\alpha$ to zero.",
        "\\end{minipage}\\end{table}"]))


# ---------------------------------------------------------------- Table 5: 강건성
ROB_EN = {
    "주 분석": "Baseline",
    "R1 d+1 시가 진입": "R1: Entry at the open of $d+1$",
    "R1 (참고) d 종가 진입": "R1: Entry at the close of $d$ (infeasible, reference)",
    "R2 누적 5일 신호": "R2: Signal from 5-day cumulative flow",
    "R2 누적 20일 신호": "R2: Signal from 20-day cumulative flow",
    "R3 대량거래 신호": "R3: Heavy-trading signal",
    "R3 하위·상위 5%": "R3: Extreme 5\\%",
    "R3 하위·상위 20%": "R3: Extreme 20\\%",
    "R4 초과수익률 −10%": "R4: Threshold $-10\\%$",
    "R4 보유 중 최저 −20%": "R4: Path minimum $\\le -20\\%$",
    "R5 보유 10일": "R5: 10-day horizon",
    "R5 보유 60일": "R5: 60-day horizon$^\\dagger$",
    "R6 KOSPI만": "R6: KOSPI only",
    "R6 KOSDAQ만": "R6: KOSDAQ only",
    "R7 크기 상위 1/3": "R7: Largest size tercile",
    "R7 시가총액 1,000억 이상": "R7: Market cap $\\ge$ KRW 100bn",
    "R8 앞 1년": "R8: First year",
    "R8 뒤 1년": "R8: Second year",
    "R9 시장 직전 20일 상승": "R9: Market up over prior 20 days",
    "R9 시장 직전 20일 하락": "R9: Market down over prior 20 days",
    "R10 통합 LPM (날짜 FE, 양방향 군집)": "R10: Pooled LPM, day FE, two-way clustered",
    "R10 로짓 평균 한계효과 (날짜 FE, 양방향 군집)": "R10: Logit AME, day FE, two-way clustered$^\\ddagger$",
    "R11 결측 중앙값 대체": "R11: Missing controls imputed",
    "R12 B/M 60일 전 값": "R12: Book-to-market lagged 60 days",
}


def table_robust():
    r = pd.read_csv(DATA / "tests_robustness.csv", **CSV)
    order = list(dict.fromkeys(r["설정"]))
    order = [order[0]] + [o for o in ROB_EN if o in order and o != order[0]]
    get = lambda s, inv, term: r[(r["설정"] == s) & (r["투자자"] == inv) & (r["항"] == term)].iloc[0]  # noqa: E731
    lines = []
    for s in order:
        cells = []
        for inv, term in [("외국인", "β_S"), ("외국인", "β_S − β_B"), ("개인", "β_S − β_B"), ("기관", "β_S − β_B")]:
            x = get(s, inv, term)
            cells.append(f"{pp(x['평균'])} {tt(x['t'])}")
        lines.append(f"{ROB_EN[s]} & " + " & ".join(cells) + " \\\\")
        if s == "주 분석":
            lines.append("\\midrule")
    write("t5_robust", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Robustness of the tail-risk results}\\label{tab:robust}",
        "\\scriptsize",
        "\\begin{tabular}{lcccc}\\toprule",
        " & Foreign & Foreign & Individual & Institutional \\\\",
        "Specification & $\\beta_S$ (H1) & $\\beta_S-\\beta_B$ (H2) & $\\beta_S-\\beta_B$ (H4) & $\\beta_S-\\beta_B$ (H3) \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.95\\textwidth}\\vspace{0.5em}\\scriptsize",
        "\\textit{Notes:} Each row changes one element of the baseline specification of Table~\\ref{tab:tail} "
        "(all rows were pre-specified). Entries are coefficients in percentage points with $t$-statistics in "
        "parentheses. H1 and H2 predict positive values, H4 predicts a negative value (individual buying riskier), "
        "and H3 predicts a value near zero. Fama--MacBeth rows use Newey--West standard errors with "
        "$\\max(h-1,5)$ lags. $^\\dagger$Only seven non-overlapping 60-day windows; treated as underpowered. "
        "$^\\ddagger$Standard errors of average marginal effects are approximated by scaling coefficient standard "
        "errors with the mean logistic density and may be too small.",
        "\\end{minipage}\\end{table}"]))


# ---------------------------------------------------------------- Table 6: 준 표본 밖
def table_split():
    r = pd.read_csv(DATA / "tests_robustness.csv", **CSV)
    get = lambda s, inv, term: r[(r["설정"] == s) & (r["투자자"] == inv) & (r["항"] == term)].iloc[0]  # noqa: E731
    lines = []
    for lab, inv, term, sign in [("H1: Foreign $\\beta_S$", "외국인", "β_S", 1),
                                 ("H2: Foreign $\\beta_S-\\beta_B$", "외국인", "β_S − β_B", 1),
                                 ("H4: Individual $\\beta_B-\\beta_S$", "개인", "β_S − β_B", -1),
                                 ("H3: Institutional $\\beta_S-\\beta_B$", "기관", "β_S − β_B", 1)]:
        a, b = get("R8 앞 1년", inv, term), get("R8 뒤 1년", inv, term)
        z = (a["평균"] - b["평균"]) / np.sqrt(a["se"] ** 2 + b["se"] ** 2)
        from paper_main_tests import norm_sf
        lines.append(f"{lab} & {pp(sign * a['평균'])} {tt(sign * a['t'])} & {pp(sign * b['평균'])} {tt(sign * b['t'])} "
                     f"& {sign * z:.2f} & {2 * norm_sf(abs(z)):.3f} \\\\")
    s = pd.read_csv(DATA / "tests_stocksplit.csv", **CSV)
    slines = []
    for hid, lab in [("H1", "H1: Foreign $\\beta_S$"), ("H2", "H2: Foreign $\\beta_S-\\beta_B$"),
                     ("H4", "H4: Individual $\\beta_B-\\beta_S$")]:
        g = s[s["가설"] == hid]
        tv = pd.concat([g["그룹A_t"], g["그룹B_t"]])
        same = ((g["그룹A_추정"] > 0) & (g["그룹B_추정"] > 0)).mean() * 100
        sig = ((g["그룹A_t"] > 1.645) & (g["그룹B_t"] > 1.645)).mean() * 100
        slines.append(f"{lab} & {same:.1f} & {sig:.1f} & {tv.min():.2f} & {tv.median():.2f} & {tv.max():.2f} \\\\")
    write("t6_split", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Within-sample replication: time and cross-sectional splits}\\label{tab:split}",
        "\\small",
        "\\textit{Panel A: First year versus second year}\\\\[3pt]",
        "\\begin{tabular}{lcccc}\\toprule",
        " & First year & Second year & $z$ (difference) & $p$ (two-sided) \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}\\\\[8pt]",
        "\\textit{Panel B: Random halves of stocks, 200 splits}\\\\[3pt]",
        "\\begin{tabular}{lccccc}\\toprule",
        " & Same sign in & Significant in & \\multicolumn{3}{c}{$t$-statistics (400 halves)} \\\\",
        "\\cmidrule(lr){4-6}",
        " & both halves (\\%) & both halves (\\%) & Min & Median & Max \\\\\\midrule",
        *slines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.95\\textwidth}\\vspace{0.5em}\\scriptsize",
        "\\textit{Notes:} Panel A re-estimates the baseline model separately for signal days 22 October 2024 to "
        "22 October 2025 and 23 October 2025 to 17 September 2026 (coefficients in percentage points, signed so "
        "that positive values support the hypothesis; Newey--West $t$-statistics in parentheses). "
        "$z=(\\bar\\beta_1-\\bar\\beta_2)/\\sqrt{se_1^2+se_2^2}$ treats the two halves as independent. Panel B splits "
        "the cross-section of stocks into two random halves (seeds 0--199) and re-estimates the baseline model in each "
        "half; ``significant'' means a one-sided $p<0.05$. Both panels use data from which the hypotheses were "
        "derived and are therefore not true out-of-sample tests.",
        "\\end{minipage}\\end{table}"]))


# ---------------------------------------------------------------- 부록 표: 급락 지표, 팩터 점검
def table_crash():
    t = pd.read_csv(DATA / "tests_tail.csv", **CSV)
    t = t[(t["모형"] == "단독") & ~t["결과변수"].str.startswith("Y")]
    names = {"NCSKEW 20일": "NCSKEW, 20 days", "DUVOL 20일": "DUVOL, 20 days",
             "NCSKEW 60일": "NCSKEW, 60 days$^\\dagger$", "DUVOL 60일": "DUVOL, 60 days$^\\dagger$"}
    lines = []
    for y, lab in names.items():
        cells = []
        for key, inv in [("F", "외국인"), ("I", "기관"), ("R", "개인")]:
            for term in [f"S_{key}", f"B_{key}", f"S_{key} − B_{key}"]:
                x = t[(t["결과변수"] == y) & (t["투자자"] == inv) & (t["항"] == term)].iloc[0]
                cells.append(f"{x['평균']:.3f}")
        tl = []
        for key, inv in [("F", "외국인"), ("I", "기관"), ("R", "개인")]:
            for term in [f"S_{key}", f"B_{key}", f"S_{key} − B_{key}"]:
                x = t[(t["결과변수"] == y) & (t["투자자"] == inv) & (t["항"] == term)].iloc[0]
                tl.append(tt(x["t"]))
        lines.append(f"{lab} & " + " & ".join(cells) + " \\\\")
        lines.append(" & " + " & ".join(tl) + " \\\\[2pt]")
    write("ta_crash", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Investor flows and conditional skewness}\\label{tab:crash}",
        "\\scriptsize\\setlength{\\tabcolsep}{3pt}",
        "\\begin{tabular}{lccccccccc}\\toprule",
        " & \\multicolumn{3}{c}{Foreign} & \\multicolumn{3}{c}{Institutional} & \\multicolumn{3}{c}{Individual} \\\\",
        "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\\cmidrule(lr){8-10}",
        "Dependent variable & $\\beta_S$ & $\\beta_B$ & $\\beta_S-\\beta_B$ & $\\beta_S$ & $\\beta_B$ & $\\beta_S-\\beta_B$ & "
        "$\\beta_S$ & $\\beta_B$ & $\\beta_S-\\beta_B$ \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.95\\textwidth}\\vspace{0.5em}\\scriptsize",
        "\\textit{Notes:} Same daily cross-sectional regressions as Table~\\ref{tab:tail} with the dependent variable "
        "replaced by the negative coefficient of skewness (NCSKEW) or the down-to-up volatility ratio (DUVOL) of "
        "firm-specific log returns over the holding window. Firm-specific returns are $\\ln(1+r_{i,t}-\\hat\\beta_{i,d}r_{m,t})$ "
        "with $\\hat\\beta$ estimated before the signal day. Newey--West $t$-statistics in parentheses. "
        "$^\\dagger$426 signal days; seven non-overlapping windows.",
        "\\end{minipage}\\end{table}"]))


def table_factors():
    f = pd.read_csv(DATA / "factors.csv", encoding="utf-8-sig", dtype={"일자": str}).set_index("일자")
    f = f[f.index >= "20241024"]
    chk = pd.read_csv(DATA / "index_check.csv", encoding="utf-8-sig", dtype={"일자": str}).set_index("일자")
    chk = chk[chk.index >= "20241023"]
    lines = []
    for k in ["MKT", "SMB", "HML", "MOM", "STR"]:
        v = f[k].dropna()
        lines.append(f"{k} & {len(v)} & {v.mean() * 100:.3f} & {v.std() * np.sqrt(252) * 100:.1f} \\\\")
    c1 = chk["우리_KOSPI"].corr(chk["KOSPI"])
    c2 = chk["우리_KOSDAQ"].corr(chk["KOSDAQ"])
    c3 = chk["우리_SMB"].corr(chk["KRX_소형-대형"])
    write("tb_factors", "\n".join([
        "\\begin{table}[htbp]\\centering",
        "\\caption{Constructed Korean factors}\\label{tab:factors}",
        "\\small",
        "\\begin{tabular}{lccc}\\toprule",
        "Factor & Days & Mean daily return (\\%) & Annualized volatility (\\%) \\\\\\midrule",
        *lines,
        "\\bottomrule\\end{tabular}",
        "\\begin{minipage}{0.85\\textwidth}\\vspace{0.5em}\\scriptsize",
        "\\textit{Notes:} Factors are built from the study universe (both markets pooled). MKT is the value-weighted "
        "universe return minus the daily CD (91-day) rate; SMB and HML use a $2\\times3$ sort on size (median) and "
        "book-to-market (30/70), MOM a $2\\times3$ sort on 12--1 month returns, both reformed at month-ends; STR is a "
        "daily-reformed $2\\times3$ sort on the prior 20-day return (losers minus winners). Correlations of daily "
        f"returns with KRX indices: our KOSPI index {c1:.4f}, our KOSDAQ index {c2:.4f}; SMB with the average of "
        f"(KOSPI small $-$ large) and (KOSDAQ small $-$ large) size indices {c3:.2f}. The lower SMB correlation reflects "
        "pooled-median versus within-market rank breakpoints.",
        "\\end{minipage}\\end{table}"]))


# ---------------------------------------------------------------- 그림
def style(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def fig_rolling():
    dc = pd.read_parquet(DATA / "daily_coefs.parquet")
    F = dc[dc["모형"] == "Y20|F"].set_index("일자")
    R = dc[dc["모형"] == "Y20|R"].set_index("일자")
    h2 = ((F["S_F"] - F["B_F"]) * 100).rolling(60).mean()
    h4 = ((R["B_R"] - R["S_R"]) * 100).rolling(60).mean()
    h1 = (F["S_F"] * 100).rolling(60).mean()
    x = pd.to_datetime(h2.index)
    import matplotlib.dates as mdates
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    style(ax)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.plot(x, h1, color=BLUE, linewidth=2, label="Foreign extreme selling, $\\beta^F_S$ (H1)")
    ax.plot(x, h2, color=BLUE, linewidth=2, linestyle="--", label="Foreign selling minus buying, $\\beta^F_S-\\beta^F_B$ (H2)")
    ax.plot(x, h4, color=ORANGE, linewidth=2, linestyle=":", label="Individual buying minus selling, $\\beta^R_B-\\beta^R_S$ (H4)")
    ax.axvline(pd.Timestamp("2025-10-23"), color=MUTED, linewidth=0.8, linestyle="-")
    ax.text(pd.Timestamp("2025-10-16"), ax.get_ylim()[1] * 0.95, "second year $\\rightarrow$", fontsize=7,
            color=MUTED, ha="right", va="top")
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.set_ylabel("Percentage points (60-day mean)", fontsize=8, color=INK)
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=1)
    fig.tight_layout()
    fig.savefig(FIG / "f1_rolling.pdf")
    plt.close(fig)


def fig_forest():
    r = pd.read_csv(DATA / "tests_robustness.csv", **CSV)
    r = r[(r["투자자"] == "외국인") & (r["항"] == "β_S")]
    order = ["주 분석"] + [k for k in ROB_EN if k != "주 분석"]
    r = r.set_index("설정").loc[order]
    labels = [ROB_EN[k].replace("$^\\dagger$", "*").replace("$^\\ddagger$", "**").replace("\\le ", "\\leq ")
              .replace("$\\ge$", "$\\geq$").replace("Extreme 5\\%", "Extreme 5%").replace("Extreme 20\\%", "Extreme 20%")
              for k in order]
    y = np.arange(len(order))[::-1]
    est, se = r["평균"] * 100, r["se"] * 100
    fig, ax = plt.subplots(figsize=(6.5, 5.6))
    style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.errorbar(est, y, xerr=1.96 * se, fmt="o", color=BLUE, ecolor=BLUE, elinewidth=1.5, markersize=4, capsize=0)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Foreign extreme-selling coefficient $\\beta^F_S$ (pp), 95% interval", fontsize=8, color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "f2_forest.pdf")
    plt.close(fig)


def main():
    TAB.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "serif", "mathtext.fontset": "cm"})
    table_summary()
    table_tail()
    table_hyp()
    table_returns()
    table_robust()
    table_split()
    table_crash()
    table_factors()
    fig_rolling()
    fig_forest()
    print("표:", sorted(p.name for p in TAB.glob("*.tex")))
    print("그림:", sorted(p.name for p in FIG.glob("*.pdf")))


if __name__ == "__main__":
    main()
