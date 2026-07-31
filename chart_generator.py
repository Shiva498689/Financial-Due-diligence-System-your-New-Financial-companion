

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

BG      = "#0D1B2A"
PANEL   = "#142233"
NAVY    = "#1B3A6B"
GOLD    = "#C9A84C"
GOLD_LT = "#F0D080"
WHITE   = "#FFFFFF"
OFF_W   = "#E8EDF2"
LGREY   = "#8E9BAD"
DGREY   = "#3A4A5C"
GREEN   = "#27AE60"
GRN_LT  = "#52D68A"
AMBER   = "#E67E22"
AMB_LT  = "#F5A623"
RED     = "#E74C3C"
RED_LT  = "#FF6B6B"
CYAN    = "#17A8C4"

plt.rcParams.update({
    "font.family":     "DejaVu Sans",
    "axes.titlecolor": GOLD_LT,
    "axes.labelcolor": LGREY,
    "xtick.color":     OFF_W,
    "ytick.color":     OFF_W,
})



def _dark(fig, ax, title: str):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(DGREY); sp.set_linewidth(0.6)
    ax.set_title(title, color=GOLD_LT, fontsize=12, fontweight="bold", pad=14)
    ax.grid(color=DGREY, linewidth=0.45, alpha=0.55, linestyle="--")


def generate_all_charts(state: Dict[str, Any], out_dir: Path) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    charts: Dict[str, Path] = {}
    for name, fn in [
        ("kpi_health_scores",   _kpi),
        ("revenue_breakdown",   _revenue),
        ("margin_trends",       _margins),
        ("dcf_waterfall",       _dcf),
        ("risk_radar",          _radar),
        ("balance_sheet_pie",   _donut),
        ("risk_flowchart",      _risk_flowchart),
        ("valuation_flowchart", _valuation_flowchart),
    ]:
        try:
            p = fn(state, out_dir)
            if p:
                charts[name] = p
        except Exception as e:
            print(f"[chart] {name} failed: {e}")
    print(f"[chart] Generated {len(charts)}: {list(charts.keys())}")
    return charts


async def generate_all_charts_async(state: Dict[str, Any], out_dir: Path) -> Dict[str, Path]:
    """
    Async version of generate_all_charts.
    Each chart's blocking savefig() call runs in a thread via asyncio.to_thread(),
    so the event loop is never blocked. All 8 charts run concurrently.

    Called by generate_memo_async() in memo_agent.py.
    The original sync generate_all_charts() is untouched for nodes.py compatibility.
    """
    import asyncio
    out_dir.mkdir(parents=True, exist_ok=True)

    chart_fns = [
        ("kpi_health_scores",   _kpi),
        ("revenue_breakdown",   _revenue),
        ("margin_trends",       _margins),
        ("dcf_waterfall",       _dcf),
        ("risk_radar",          _radar),
        ("balance_sheet_pie",   _donut),
        ("risk_flowchart",      _risk_flowchart),
        ("valuation_flowchart", _valuation_flowchart),
    ]

    async def _run_one(name: str, fn) -> tuple[str, Optional[Path]]:
        try:
            # Each chart fn does CPU work + fig.savefig() — run in thread
            p = await asyncio.to_thread(fn, state, out_dir)
            return name, p
        except Exception as e:
            print(f"[chart-async] {name} failed: {e}")
            return name, None

    results = await asyncio.gather(*[_run_one(n, f) for n, f in chart_fns])
    charts = {name: path for name, path in results if path}
    print(f"[chart-async] Generated {len(charts)}: {list(charts.keys())}")
    return charts



