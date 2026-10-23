# 90-second demo script — "Maya, fresh UH grad"

**0:00 – Hook (10 s).** Maya just graduated from UH. She earns $65,000, has $30,000 saved, and wants
to stop renting. Houston has 25,800 listings in our data — which ones are actually a fair price, and what will they *really* cost per month?

**0:10 – The model (20 s).** Model card tab. A LightGBM model trained on 22,764 Houston homes predicts a fair price for homes it has
**never seen**: typical error **6.0%** (median), versus 22% for the naive "average price in the ZIP" guess.
Vacant land is priced by its own segment and reported separately. *Leakage: Zestimate, rent estimates and $/sqft are never features, duplicate listings never straddle
folds, and every price-based feature is fit on training folds only. Prior list price = the last asking price of a PREVIOUS listing of the same house that ended (sold or taken off market) at least 12 months before the current listing, time-adjusted with the ZIP's Zillow home-value index; it is not leakage because no event from the current listing (its price, price changes, or sale) is ever used, so it is information a buyer could have seen a year before this listing went up.*

**0:30 – UH grad mode (25 s).** Enter income $65,000, savings $30,000; in the sidebar type the rate
Maya was quoted (we use 6.5% as an example input — the app never assumes a rate). The app lists affordable
fair or underpriced homes near UH. Top pick: **16323 Hunting Dog Ct, Missouri City TX 77489** — 3 bd / 2.0 ba, 1,649 sqft,
listed at **$199,900** vs a fair price of **$249,433** (-19.9%), below its 80% fair range
($214,688–$290,990) → 🟢 UNDERPRICED.

**0:55 – Why + true cost (20 s).** The SHAP waterfall shows which factors drive the fair price. True monthly cost:
**$1,745/mo** (P&I $1,137 + tax $366 + insurance $167
+ PMI $75) = 32% of her income.

**1:15 – Contrast (10 s).** Compare: 8714 Shady Vista Ln, Houston TX 77028 at $217,000 is ⚪ FAIR (-0.0%); 9442 Rippling Fields Dr, Houston TX 77064 at $217,900
is 🔴 OVERPRICED (+19.3%) — $1,902/mo for a house the model values at $182,689.

**1:25 – Close (5 s).** Fair price, honest range, the reason why, and the real monthly bill — in one Houston tool.
