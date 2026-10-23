"""Houston Housing Market Intelligence — fair-price deal finder + true monthly cost, for a UH grad's first home.
Loads only artifacts/ (no training at startup).  streamlit run app/streamlit_app.py
"""
import os, sys

import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
from finance import affordability, monthly_cost

st.set_page_config(page_title="Houston Fair Price", page_icon="🏠", layout="wide")
COLORS = {"UNDERPRICED": [12, 163, 12], "FAIR": [140, 140, 140], "OVERPRICED": [208, 59, 59]}
BADGE = {"UNDERPRICED": "🟢 UNDERPRICED", "FAIR": "⚪ FAIR", "OVERPRICED": "🔴 OVERPRICED"}


@st.cache_resource
def load():
    return core.load()


model, fz, scored, shap, metrics = load()
homes = scored[scored.home_type != "LOT"]


def money(x):
    return "n/a" if x is None or pd.isna(x) else f"${x:,.0f}"


# ---------------- sidebar: financing assumptions (all user inputs) ----------------
with st.sidebar:
    st.header("Your financing")
    st.caption("Rates are **your inputs** — enter the rate a lender quotes you. We don't know today's rate.")
    rate = st.number_input("Mortgage interest rate (%)", 0.0, 15.0, 6.5, 0.125,
                           help="Placeholder value. Replace with your actual quoted rate.")
    down_pct = st.number_input("Down payment (%)", 0.0, 100.0, 10.0, 1.0)
    term = st.selectbox("Term (years)", [30, 20, 15], 0)
    tax_pct = st.slider("Property tax (% of price / yr)", 1.8, 3.0, 2.2, 0.05,
                        help="Harris-area total rates commonly fall around 2–3%; check your exact tax unit.")
    ins_pct = st.number_input("Home + windstorm insurance (% of price / yr)", 0.0, 5.0, 1.0, 0.1,
                              help="Assumption — replace with a real quote.")
    pmi_pct = st.number_input("PMI (% of loan / yr, if down < 20%)", 0.0, 2.0, 0.5, 0.05)


def cost(price, hoa=0.0, flood=0.0):
    return monthly_cost(price, rate, down_pct, term, tax_pct, price * ins_pct / 100, hoa, flood, pmi_pct)


