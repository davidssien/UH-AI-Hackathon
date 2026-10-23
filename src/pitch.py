"""Regenerate pitch/ from artifacts/ + results.tsv (run by promote.py after every promotion).
PNGs: pred_vs_actual, residual_map_zip, shap_summary, error_before_after, deal_card. Text: numbers.md, demo_script.md.
Every number comes from artifacts/metrics.json or artifacts/houses_scored.parquet (eval.py-scored OOF).
"""
import json, os, shutil, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import core
from finance import affordability, monthly_cost

ART, OUT = os.path.join(ROOT, "artifacts"), os.path.join(ROOT, "pitch")
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, GOOD, CRIT, NEUTRAL = "#2a78d6", "#eb6834", "#0ca30c", "#d03b3b", "#8c8c8c"
# persona example inputs (the presenter types these; the rate is an EXAMPLE input, not a market quote)
PRIOR_LIST_LINE = ("Prior list price = the last asking price of a PREVIOUS listing of the same house that ended (sold or taken off market) at least 12 months before the current listing, time-adjusted with the ZIP's Zillow home-value index; it is not leakage because no event from the current listing (its price, price changes, or sale) is ever used, so it is information a buyer could have seen a year before this listing went up.")
PERSONA = dict(income=65000, savings=30000, rate=6.5, down=10.0, tax=2.2, ins_pct=1.0, pmi=0.5, closing=3.0)
plt.rcParams.update({"font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.6, "axes.titlecolor": INK, "axes.titleweight": "bold"})


def ftext(fig, *a, **k):  # plain text: "$" must not trigger mathtext
    return fig.text(*a, parse_math=False, **k)


def money(x):
    return f"${x:,.0f}"


def cost(price, p=PERSONA):
    return monthly_cost(price, p["rate"], p["down"], 30, p["tax"], price * p["ins_pct"] / 100, 0, 0, p["pmi"])


def pred_vs_actual(s, m):
    fig, ax = plt.subplots(figsize=(6.4, 6))
    ax.hexbin(s.price, s.pred, gridsize=70, xscale="log", yscale="log", bins="log", cmap="Blues", mincnt=1)
    lim = [2e4, 2e7]
    ax.plot(lim, lim, color=ORANGE, lw=2, label="perfect prediction")
    ax.set(xlim=lim, ylim=lim, xlabel="List price ($, log scale)", ylabel="Model fair price, out-of-fold ($, log scale)")
    ax.set_title(f"Homes: predicted vs actual — median error {m['segments']['homes']['cv']['mdape']:.1f}%", loc="left")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(f"{OUT}/pred_vs_actual.png", dpi=130); plt.close(fig)


def residual_map(s):
    z = s.assign(err=(s.price - s.pred) / s.pred * 100).groupby("zip").agg(lat=("lat", "median"), lon=("lon", "median"),
                                                                           err=("err", "median"), n=("err", "size"))
    z = z[z.n >= 20]
    fig, ax = plt.subplots(figsize=(7.5, 6))
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    cmap = LinearSegmentedColormap.from_list("div", ["#1c5cab", "#f0efec", "#b8322f"])
    sc = ax.scatter(z.lon, z.lat, c=z.err, s=np.sqrt(z.n) * 9, cmap=cmap, norm=TwoSlopeNorm(0, -10, 10),
                    edgecolor="white", linewidth=1)
    for k, (la, lo) in core.HUBS.items():
        ax.plot(lo, la, marker="*", color=INK, ms=11)
        ax.annotate({"downtown": "Downtown", "tmc": "TMC", "galleria": "Galleria", "energy": "Energy Corr.", "uh": "UH"}[k],
                    (lo, la), xytext=(5, 4), textcoords="offset points", fontsize=9, color=INK)
    cb = fig.colorbar(sc, ax=ax, shrink=0.8)
    cb.set_label("Median (list − fair) / fair, %   (red = listed above model)")
    ax.set(xlabel="Longitude", ylabel="Latitude")
    ax.set_title("Homes: residuals by ZIP (out-of-fold, ZIPs with ≥ 20 homes)", loc="left")
    fig.tight_layout(); fig.savefig(f"{OUT}/residual_map_zip.png", dpi=130); plt.close(fig)


def error_bars(m):
    """Homes: median % error from the naive baseline to the promoted model (MdAPE = headline metric)."""
    ba = pd.DataFrame(m["before_after"])
    hid = m["segments"]["homes"]["id"]
    ba = ba[(ba.segment == "homes") & ((ba.model == "b0") | (ba.kept == 1) | (ba.id == hid))].drop_duplicates("id")
    fig, ax = plt.subplots(figsize=(9, 3.4))
    cols = [NEUTRAL if r.model == "b0" else (BLUE if r.id == hid else "#9cc0ec") for r in ba.itertuples()]
    bars = ax.barh(range(len(ba))[::-1], ba.mdape, color=cols, height=0.6)
    names = {"b0": "Naive: median price of the ZIP"}
    ax.set_yticks(range(len(ba))[::-1], [names.get(r.model, ("One model for all listings" if r.model == "ref" else "Separate homes model + comps"))
                                         for r in ba.itertuples()])
    ax.bar_label(bars, labels=[f"{v:.1f}%" for v in ba.mdape], padding=4, color=INK, fontsize=11)
    ax.set_xlabel("Median absolute % error on homes, out-of-fold (lower is better)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, ba.mdape.max() * 1.2)
    b0, best = ba.mdape.iloc[0], ba[ba.id == hid].mdape.iloc[0]
    fig.suptitle(f"Typical pricing error on homes: {b0:.0f}% → {best:.1f}%", x=0.02, ha="left", fontweight="bold", color=INK)
    fig.tight_layout(); fig.savefig(f"{OUT}/error_before_after.png", dpi=130); plt.close(fig)


def pick_demo(s):
    h = s[(s.home_type == "SINGLE_FAMILY") & s.living_area.notna() & (s.year_built >= 1960)].copy()
    h["mi_uh"] = core.haversine(h.lat.values, h.lon.values, *core.UH)
    c = cost(h.price.values)
    h["monthly"], h["share"] = c["total"], c["total"] / (PERSONA["income"] / 12) * 100
    h["cash"] = h.price * (PERSONA["down"] + PERSONA["closing"]) / 100
    fits = h[(h.cash <= PERSONA["savings"]) & (h.share <= 36) & (h.mi_uh <= 20)]
    under = fits[(fits.deal == "UNDERPRICED") & fits.gap_pct.between(-35, -12)]
    u = under.iloc[(under.gap_pct + 20).abs().argsort()].iloc[0] if len(under) else fits.sort_values("gap_pct").iloc[0]
    near = fits[fits.row_id != u.row_id]
    f = near[near.deal == "FAIR"].iloc[(near[near.deal == "FAIR"].gap_pct.abs()).argsort()].iloc[0]
    over = h[(h.deal == "OVERPRICED") & h.price.between(u.price * 0.8, u.price * 1.3) & (h.mi_uh <= 20)]
    o = over.iloc[(over.gap_pct - 20).abs().argsort()].iloc[0] if len(over) else h.sort_values("gap_pct").iloc[-1]
    return u, f, o


def deal_card(u, shap):
    s = shap[shap.row_id == u.row_id]
    base, w = core.waterfall_frame(s)
    fig = plt.figure(figsize=(9, 5.4))
    ftext(fig, 0.04, 0.93, f"🟢 UNDERPRICED  ·  {u.address}".replace("🟢 ", ""), fontsize=15, weight="bold", color=GOOD)
    ftext(fig, 0.04, 0.87, f"{u.beds:.0f} bd · {u.baths:.1f} ba · {u.living_area:,.0f} sqft · built {u.year_built:.0f} · "
                         f"{u.mi_uh:.1f} mi from UH", fontsize=11, color=MUTED)
    ftext(fig, 0.04, 0.79, f"List {money(u.price)}   ·   Fair {money(u.pred)}   ·   {u.gap_pct:+.1f}%   ·   "
                         f"80% fair range {money(u.p10)} – {money(u.p90)}", fontsize=12, color=INK)
    ax = fig.add_axes([0.06, 0.62, 0.88, 0.1])
    ax.barh([0], [u.p90 - u.p10], left=[u.p10], color=BLUE, alpha=0.25, height=0.6)
    ax.plot(u.pred, 0, "o", color=BLUE, ms=10, label="model fair price")
    ax.plot(u.price, 0, "D", color=INK, ms=9, label="list price")
    ax.set_yticks([]); ax.grid(False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v / 1000:.0f}k"))
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.5), fontsize=9)
    ax2 = fig.add_axes([0.45, 0.06, 0.52, 0.40])
    w = w.iloc[::-1]
    ax2.barh(range(len(w)), w.delta, left=w.start, color=[GOOD if d >= 0 else CRIT for d in w.delta], height=0.65)
    ax2.set_yticks(range(len(w)), [l[:40] for l in w.label], fontsize=8.5)
    ax2.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
    ax2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v / 1000:.0f}k"))
    ax2.set_title("Why: SHAP factors (green raises, red lowers)", loc="left", fontsize=10)
    ax2.grid(axis="y", visible=False)
    c = cost(u.price)
    ftext(fig, 0.04, 0.40, "True monthly cost", fontsize=11, weight="bold", color=INK)
    ftext(fig, 0.04, 0.33, f"{money(c['total'])} / mo", fontsize=20, weight="bold", color=INK)
    sh, col = affordability(c["total"], PERSONA["income"])
    ftext(fig, 0.04, 0.12, f"P&I {money(c['principal_interest'])}\nTax {money(c['property_tax'])}\n"
                         f"Insurance {money(c['insurance'])}\nPMI {money(c['pmi'])}\n"
                         f"{sh:.0f}% of a ${PERSONA['income'] / 1000:.0f}k income", fontsize=9.5, color=MUTED)
    ftext(fig, 0.04, 0.03, f"Example inputs: {PERSONA['rate']}% rate (user input), {PERSONA['down']:.0f}% down, "
                         f"{PERSONA['tax']}% tax", fontsize=7.5, color=MUTED)
    fig.savefig(f"{OUT}/deal_card.png", dpi=130); plt.close(fig)


