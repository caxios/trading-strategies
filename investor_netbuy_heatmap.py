"""일별 투자주체별(외국인/개인/기관) 순매수·순매도 시각화.

fetch_investor_netbuy.py 가 만든 investor_netbuy_daily_*.csv 를 읽어서
투자주체마다 PNG 2장씩 만든다 (왼쪽 코스피, 오른쪽 코스닥).

1. heatmap_<주체>.png : 종목 × 일자 히트맵. 기간 합계 기준 순매수 상위 / 순매도 상위 종목을
                        골라서, 그 종목이 날마다 얼마나 순매수(빨강)·순매도(파랑)됐는지 보여준다.
                        해당 날짜 상위 N위 밖이라 값이 없는 칸은 비워 둔다.
2. board_<주체>.png   : 일자별 순위표. 날짜마다 순매수 TOP10 / 순매도 TOP10 종목명과 금액.

사용 예:
    python investor_netbuy_heatmap.py
    python investor_netbuy_heatmap.py --csv investor_netbuy_daily_top50_20261012_20261022.csv --rows 30 --top 10
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402

ROOT = Path(__file__).resolve().parent

INVESTORS = ["외국인", "기관", "개인"]
MARKETS = ["KOSPI", "KOSDAQ"]

# 색상: 한국 시장 관례대로 순매수 = 빨강, 순매도 = 파랑, 0 = 중립 회색
SELL = "#2a78d6"
NEUTRAL = "#f0efec"
BUY = "#e34948"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
CMAP = LinearSegmentedColormap.from_list("netbuy", [SELL, NEUTRAL, BUY])

plt.rcParams.update({
    "font.family": "Malgun Gothic",
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": INK,
})


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype={"종목코드": str, "일자": str})
    df["억"] = df["순매수거래대금"] / 1e8
    return df


def fmt_eok(v: float) -> str:
    """억 단위 금액 → '+1,234' / '-2.4조'."""
    if abs(v) >= 10000:
        return f"{v / 10000:+.1f}조"
    return f"{v:+,.0f}"


def date_label(d: str) -> str:
    return pd.Timestamp(d).strftime("%m/%d\n(%a)").replace("Mon", "월").replace("Tue", "화") \
        .replace("Wed", "수").replace("Thu", "목").replace("Fri", "금")


def week_break(dates: list[str]) -> int | None:
    """저번주/이번주 경계 열 인덱스."""
    ts = [pd.Timestamp(d) for d in dates]
    for i in range(1, len(ts)):
        if ts[i].isocalendar().week != ts[i - 1].isocalendar().week:
            return i
    return None


def text_color(rgba) -> str:
    r, g, b = rgba[:3]
    return INK if (0.299 * r + 0.587 * g + 0.114 * b) > 0.6 else "#ffffff"


# ---------------------------------------------------------------- heatmap

def pick_rows(sub: pd.DataFrame, n_rows: int) -> pd.DataFrame:
    """기간 합계 기준 순매수 상위 n/2, 순매도 상위 n/2 종목의 종목×일자 행렬."""
    piv = sub.pivot_table(index=["종목코드", "종목명"], columns="일자", values="억", aggfunc="first")
    total = piv.sum(axis=1, skipna=True)
    half = n_rows // 2
    buys = total[total > 0].sort_values(ascending=False).head(half).index
    sells = total[total < 0].sort_values().head(half).index[::-1]
    piv = piv.loc[list(buys) + list(sells)]
    piv["합계"] = total.loc[piv.index]
    return piv


def draw_heatmap(ax, piv: pd.DataFrame, dates: list[str], title: str):
    vals = piv[dates].to_numpy(dtype=float)
    finite = np.abs(vals[np.isfinite(vals)])
    vmax = np.percentile(finite, 90) if finite.size else 1  # 극단값(대형주) 때문에 색이 죽지 않게 90%에서 자름
    norm = Normalize(-vmax, vmax)

    n_r, n_c = vals.shape
    for i in range(n_r):
        for j in range(n_c):
            v = vals[i, j]
            if np.isnan(v):
                ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=SURFACE, edgecolor=GRID, lw=0.6))
                continue
            c = CMAP(norm(np.clip(v, -vmax, vmax)))
            ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=c, edgecolor=SURFACE, lw=2))
            ax.text(j + 0.5, i + 0.5, fmt_eok(v), ha="center", va="center", fontsize=7.5, color=text_color(c))

    # 합계 열 (색 없이 숫자만)
    for i, v in enumerate(piv["합계"]):
        ax.text(n_c + 0.6, i + 0.5, fmt_eok(v), ha="left", va="center", fontsize=8,
                color=BUY if v > 0 else SELL, fontweight="bold")
    ax.text(n_c + 0.6, -0.4, "합계*", ha="left", va="bottom", fontsize=8.5, color=INK_2)

    # 순매수/순매도 그룹 구분선
    n_buy = int((piv["합계"] > 0).sum())
    if 0 < n_buy < n_r:
        ax.axhline(n_buy, color=INK_2, lw=1.2)

    wb = week_break(dates)
    if wb:
        ax.axvline(wb, color=INK_2, lw=1.2, ls=(0, (3, 2)))

    ax.set_xlim(0, n_c + 2.4)
    ax.set_ylim(n_r, -0.0)
    ax.set_xticks(np.arange(n_c) + 0.5)
    ax.set_xticklabels([date_label(d) for d in dates], fontsize=8.5)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(n_r) + 0.5)
    ax.set_yticklabels(piv.index.get_level_values("종목명"), fontsize=9)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=13, loc="left", pad=34, color=INK, fontweight="bold")
    return norm


def heatmap_figure(df: pd.DataFrame, investor: str, n_rows: int, out: Path):
    dates = sorted(df["일자"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(22, 0.36 * n_rows + 3.2))
    for ax, market in zip(axes, MARKETS):
        sub = df[(df["투자자"] == investor) & (df["시장"] == market)]
        piv = pick_rows(sub, n_rows)
        draw_heatmap(ax, piv, dates, f"{market}")
    top_n = int(df["순위"].max())
    fig.suptitle(f"{investor} 일별 순매수 거래대금 (단위: 억원)", x=0.02, ha="left", fontsize=17,
                 fontweight="bold", y=0.995)
    fig.text(0.02, 0.005,
             f"빨강 = 순매수, 파랑 = 순매도 · 빈 칸 = 그날 순매수/순매도 상위 {top_n}위 밖(값 미수집) · "
             f"가로 실선 위: 기간 순매수 상위, 아래: 순매도 상위 · 점선 = 주 경계 · "
             f"*합계는 상위 {top_n}위에 든 날만 더한 값 · 출처: KRX(pykrx)",
             fontsize=9, color=MUTED, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(out, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- board

def draw_board(ax, sub: pd.DataFrame, dates: list[str], top: int, title: str):
    n_c = len(dates)
    gap = 0.6  # 순매수 블록과 순매도 블록 사이 간격
    vals = sub.loc[sub["순위"] <= top, "억"].abs()
    vmax = np.percentile(vals, 90) if len(vals) else 1
    norm = Normalize(-vmax, vmax)

    for j, d in enumerate(dates):
        day = sub[sub["일자"] == d]
        for k, side in enumerate(["순매수", "순매도"]):
            rows = day[(day["구분"] == side) & (day["순위"] <= top)].sort_values("순위")
            for _, r in rows.iterrows():
                y = (r["순위"] - 1) + k * (top + gap)
                c = CMAP(norm(np.clip(r["억"], -vmax, vmax)))
                ax.add_patch(plt.Rectangle((j, y), 1, 1, facecolor=c, edgecolor=SURFACE, lw=2))
                tc = text_color(c)
                name = r["종목명"] if len(r["종목명"]) <= 9 else r["종목명"][:8] + "…"
                ax.text(j + 0.5, y + 0.38, name, ha="center", va="center", fontsize=8, color=tc)
                ax.text(j + 0.5, y + 0.72, fmt_eok(r["억"]), ha="center", va="center", fontsize=7, color=tc)

    total_h = 2 * top + gap
    for k, side in enumerate(["순매수 TOP", "순매도 TOP"]):
        y0 = k * (top + gap)
        for i in range(top):
            ax.text(-0.12, y0 + i + 0.5, f"{i + 1}", ha="right", va="center", fontsize=8, color=MUTED)
        ax.text(-0.55, y0 + top / 2, f"{side}{top}", ha="right", va="center", fontsize=10,
                color=BUY if k == 0 else SELL, fontweight="bold", rotation=90)

    wb = week_break(dates)
    if wb:
        ax.axvline(wb, color=INK_2, lw=1.2, ls=(0, (3, 2)))

    ax.set_xlim(-0.9, n_c)
    ax.set_ylim(total_h, 0)
    ax.set_xticks(np.arange(n_c) + 0.5)
    ax.set_xticklabels([date_label(d) for d in dates], fontsize=8.5)
    ax.xaxis.tick_top()
    ax.set_yticks([])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=13, loc="left", pad=34, fontweight="bold")


def board_figure(df: pd.DataFrame, investor: str, top: int, out: Path):
    dates = sorted(df["일자"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(26, 0.62 * top * 2 + 3))
    for ax, market in zip(axes, MARKETS):
        sub = df[(df["투자자"] == investor) & (df["시장"] == market)]
        draw_board(ax, sub, dates, top, market)
    fig.suptitle(f"{investor} 일자별 순매수 / 순매도 TOP{top} (거래대금, 단위: 억원)", x=0.02, ha="left",
                 fontsize=17, fontweight="bold", y=0.995)
    fig.text(0.02, 0.005, "색이 진할수록 금액이 큼 (빨강 = 순매수, 파랑 = 순매도) · 점선 = 주 경계 · 출처: KRX(pykrx)",
             fontsize=9, color=MUTED, ha="left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(out, dpi=150)
    plt.close(fig)


def latest_csv() -> Path:
    files = [*ROOT.glob("investor_netbuy_daily_*.csv"), *(ROOT / "data").glob("investor_netbuy_daily_*.csv")]
    files.sort(key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit("investor_netbuy_daily_*.csv 가 없습니다. fetch_investor_netbuy.py 를 먼저 실행하세요.")
    return files[-1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=None, help="입력 CSV (기본: 루트 또는 data/ 의 최신 investor_netbuy_daily_*.csv)")
    p.add_argument("--rows", type=int, default=30, help="히트맵 종목 수 (순매수 절반 + 순매도 절반)")
    p.add_argument("--top", type=int, default=10, help="순위표에 보여줄 일별 순위 수")
    p.add_argument("--outdir", default=str(ROOT))
    args = p.parse_args()

    csv_path = Path(args.csv) if args.csv else latest_csv()
    df = load(csv_path)
    outdir = Path(args.outdir)
    print(f"입력: {csv_path.name} ({len(df)}행, 일자 {df['일자'].min()}~{df['일자'].max()})")

    for inv in INVESTORS:
        h = outdir / f"investor_netbuy_heatmap_{inv}.png"
        b = outdir / f"investor_netbuy_board_{inv}.png"
        heatmap_figure(df, inv, args.rows, h)
        board_figure(df, inv, args.top, b)
        print(f"저장: {h.name}, {b.name}")


if __name__ == "__main__":
    main()