def _kpi(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    quant = state.get("quant_analysis") or {}
    if not quant:
        return None

    SHORT = {
        "Revenue":"Total Revenue","CostOfRevenue":"Cost of Revenue",
        "GrossProfit":"Gross Profit","GrossMargin":"Gross Margin %",
        "OperatingIncome":"Operating Income","OperatingMargin":"Operating Margin %",
        "NetIncome":"Net Profit","NetProfitMargin":"Net Profit Margin %",
        "OperatingCashFlow":"Cash from Operations","CapitalExpenditures":"Capital Expenditure",
        "FreeCashFlow":"Free Cash Flow","CashAndEquivalents":"Cash & Equivalents",
        "CurrentAssets":"Current Assets","CurrentLiabilities":"Current Liabilities",
        "CurrentRatio":"Current Ratio","TotalAssets":"Total Assets",
        "TotalLiabilities":"Total Liabilities","LongTermDebt":"Long-term Debt",
        "ShareholdersEquity":"Shareholders Equity","ReturnOnEquity":"Return on Equity %",
        "ReturnOnAssets":"Return on Assets %","DebtToEquity":"Debt-to-Equity Ratio",
    }

    items = [(SHORT.get(k, k), v.get("audit", {}).get("health_score"))
             for k, v in quant.items() if v.get("audit", {}).get("health_score") is not None]
    if not items:
        return None

    labels = [l for l, _ in items]
    scores = [s for _, s in items]

    def col(s): return GRN_LT if s >= 8 else (AMB_LT if s >= 5 else RED_LT)
    colours = [col(s) for s in scores]

    n = len(labels)
    fig_h = max(6, n * 0.42 + 1.8)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    _dark(fig, ax, "KPI Health Scores — AI Audit Results")
    ax.grid(axis="y", visible=False)

    y = np.arange(n)
    for i, (s, c) in enumerate(zip(scores, colours)):
        ax.plot([0, s], [i, i], color=c, alpha=0.25, linewidth=1.4)
        ax.scatter(s, i, s=150, color=c, zorder=5, edgecolors=WHITE, linewidths=0.5)
        ax.text(min(s + 0.15, 10.5), i, f"{s}/10", va="center",
                fontsize=8.5, color=c, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlim(0, 11.8)
    ax.set_xlabel("Health Score  (1 = Poor  →  10 = Excellent)", fontsize=9)
    ax.invert_yaxis()
    ax.axvspan(8, 10, alpha=0.06, color=GREEN)
    ax.axvspan(5, 8,  alpha=0.04, color=AMBER)
    ax.axvspan(0, 5,  alpha=0.04, color=RED)

    patches = [mpatches.Patch(color=GRN_LT, label="Strong (8–10)"),
               mpatches.Patch(color=AMB_LT, label="Moderate (5–7)"),
               mpatches.Patch(color=RED_LT, label="Weak (1–4)")]
    # Legend BELOW the plot, not overlapping
    fig.legend(handles=patches, loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, 0.0), fontsize=8.5,
               facecolor=PANEL, edgecolor=DGREY, labelcolor=OFF_W,
               framealpha=0.9)

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    out = out_dir / "kpi_health_scores.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def _revenue(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    mapping = [
        ("Total Revenue",    "revenue_latest",          "revenue_previous"),
        ("Cost of Revenue",  "cogs_latest",             "cogs_previous"),
        ("Gross Profit",     "gross_profit_latest",     "gross_profit_previous"),
        ("Operating Income", "operating_income_latest", "operating_income_previous"),
        ("Net Profit",       "net_income_latest",       "net_income_previous"),
    ]
    cats, lv, pv = [], [], []
    for label, lk, pk in mapping:
        l = state.get(lk)
        if l is not None:
            cats.append(label)
            lv.append((l or 0) / 1e9)
            pv.append((state.get(pk) or 0) / 1e9)
    if not cats:
        return None

    x = np.arange(len(cats))
    w = 0.36
    fig, ax = plt.subplots(figsize=(10, 5.5))
    _dark(fig, ax, "Income Statement — Latest vs Previous Year")
    ax.grid(axis="x", visible=False)

    b1 = ax.bar(x - w/2, lv, w, label="Latest Year",
                color=NAVY, edgecolor=GOLD, linewidth=0.8, zorder=3)
    b2 = ax.bar(x + w/2, pv, w, label="Prior Year",
                color=DGREY, edgecolor=LGREY, linewidth=0.6, zorder=3)

    top = max(lv) * 1.30
    for bar, val in zip(b1, lv):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + top * 0.01,
                f"${val:.0f}B", ha="center", va="bottom",
                fontsize=7.5, color=GOLD_LT, fontweight="bold")
    for bar, val in zip(b2, pv):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + top * 0.01,
                f"${val:.0f}B", ha="center", va="bottom",
                fontsize=7.5, color=LGREY)
    for i, (l2, p2, bar) in enumerate(zip(lv, pv, b1)):
        if p2 and p2 > 0:
            chg = (l2 - p2) / p2 * 100
            sign = "+" if chg >= 0 else ""
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + top * 0.065,
                    f"{sign}{chg:.1f}%", ha="center", va="bottom",
                    fontsize=7, color=GRN_LT if chg >= 0 else RED_LT,
                    fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=9)
    ax.set_ylabel("USD Billions ($B)", fontsize=9)
    ax.set_ylim(0, top * 1.10)
    ax.legend(facecolor=PANEL, edgecolor=DGREY, labelcolor=OFF_W, fontsize=9)
    fig.tight_layout(pad=1.4)
    out = out_dir / "revenue_breakdown.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def _margins(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    quant = state.get("quant_analysis") or {}
    rev_p = state.get("revenue_previous") or 1

    def _pct(k):
        d = quant.get(k, {})
        v = d.get("value")
        return float(v) * 100 if v is not None else None

    pairs = [
        ("Gross\nMargin",     _pct("GrossMargin"),
         (state.get("gross_profit_previous") or 0) / rev_p * 100),
        ("Operating\nMargin", _pct("OperatingMargin"),
         (state.get("operating_income_previous") or 0) / rev_p * 100),
        ("Net Profit\nMargin",_pct("NetProfitMargin"),
         (state.get("net_income_previous") or 0) / rev_p * 100),
    ]
    pairs = [(l, lv, pv) for l, lv, pv in pairs if lv is not None]
    if not pairs:
        return None

    cats  = [p[0] for p in pairs]
    lvals = [p[1] for p in pairs]
    pvals = [p[2] for p in pairs]

    x = np.arange(len(cats))
    w = 0.32
    fig, ax = plt.subplots(figsize=(7.5, 5))
    _dark(fig, ax, "Profitability Margins — Latest vs Previous Year")
    ax.grid(axis="x", visible=False)

    b1 = ax.bar(x - w/2, lvals, w, label="Latest Year",
                color=GOLD, edgecolor=GOLD_LT, linewidth=0.6, zorder=3)
    b2 = ax.bar(x + w/2, pvals, w, label="Prior Year",
                color=DGREY, edgecolor=LGREY, linewidth=0.5, zorder=3)
    for bar, v in zip(b1, lvals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,
                f"{v:.1f}%", ha="center", va="bottom",
                color=GOLD_LT, fontsize=9.5, fontweight="bold")
    for bar, v in zip(b2, pvals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,
                f"{v:.1f}%", ha="center", va="bottom",
                color=LGREY, fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=10)
    ax.set_ylabel("Margin (%)", fontsize=9)
    ax.set_ylim(0, max(lvals) * 1.35)
    ax.legend(facecolor=PANEL, edgecolor=DGREY, labelcolor=OFF_W, fontsize=9)
    fig.tight_layout(pad=1.4)
    out = out_dir / "margin_trends.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def _dcf(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    p10 = state.get("monte_carlo_p10_floor")
    p50 = state.get("monte_carlo_p50_median")
    p90 = state.get("monte_carlo_p90_ceiling")
    dcf = state.get("deterministic_dcf_value")
    mkt = state.get("market_capitalization")
    if not p10:
        return None

    T = lambda v: (v or 0) / 1e12

    fig, ax = plt.subplots(figsize=(11, 4.5))
    _dark(fig, ax, "DCF Valuation Range — Monte Carlo vs Market Cap")
    ax.grid(axis="y", visible=False)

    ax.barh(0, T(p90) - T(p10), left=T(p10), height=0.38,
            color=NAVY, alpha=0.55, zorder=2)

    vals_x = [T(p10), T(p50), T(p90)]
    label_spec = [
        (T(p10), f"${T(p10):.2f}T\nBear (P10)",    RED_LT,  +0.38, "bottom"),
        (T(p50), f"${T(p50):.2f}T\nBase (P50)",    AMB_LT,  -0.38, "top"),
        (T(p90), f"${T(p90):.2f}T\nBull (P90)",    GRN_LT,  +0.38, "bottom"),
    ]
    for xv, label, col, yoff, va in label_spec:
        ax.axvline(xv, color=col, linewidth=2.0, zorder=4)
        ax.text(xv, yoff, label, ha="center", va=va,
                fontsize=8, color=col, fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", fc=PANEL, ec=col, alpha=0.85))

    if dcf:
        ax.axvline(T(dcf), color=CYAN, linewidth=2.2, linestyle="--", zorder=4)
        ax.text(T(dcf), -0.52, f"${T(dcf):.2f}T\nDCF Estimate",
                ha="center", va="top", fontsize=8, color=CYAN, fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", fc=PANEL, ec=CYAN, alpha=0.85))

    if mkt:
        ax.axvline(T(mkt), color=WHITE, linewidth=1.8, linestyle=":", zorder=4)
        ax.text(T(mkt), +0.52, f"${T(mkt):.2f}T\nMarket Cap",
                ha="center", va="bottom", fontsize=8, color=WHITE, fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", fc=PANEL, ec=WHITE, alpha=0.85))

    ax.set_yticks([])
    ax.set_xlabel("Equity / Enterprise Value (USD Trillions — $T)", fontsize=9)
    span = max(T(mkt) if mkt else 0, T(p90)) - T(p10)
    pad  = span * 0.22
    ax.set_xlim(T(p10) - pad, max(T(p90), T(mkt) if mkt else 0) + pad)
    ax.set_ylim(-0.85, 0.85)

    fig.tight_layout(pad=1.6)
    out = out_dir / "dcf_waterfall.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def _radar(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    piotroski = state.get("piotroski_f_score")
    beneish   = state.get("beneish_m_score")
    ohlson    = state.get("ohlson_o_score_probability")
    merton    = state.get("merton_distance_to_default")
    p10 = state.get("monte_carlo_p10_floor")
    p50 = state.get("monte_carlo_p50_median")
    p90 = state.get("monte_carlo_p90_ceiling")
    if piotroski is None:
        return None

    def norm_f(v): return min(10, float(v) / 9 * 10)
    def norm_b(v): return min(10, max(0, (-float(v) - 1) * 2.5))
    def norm_o(v): return min(10, max(0, (1 - float(v) * 100) * 10))
    def norm_m(v): return min(10, float(v) * 0.8)
    def norm_d(p10, p50, p90):
        if p10 and p50 and p90:
            spread = (p90 - p10) / (p50 + 1e-9)
            return max(0, 10 - spread * 10)
        return 5.0

    raw = [norm_f(piotroski), norm_b(beneish), norm_o(ohlson),
           norm_m(merton),    norm_d(p10, p50, p90)]

    cats = ["Financial\nStrength", "Earnings\nQuality",
            "Bankruptcy\nRisk", "Default\nDistance", "Valuation\nCertainty"]

    N = len(cats)
    angles = [n / N * 2 * math.pi for n in range(N)]
    angles += angles[:1]
    scores_plot = raw + raw[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)

    for level in [2, 4, 6, 8, 10]:
        ax.plot(angles, [level] * (N + 1), color=DGREY, linewidth=0.7, alpha=0.7)

    ax.fill(angles, scores_plot, alpha=0.20, color=GOLD)
    ax.plot(angles, scores_plot, color=GOLD, linewidth=2.5, zorder=4)

    for a, s in zip(angles[:-1], raw):
        dot_col = GRN_LT if s >= 7 else (AMB_LT if s >= 4 else RED_LT)
        ax.plot(a, s, "o", color=dot_col, markersize=9, zorder=6,
                markeredgecolor=WHITE, markeredgewidth=0.8)
        inner = max(s - 1.4, 0.5)
        ax.text(a, inner, f"{s:.1f}", ha="center", va="center",
                fontsize=8, fontweight="bold", color=dot_col, zorder=7,
                bbox=dict(boxstyle="round,pad=0.18", fc=PANEL, ec=dot_col,
                          alpha=0.88, linewidth=0.6))

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(cats, size=8.5, color=OFF_W)
    ax.set_ylim(0, 12)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(["2", "4", "6", "8", "10"], size=7, color=LGREY)
    ax.spines["polar"].set_edgecolor(DGREY)
    ax.set_title("Risk Model Radar — All 5 Models (10 = Safest)",
                 color=GOLD_LT, fontsize=11, fontweight="bold", pad=28)

    fig.tight_layout()
    out = out_dir / "risk_radar.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def _donut(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    cash  = state.get("cash_and_equivalents_latest") or 0
    rec   = state.get("receivables_latest") or 0
    inv   = state.get("inventory_latest") or 0
    ppe   = state.get("gross_ppe_latest") or 0
    total = state.get("total_assets_latest") or 0
    other = max(0, total - cash - rec - inv - ppe)

    if total <= 0:
        return None

    segs = [(l, v, c) for l, v, c in [
        ("Cash",         cash,  CYAN),
        ("Receivables",  rec,   GOLD),
        ("Inventory",    inv,   AMB_LT),
        ("PP&E",         ppe,   GRN_LT),
        ("Other Assets", other, LGREY),
    ] if v > 0]
    labels, vals, colours = zip(*segs)
    vb = [v / 1e9 for v in vals]

    fig, ax = plt.subplots(figsize=(7.5, 6.8))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    wedges, _, autotexts = ax.pie(
        vb, labels=None, colors=colours, autopct="%1.1f%%",
        startangle=90, pctdistance=0.75,
        wedgeprops={"edgecolor": BG, "linewidth": 2.5, "width": 0.55},
    )
    for at, c in zip(autotexts, colours):
        at.set_color(WHITE); at.set_fontweight("bold"); at.set_fontsize(8.5)

    leg_labels = [f"{l}  ${v:.0f}B  ({v/sum(vb)*100:.1f}%)"
                  for l, v in zip(labels, vb)]
    ax.legend(wedges, leg_labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.16), ncol=2,
              fontsize=8.5, facecolor=PANEL, edgecolor=DGREY,
              labelcolor=OFF_W, framealpha=0.9)

    ax.set_title(
        f"Total Asset Composition — ${total/1e9:.0f}B\n"
        "Where the company's money is deployed",
        color=GOLD_LT, fontsize=11, fontweight="bold", pad=10)
    ax.text(0, 0, f"${total/1e9:.0f}B\nTotal\nAssets",
            ha="center", va="center", fontsize=10,
            fontweight="bold", color=WHITE, linespacing=1.4)

    fig.tight_layout()
    out = out_dir / "balance_sheet_pie.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def _draw_box(ax, cx, cy, w, h, text, bg, fg=WHITE, fs=8.5, radius=0.04):
    """Draw a rounded rectangle node with centred text."""
    box = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                         boxstyle=f"round,pad={radius}",
                         facecolor=bg, edgecolor=fg, linewidth=1.0)
    ax.add_patch(box)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=fs, color=fg, fontweight="bold",
            wrap=True, multialignment="center")