def write_text(m, u, f, o):
    H, L, A = m["segments"]["homes"], m["segments"]["land"], m["all_listings"]
    cv, zb, oz = H["cv"], m["zestimate_benchmark"], m["ours_on_zestimate_rows"]
    ba = pd.DataFrame(m["before_after"])
    b0 = ba[(ba.segment == "homes") & (ba.model == "b0")].iloc[0]
    sp = m.get("spatial_cv") or {}
    cu, cf, co = cost(u.price), cost(f.price), cost(o.price)
    nums = [
        "# Numbers quoted in the pitch (copied from artifacts/metrics.json — do not edit by hand)", "",
        "Headline = median absolute % error (MdAPE). MAE is listed for completeness; a few multi-million-dollar listings inflate it.", "",
        f"- **Homes: median pricing error {cv['mdape']:.2f}%** on {H['rows']:,} homes the model never saw (out-of-fold); naive ZIP-median baseline {b0.mdape:.2f}%",
        f"- Homes: half of predictions within ±{cv['mdape']:.1f}% of list price; RMSE(log) {cv['rmse_log']:.4f}; MAE {money(cv['mae'])}",
        f"- Homes: P10–P90 fair range covers {H['interval_coverage_p10_p90'] * 100:.1f}% of list prices (target 80%)",
        f"- Vacant land (separate segment, {L['rows']:,} lots): MdAPE {L['cv']['mdape']:.1f}% — land is much harder to price from listing data",
        f"- All {m['rows']:,} listings combined: MdAPE {A['mdape']:.2f}%",
        f"- Zestimate vs list price (reference, not apples-to-apples — Zillow sees the listing): MdAPE {zb['mdape']:.2f}% on {zb['rows']:,} homes; ours on the same homes {oz['mdape']:.2f}%",
        "- Deal labels (homes): " + ", ".join(f"{k} {v:,}" for k, v in H["deal_counts"].items()),
        "- Spatial CV (whole ZIPs held out): " + ("; ".join(f"{k} MdAPE {v['mdape']:.2f}%" for k, v in sp.items()) or "not run yet"),
        f"- Demo house 1 (underpriced): {u.address}, list {money(u.price)}, fair {money(u.pred)} ({u.gap_pct:+.1f}%), monthly {money(cu['total'])}",
        f"- Demo house 2 (fair): {f.address}, list {money(f.price)}, fair {money(f.pred)} ({f.gap_pct:+.1f}%), monthly {money(cf['total'])}",
        f"- Demo house 3 (overpriced): {o.address}, list {money(o.price)}, fair {money(o.pred)} ({o.gap_pct:+.1f}%), monthly {money(co['total'])}",
        f"- Prior list price feature: {PRIOR_LIST_LINE}",
        f"- Monthly-cost example inputs: rate {PERSONA['rate']}% (user-entered example, not a market quote), {PERSONA['down']:.0f}% down, tax {PERSONA['tax']}%, insurance {PERSONA['ins_pct']}%/yr, PMI {PERSONA['pmi']}%",
    ]
    open(f"{OUT}/numbers.md", "w").write("\n".join(nums) + "\n")
    script = f"""# 90-second demo script — "Maya, fresh UH grad"

**0:00 – Hook (10 s).** Maya just graduated from UH. She earns ${PERSONA['income']:,}, has ${PERSONA['savings']:,} saved, and wants
to stop renting. Houston has {m['rows']:,} listings in our data — which ones are actually a fair price, and what will they *really* cost per month?

**0:10 – The model (20 s).** Model card tab. A LightGBM model trained on {H['rows']:,} Houston homes predicts a fair price for homes it has
**never seen**: typical error **{cv['mdape']:.1f}%** (median), versus {b0.mdape:.0f}% for the naive "average price in the ZIP" guess.
Vacant land is priced by its own segment and reported separately. *Leakage: Zestimate, rent estimates and $/sqft are never features, duplicate listings never straddle
folds, and every price-based feature is fit on training folds only. {PRIOR_LIST_LINE}*

**0:30 – UH grad mode (25 s).** Enter income ${PERSONA['income']:,}, savings ${PERSONA['savings']:,}; in the sidebar type the rate
Maya was quoted (we use {PERSONA['rate']}% as an example input — the app never assumes a rate). The app lists affordable
fair or underpriced homes near UH. Top pick: **{u.address}** — {u.beds:.0f} bd / {u.baths:.1f} ba, {u.living_area:,.0f} sqft,
listed at **{money(u.price)}** vs a fair price of **{money(u.pred)}** ({u.gap_pct:+.1f}%), below its 80% fair range
({money(u.p10)}–{money(u.p90)}) → 🟢 UNDERPRICED.

**0:55 – Why + true cost (20 s).** The SHAP waterfall shows which factors drive the fair price. True monthly cost:
**{money(cu['total'])}/mo** (P&I {money(cu['principal_interest'])} + tax {money(cu['property_tax'])} + insurance {money(cu['insurance'])}
+ PMI {money(cu['pmi'])}) = {cu['total'] / (PERSONA['income'] / 12) * 100:.0f}% of her income.

**1:15 – Contrast (10 s).** Compare: {f.address} at {money(f.price)} is ⚪ FAIR ({f.gap_pct:+.1f}%); {o.address} at {money(o.price)}
is 🔴 OVERPRICED ({o.gap_pct:+.1f}%) — {money(co['total'])}/mo for a house the model values at {money(o.pred)}.

**1:25 – Close (5 s).** Fair price, honest range, the reason why, and the real monthly bill — in one Houston tool.
"""
    open(f"{OUT}/demo_script.md", "w").write(script)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    model, fz, s, shap, m = core.load()
    hs = s[s.segment == "homes"]
    pred_vs_actual(hs, m)
    residual_map(hs)
    shutil.copy(f"{ART}/shap_summary.png", f"{OUT}/shap_summary.png")
    error_bars(m)
    u, f, o = pick_demo(s)
    deal_card(u, shap)
    write_text(m, u, f, o)
    print("pitch assets written:", sorted(os.listdir(OUT)))