def waterfall(contrib, title):
    base, w = core.waterfall_frame(contrib)
    w["color"] = np.where(w.delta >= 0, "raises value", "lowers value")
    w["order"] = range(len(w))
    w["txt"] = w.pct.map(lambda p: f"{p:+.1f}%")
    ch = alt.Chart(w).mark_bar().encode(
        y=alt.Y("label:N", sort=alt.SortField("order"), title=None),
        x=alt.X("start:Q", title="Estimated price ($)", axis=alt.Axis(format="$,.0f")), x2="end:Q",
        color=alt.Color("color:N", scale=alt.Scale(domain=["raises value", "lowers value"], range=["#1a9850", "#d73027"]),
                        legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["label", alt.Tooltip("delta:Q", format="$,.0f", title="$ impact"), alt.Tooltip("txt:N", title="% impact")])
    st.markdown(f"**{title}** — starts at the model's average Houston "
                f"{'price per sqft' if (contrib.feature == '_size').any() else 'listing'} ({money(base)}), each bar is one factor.")
    st.altair_chart(ch, width="stretch")


def range_chart(price, pred, p10, p90):
    df = pd.DataFrame([{"what": "Fair range (P10–P90)", "lo": p10, "hi": p90}])
    pts = pd.DataFrame([{"what": "Model fair price", "v": pred}, {"what": "List price", "v": price}])
    base = alt.Chart(df).mark_bar(height=18, opacity=0.35, color="#4575b4").encode(
        x=alt.X("lo:Q", title=None, axis=alt.Axis(format="$,.0f"), scale=alt.Scale(zero=False)), x2="hi:Q")
    dots = alt.Chart(pts).mark_point(size=160, filled=True).encode(
        x="v:Q", color=alt.Color("what:N", scale=alt.Scale(range=["#4575b4", "#000000"]), legend=alt.Legend(orient="bottom", title=None)),
        shape="what:N", tooltip=["what", alt.Tooltip("v:Q", format="$,.0f")])
    st.altair_chart((base + dots).properties(height=70), width="stretch")


def cost_table(c):
    t = pd.DataFrame({"Monthly": [c["principal_interest"], c["property_tax"], c["insurance"], c["hoa"], c["flood"], c["pmi"], c["total"]]},
                     index=["Principal & interest", "Property tax", "Home/windstorm insurance", "HOA", "Flood insurance", "PMI", "TOTAL"])
    st.dataframe(t.style.format("${:,.0f}"), width="stretch")


def house_detail(r):
    st.subheader(f"{r.address}")
    if isinstance(r.get("img"), str) and r.img.startswith("http"):
        st.image(r.img, width=360)
    st.caption(f"{r.home_type.replace('_', ' ').title()} · {r.beds:.0f} bd · {r.baths:.1f} ba · "
               f"{r.living_area:,.0f} sqft · built {r.year_built:.0f} · [Zillow listing]({r.url})" if pd.notna(r.living_area)
               else f"{r.home_type} · [Zillow listing]({r.url})")
    a, b, c, d = st.columns(4)
    a.metric("List price", money(r.price))
    b.metric("Model fair price", money(r.pred), f"{r.gap_pct:+.1f}% list vs fair", delta_color="inverse")
    c.metric("Fair range (P10–P90)", f"{money(r.p10)} – {money(r.p90)}")
    d.metric("Zillow Zestimate (reference)", money(r.zestimate))
    st.markdown(f"### {BADGE[r.deal]}")
    range_chart(r.price, r.pred, r.p10, r.p90)
    s = shap[shap.row_id == r.row_id]
    if len(s):
        waterfall(s, "Why: LightGBM SHAP explanation" + (" (the fair price above is the blend of several models)"
                                                           if "blend" in metrics["segments"]["homes"] else ""))
    cc = cost(r.price)
    st.markdown(f"**True monthly cost at list price:** {money(cc['total'])} / month "
                f"(down payment {money(cc['down_payment'])}) — see sidebar assumptions.")


tabs = st.tabs(["🗺️ Deal finder", "💰 What's it worth?", "🏠 True monthly cost", "🎓 UH grad mode", "📋 Model card"])

# ---------------- 1. map explorer ----------------
with tabs[0]:
    st.markdown("Every listing priced against an **honest out-of-fold model estimate** (the model never saw that house). "
                "🟢 underpriced = list below the P10 fair range *and* ≥10% under fair price.")
    f1, f2, f3, f4, f5 = st.columns([2, 1, 2, 2, 1])
    lo, hi = f1.slider("Price ($k)", 0, 3000, (150, 600), 25)
    beds = f2.number_input("Min beds", 0, 10, 2)
    types = f3.multiselect("Type", sorted(scored.home_type.unique()), ["SINGLE_FAMILY", "TOWNHOUSE", "CONDO"])
    zips = f4.multiselect("ZIP", sorted(scored.zip.unique()))
    deals_only = f5.checkbox("Deals only", False)
    v = scored[scored.price.between(lo * 1000, hi * 1000) & scored.home_type.isin(types)]
    v = v[(v.beds >= beds) | v.beds.isna()] if beds == 0 else v[v.beds >= beds]
    if zips:
        v = v[v.zip.isin(zips)]
    if deals_only:
        v = v[v.deal == "UNDERPRICED"]
    st.caption(f"{len(v):,} listings · {int((v.deal == 'UNDERPRICED').sum()):,} underpriced · "
               f"{int((v.deal == 'OVERPRICED').sum()):,} overpriced")
    m = v.assign(color=v.deal.map(COLORS), price_txt=v.price.map(money), pred_txt=v.pred.map(money))
    layer = pdk.Layer("ScatterplotLayer", m[["row_id", "lat", "lon", "color", "address", "price_txt", "pred_txt", "deal"]],
                      id="houses", get_position=["lon", "lat"], get_fill_color="color", get_radius=120,
                      radius_min_pixels=2, radius_max_pixels=8, pickable=True, opacity=0.8)
    deck = pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=29.76, longitude=-95.40, zoom=9),
                    tooltip={"text": "{address}\nList {price_txt} · Fair {pred_txt}\n{deal}"}, map_style=None)
    ev = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="map")
    picked = None
    try:
        objs = ev.selection.objects.get("houses", [])
        picked = objs[0]["row_id"] if objs else None
    except Exception:
        pass
    top = v.sort_values("gap_pct").head(200)
    opts = top.row_id.tolist()
    if picked is not None and picked not in opts:
        opts = [picked] + opts
    if opts:
        lab = scored.set_index("row_id")
        sel = st.selectbox("Selected house (click the map, or pick from the best deals)", opts,
                           index=opts.index(picked) if picked in opts else 0,
                           format_func=lambda i: f"{lab.at[i, 'address']} — list {money(lab.at[i, 'price'])}, "
                                                 f"{lab.at[i, 'gap_pct']:+.1f}% vs fair ({lab.at[i, 'deal']})")
        house_detail(scored[scored.row_id == sel].iloc[0])
    else:
        st.info("No listings match these filters.")