def _arrow(ax, x1, y1, x2, y2, col=GOLD):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=col,
                                lw=1.4, mutation_scale=14))


def _risk_col(flag: str):
    if "LOW"  in flag: return "#1E8B4C"
    if "HIGH" in flag: return "#C0392B"
    return AMBER


def _risk_flowchart(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    risk = state.get("risk_report") or {}
    ticker = state.get("ticker", "")
    piotroski = state.get("piotroski_f_score", "N/A")
    beneish   = state.get("beneish_m_score",   "N/A")
    ohlson    = state.get("ohlson_o_score_probability")
    merton    = state.get("merton_distance_to_default", "N/A")
    overall   = risk.get("overall_assessment", {}).get("final_verdict", "N/A")

    def fmt_o(v):
        if v is None: return "N/A"
        f = float(v)
        return f"{f*100:.4f}%" if abs(f) < 0.01 else f"{f*100:.1f}%"

    p_flag  = risk.get("piotroski", {}).get("risk", "N/A")
    m_flag  = risk.get("beneish",   {}).get("risk", "N/A")
    o_flag  = risk.get("ohlson",    {}).get("risk", "N/A")
    d_flag  = risk.get("merton",    {}).get("risk", "N/A")
    f_flag  = risk.get("dcf_risk",  {}).get("risk", "N/A")

    nodes = [
        (f"Piotroski F-Score\n{piotroski}/9\n{p_flag}",  p_flag),
        (f"Beneish M-Score\n{beneish}\n{m_flag}",         m_flag),
        (f"Ohlson O-Score\n{fmt_o(ohlson)}\n{o_flag}",    o_flag),
        (f"Merton Default\n{merton}\n{d_flag}",           d_flag),
        (f"DCF Risk\n{f_flag}",                            f_flag),
    ]

    v_col = GREEN if "HEALTHY" in overall else (RED if "HIGH" in overall else AMBER)

    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 11); ax.set_ylim(0, 5)
    ax.axis("off")

   
    _draw_box(ax, 5.5, 4.3, 3.2, 0.7, f"{ticker} — Risk Assessment",
              NAVY, GOLD_LT, fs=10)

    xs = np.linspace(0.9, 10.1, 5)
    for i, ((label, flag), x) in enumerate(zip(nodes, xs)):
        _draw_box(ax, x, 2.5, 1.6, 1.1, label, _risk_col(flag), WHITE, fs=7.5)
        _arrow(ax, 5.5, 3.95, x, 3.05)

    _draw_box(ax, 5.5, 0.75, 4.5, 0.7, f"Overall Verdict: {overall}",
              v_col, WHITE, fs=10)
    for x in xs:
        _arrow(ax, x, 1.95, 5.5, 1.10)

    ax.set_title("Risk Assessment Flowchart — All 5 Models",
                 color=GOLD_LT, fontsize=12, fontweight="bold", pad=6)
    fig.tight_layout()
    out = out_dir / "risk_flowchart.png"
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out


