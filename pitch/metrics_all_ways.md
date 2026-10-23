# Homes metrics, every common way (model `BL2`, out-of-fold; Zestimate = reference, not apples-to-apples)

Clean subset = homes only with list price between $100,000 and $3,018,500 (1st–99th pct). Zestimate is computed by Zillow WITH the listing visible, so it is not a fair competitor.

|                                                          |      n |   MdAPE % |   MAPE % |   within 5 % |   within 10 % |   R² ($) |   R² (log) |   MAPE on log scale % |   mean |log error| x100 |   MAE $ |   median AE $ |
|:---------------------------------------------------------|-------:|----------:|---------:|-------------:|--------------:|---------:|-----------:|----------------------:|------------------------:|--------:|--------------:|
| Ours — all homes                                         | 22,764 |      6    |     9.63 |        43.67 |         69.28 |    0.831 |      0.932 |                  0.73 |                    9.56 |  67,211 |        22,533 |
| Ours — CLEAN subset (homes, top/bottom 1% price dropped) | 22,314 |      5.9  |     9.23 |        44.31 |         70.15 |    0.879 |      0.923 |                  0.7  |                    9.15 |  51,179 |        22,276 |
| Ours — homes with a real Zestimate                       | 21,322 |      5.99 |     9.42 |        43.76 |         69.56 |    0.879 |      0.941 |                  0.71 |                    9.25 |  60,412 |        22,504 |
| Zestimate vs list — homes with a real Zestimate          | 21,322 |      3.15 |     3.5  |        81.79 |         98.89 |    0.988 |      0.992 |                  0.28 |                    3.62 |  20,746 |        11,600 |
| Ours — CLEAN subset ∩ Zestimate rows                     | 20,933 |      5.89 |     9.08 |        44.34 |         70.35 |    0.896 |      0.93  |                  0.69 |                    8.95 |  49,156 |        22,250 |
| Zestimate vs list — CLEAN subset ∩ Zestimate rows        | 20,933 |      3.11 |     3.42 |        83.02 |         99.3  |    0.987 |      0.99  |                  0.27 |                    3.52 |  16,966 |        11,600 |

**What could '4%' mean?** (1) Zestimate vs list price: MAPE / mean |log error| come out ~3.5% — but Zillow computes it after seeing the listing (it tracks the asking price), so it is not a prediction. (2) 'MAPE on log scale' divides log errors by log(price) ≈ 12.8, shrinking errors ~13× (ours < 1%) — not a percentage of price. Honest headline numbers for a model that never sees the price: MdAPE (half of homes within ±X%) and % within 10%.