# ---------------- 2. what's it worth ----------------
with tabs[1]:
    st.markdown("Describe a home — get a fair price, a likely range, and why.")
    with st.form("worth"):
        c1, c2, c3, c4 = st.columns(4)
        zip_ = c1.selectbox("ZIP", fz["homes"].cats["zip"], index=fz["homes"].cats["zip"].index("77004") if "77004" in fz["homes"].cats["zip"] else 0)
        htype = c2.selectbox("Home type", [t for t in fz["homes"].cats["home_type"] if t != "LOT"])
        beds_ = c3.number_input("Bedrooms", 0, 10, 3)
        baths_ = c4.number_input("Bathrooms", 0.0, 10.0, 2.0, 0.5)
        c5, c6, c7, c8 = st.columns(4)
        sqft = c5.number_input("Living area (sqft)", 300, 15000, 1600, 50)
        lot = c6.number_input("Lot (sqft, 0 = unknown)", 0, 500000, 5000, 100)
        year = c7.number_input("Year built", 1900, 2025, 2005)
        latlon = c8.text_input("Lat, lon (optional)", "", help="Blank = ZIP centroid")
        new_build = st.checkbox("New construction (builder listing)", value=False)
        go = st.form_submit_button("Estimate")
    if go:
        lat = lon = None
        if latlon.strip():
            try:
                lat, lon = (float(x) for x in latlon.split(","))
            except ValueError:
                st.warning("Couldn't read lat, lon — using the ZIP centroid.")
        res = core.predict_home(model, fz, beds=beds_, baths=baths_, living_area=sqft, lot_sqft=lot or np.nan,
                                home_type=htype, year_built=year, zip=zip_, lat=lat, lon=lon,
                                f_new_home=float(new_build), f_has_builder=float(new_build))
        st.session_state["worth_price"] = res["pred"]
        a, b = st.columns(2)
        a.metric("Fair price estimate", money(res["pred"]))
        b.metric("Likely range (P10–P90)", f"{money(res['p10'])} – {money(res['p90'])}")
        waterfall(res["contrib"], "What drives this estimate (SHAP)")
        st.caption("Tip: the True monthly cost tab is prefilled with this estimate.")

# ---------------- 3. true monthly cost ----------------
with tabs[2]:
    c1, c2, c3 = st.columns(3)
    price = c1.number_input("Home price ($)", 10000, 10000000, int(st.session_state.get("worth_price", 300000)), 5000)
    hoa = c2.number_input("HOA ($ / month)", 0, 5000, 0, 10)
    income = c3.number_input("Your gross household income ($ / yr)", 0, 2000000, 65000, 1000)
    c4, c5 = st.columns(2)
    flood_on = c4.checkbox("Add flood insurance", False)
    flood = c5.number_input("Flood insurance ($ / yr)", 0, 20000, 700, 50, disabled=not flood_on,
                            help="Assumption — get a quote; cost depends heavily on flood zone.") if flood_on else 0
    cc = cost(price, hoa, flood)
    share, color = affordability(cc["total"], income)
    st.markdown(f"## {money(cc['total'])} / month")
    st.markdown({"green": "🟢", "yellow": "🟡", "red": "🔴"}[color] +
                f" **{share:.1f}% of gross monthly income** (green ≤ 30%, yellow ≤ 36%, red above)")
    cost_table(cc)
    st.caption(f"Down payment {money(cc['down_payment'])} · loan {money(cc['loan'])} · rate {rate}% (your input) · {term}-year term.")

