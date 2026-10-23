# Numbers quoted in the pitch (copied from artifacts/metrics.json — do not edit by hand)

Headline = median absolute % error (MdAPE). MAE is listed for completeness; a few multi-million-dollar listings inflate it.

- **Homes: median pricing error 6.01%** on 22,764 homes the model never saw (out-of-fold); naive ZIP-median baseline 22.06%
- Homes: half of predictions within ±6.0% of list price; RMSE(log) 0.1566; MAE $67,276
- Homes: P10–P90 fair range covers 80.0% of list prices (target 80%)
- Vacant land (separate segment, 3,036 lots): MdAPE 27.8% — land is much harder to price from listing data
- All 25,800 listings combined: MdAPE 6.78%
- Zestimate vs list price (reference, not apples-to-apples — Zillow sees the listing): MdAPE 3.15% on 21,322 homes; ours on the same homes 5.99%
- Deal labels (homes): FAIR 20,162, OVERPRICED 1,311, UNDERPRICED 1,291
- Spatial CV (whole ZIPs held out): homes MdAPE 13.39%; all MdAPE 14.35%
- Demo house 1 (underpriced): 16323 Hunting Dog Ct, Missouri City TX 77489, list $199,900, fair $249,433 (-19.9%), monthly $1,745
- Demo house 2 (fair): 8714 Shady Vista Ln, Houston TX 77028, list $217,000, fair $217,035 (-0.0%), monthly $1,894
- Demo house 3 (overpriced): 9442 Rippling Fields Dr, Houston TX 77064, list $217,900, fair $182,689 (+19.3%), monthly $1,902
- Prior list price feature: Prior list price = the last asking price of a PREVIOUS listing of the same house that ended (sold or taken off market) at least 12 months before the current listing, time-adjusted with the ZIP's Zillow home-value index; it is not leakage because no event from the current listing (its price, price changes, or sale) is ever used, so it is information a buyer could have seen a year before this listing went up.
- Monthly-cost example inputs: rate 6.5% (user-entered example, not a market quote), 10% down, tax 2.2%, insurance 1.0%/yr, PMI 0.5%