def _valuation_flowchart(state: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    p10 = state.get("monte_carlo_p10_floor")
    p50 = state.get("monte_carlo_p50_median")
    p90 = state.get("monte_carlo_p90_ceiling")
    dcf = state.get("deterministic_dcf_value")
    mkt = state.get("market_capitalization")
    if not p10:
        return None

    T = lambda v: (v or 0) / 1e12

    over  = mkt and dcf and float(mkt) > float(dcf) * 1.1
    under = mkt and dcf and float(mkt) < float(dcf) * 0.9
    label = "Potentially Overvalued" if over else ("Potentially Undervalued" if under else "Fairly Valued")
    v_col = RED if over else (GREEN if under else AMBER)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 9); ax.set_ylim(0, 4.5)
    ax.axis("off")

    scenario_nodes = [
        (1.2, 3.5, f"Bear Case\n${T(p10):.2f}T",  RED_LT),
        (4.5, 3.5, f"Base Case\n${T(p50):.2f}T",  AMB_LT),
        (7.8, 3.5, f"Bull Case\n${T(p90):.2f}T",  GRN_LT),
    ]
    for cx, cy, txt, col in scenario_nodes:
        _draw_box(ax, cx, cy, 2.0, 0.75, txt, col, WHITE, fs=9)

    _draw_box(ax, 4.5, 2.1, 2.6, 0.75,
              f"DCF Estimate\n${T(dcf):.2f}T", NAVY, GOLD_LT, fs=9)
    for cx, cy, *_ in scenario_nodes:
        _arrow(ax, cx, cy - 0.375, 4.5, 2.475)

    _draw_box(ax, 7.5, 2.1, 2.2, 0.75,
              f"Market Cap\n${T(mkt):.2f}T", DGREY, OFF_W, fs=9)

    _draw_box(ax, 5.7, 0.8, 3.8, 0.75, label, v_col, WHITE, fs=10)
    _arrow(ax, 4.5, 1.725, 5.7, 1.175)
    _arrow(ax, 7.5, 1.725, 5.7, 1.175)

    ax.set_title("Valuation Decision — DCF vs Market Cap",
                 color=GOLD_LT, fontsize=12, fontweight="bold", pad=6)
    fig.tight_layout()
    out = out_dir / "valuation_flowchart.png"
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return out