# ---------------- 4. persona ----------------
with tabs[3]:
    st.markdown("### 🎓 Fresh UH grad buying a first home")
    p1, p2, p3, p4 = st.columns(4)
    inc = p1.number_input("Income ($ / yr)", 20000, 1000000, 65000, 1000, key="p_inc")
    sav = p2.number_input("Savings for down payment + closing ($)", 0, 2000000, 30000, 1000, key="p_sav")
    close_pct = p3.number_input("Closing costs (% of price)", 0.0, 6.0, 3.0, 0.5, help="Assumption")
    max_share = p4.selectbox("Max housing cost share", [30, 36], 0, format_func=lambda x: f"{x}% of income")
    near_uh = st.slider("Max miles from UH", 2, 60, 25)
    h = homes[homes.deal.isin(["UNDERPRICED", "FAIR"])].copy()
    h["mi_uh"] = core.haversine(h.lat.values, h.lon.values, *core.UH)
    c = cost(h.price.values)
    h["monthly"] = c["total"]
    h["cash_needed"] = h.price * (down_pct + close_pct) / 100
    h["share"] = h.monthly / (inc / 12) * 100
    ok = h[(h.share <= max_share) & (h.cash_needed <= sav) & (h.mi_uh <= near_uh)].sort_values("gap_pct").head(10)
    st.caption(f"Down payment {down_pct:.0f}% at {rate}% (sidebar, your inputs). {len(h[(h.share <= max_share) & (h.cash_needed <= sav) & (h.mi_uh <= near_uh)]):,} homes fit; showing the 10 most underpriced.")
    if ok.empty:
        st.warning("Nothing fits — try a lower down payment %, more savings, or a wider radius.")
    else:
        show = ok.assign(Deal=ok.deal.map(BADGE), List=ok.price.map(money), Fair=ok.pred.map(money),
                         Gap=ok.gap_pct.map(lambda g: f"{g:+.1f}%"), Monthly=ok.monthly.map(money),
                         Share=ok.share.map(lambda s: f"{s:.0f}%"), Miles_to_UH=ok.mi_uh.round(1))
        st.dataframe(show[["address", "Deal", "List", "Fair", "Gap", "Monthly", "Share", "beds", "baths", "living_area", "Miles_to_UH", "url"]],
                     width="stretch", hide_index=True,
                     column_config={"url": st.column_config.LinkColumn("Listing", display_text="Zillow")})
        pick = st.selectbox("Explain one", ok.row_id.tolist(), format_func=lambda i: ok.set_index("row_id").at[i, "address"])
        house_detail(ok[ok.row_id == pick].iloc[0])

# ---------------- 5. model card ----------------
with tabs[4]:
    H, L, A = metrics["segments"]["homes"], metrics["segments"]["land"], metrics["all_listings"]
    zb, oz = metrics["zestimate_benchmark"], metrics["ours_on_zestimate_rows"]
    st.markdown(f"### Homes model `{H['id']}` — LightGBM on log(price), {H['rows']:,} Houston homes")
    st.caption("Headline metric: median absolute % error (MdAPE). Dollar MAE is pulled up by a few multi-million-dollar listings.")
    a, b, c, d = st.columns(4)
    a.metric("Homes: median % error", f"{H['cv']['mdape']:.2f}%", help="Out-of-fold: the model never saw these houses")
    b.metric("Homes: P10–P90 coverage", f"{H['interval_coverage_p10_p90'] * 100:.1f}%", help="Target ~80%")
    c.metric("Vacant land: median % error", f"{L['cv']['mdape']:.1f}%", help=f"{L['rows']:,} LOT listings, priced by `{L['id']}`")
    d.metric("All listings: median % error", f"{A['mdape']:.2f}%")
    st.markdown("#### Before → after (out-of-fold, frozen GroupKFold)")
    ba = pd.DataFrame(metrics["before_after"])
    seg = st.radio("Segment", ["homes", "land", "all"], horizontal=True)
    bs = ba[ba.segment == seg].drop(columns=["segment", "model"])
    st.dataframe(bs.assign(mdape=bs.mdape.map(lambda x: f"{x:.2f}%"), mae=bs.mae.map(money),
                           kept=bs.kept.map({1: "✅", 0: "—"})), hide_index=True, width="stretch")
    st.markdown("#### Zillow Zestimate benchmark *(reference, not apples-to-apples: Zillow sees the listing)*")
    st.dataframe(pd.DataFrame({"MdAPE": [f"{zb['mdape']:.2f}%", f"{oz['mdape']:.2f}%"], "MAE": [money(zb["mae"]), money(oz["mae"])]},
                              index=["Zestimate vs list price", "Our homes model (same rows)"]), width="stretch")
    st.caption(f"{zb['rows']:,} homes that have a real Zestimate.")
    st.markdown("#### Leakage firewall")
    st.markdown("\n".join(f"- {x}" for x in metrics["leakage_firewall"]))
    st.markdown("#### Spatial robustness (whole ZIPs held out)")
    sp = metrics.get("spatial_cv") or {}
    st.write("\n".join(f"- {k}: MdAPE {v['mdape']:.2f}%, RMSE_log {v['rmse_log']:.4f}" for k, v in sp.items()) or "Not run yet.")
    st.markdown("#### Feature importance, homes model (gain share)")
    fi = pd.DataFrame({"feature": [core.pretty(k) for k in H["feature_importance_gain"]],
                       "share": list(H["feature_importance_gain"].values())})
    st.altair_chart(alt.Chart(fi).mark_bar(color="#2a78d6").encode(y=alt.Y("feature:N", sort="-x", title=None),
                                                                  x=alt.X("share:Q", axis=alt.Axis(format="%"))), width="stretch")
    img = os.path.join(core.ART, "shap_summary.png")
    if os.path.exists(img):
        st.image(img, caption="SHAP summary, homes model (out-of-fold fold models)")
