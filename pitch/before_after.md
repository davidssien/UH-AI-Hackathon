# Before → After (5-fold GroupKFold CV, out-of-fold, scored by src/eval.py)

Headline metric: **MdAPE** (median absolute % error). MAE is pulled up by a few multi-million-dollar listings.

## Homes (persona model)

Best **BLEND**: MdAPE **6.01%** vs B0 22.06% (73% lower); RMSE_log 0.1566 vs 0.5143; MAE $67,276 vs $215,383.

| step | change | MdAPE % | RMSE_log | MAE $ | R² | kept |
|---|---|---|---|---|---|---|
| B0 | median price by ZIP (naive) | 22.06 | 0.5143 ± 0.0149 | 215,383 | 0.098 | yes |
| F6s (one model) | single all-listings model, scored on homes only | 7.78 | 0.1862 ± 0.0118 | 80,846 | 0.804 | yes |
| SEG-homes | separate homes-only LightGBM (F6s features) | 7.39 | 0.1859 ± 0.0119 | 79,518 | 0.800 | no |
| SEG-homes | homes-only LightGBM + KNN comps (kept on user call: separate home model; MdAPE better, RMSE tie) | 7.25 | 0.1854 ± 0.0137 | 78,241 | 0.803 | yes |
| F7-flags | + listing flags (new build, bank-owned, auction, builder, condo unit) | 7.14 | 0.1837 ± 0.0137 | 77,711 | 0.805 | yes |
| B0 | median price by ZIP (rebased on teammate-cleaned data) | 22.08 | 0.5143 ± 0.0149 | 215,429 | 0.098 | yes |
| REBASE | H3 config, rebased on teammate-cleaned data | 7.19 | 0.1812 ± 0.0122 | 77,856 | 0.803 | yes |
| F6-census | + census (teammate ZIP file) | 7.23 | 0.1808 ± 0.0112 | 77,606 | 0.806 | no |
| F6-censusv | + census median home value (passes keep rule +0.0008, but not adopted: ZIP price proxy, gain within noise) | 7.18 | 0.1804 ± 0.0117 | 77,694 | 0.804 | no |
| F6-zhvi | + zhvi (teammate ZIP file) | 7.21 | 0.1809 ± 0.0117 | 77,150 | 0.810 | no |
| N2-ppsf | target log(price/livingArea) instead of log(price) | 7.22 | 0.1798 ± 0.0117 | 75,615 | 0.838 | yes |
| N1-prior-sale | + prior Sold event (has/count/years since; TX non-disclosure: no sold prices) | 7.21 | 0.1794 ± 0.0110 | 76,228 | 0.835 | yes |
| N5-schools | + school ratings mean/min/max (Heavy JSON) | 7.13 | 0.1786 ± 0.0119 | 76,015 | 0.833 | yes |
| N1b-side | SIDE TEST (needs approval): + past list price >=12 mo old, ZHVI-adjusted [held: passes 5/5, awaiting approval] | 7.01 | 0.1753 ± 0.0119 | 74,752 | 0.832 | no |
| N3-text | + description embeddings (bge-small, PCA32 in-fold) + keyword flags | 6.80 | 0.1742 ± 0.0118 | 73,416 | 0.843 | yes |
| ZOO-tabpfn | TabPFN (GPU, 10k context) on N3 features | 6.62 | 0.1814 ± 0.0113 | 75,051 | 0.820 | no |
| ZOO-tabicl | TabICL (GPU, 10k context) on N3 features | 6.72 | 0.1812 ± 0.0123 | 76,796 | 0.802 | no |
| N1c-prior-list | + prior list price (previous listing ended >=12 mo before current; ZHVI-adjusted) | 6.65 | 0.1707 ± 0.0118 | 72,631 | 0.844 | yes |
| ZOO-tabpfn | TabPFN (GPU, 10k context) on N1c features | 6.51 | 0.1771 ± 0.0111 | 74,667 | 0.815 | no |
| ZOO-xgb | XGBoost (GPU) on N1c features | 6.69 | 0.1728 ± 0.0116 | 73,068 | 0.832 | no |
| OPTUNA-lgbm | LightGBM Optuna params (3-fold, 900s), refit 5 folds | 6.86 | 0.1689 ± 0.0124 | 72,238 | 0.848 | yes |
| ZOO-tabicl | TabICL (GPU) on N1c features | 6.63 | 0.1785 ± 0.0130 | 75,843 | 0.806 | no |
| N4-photos | + CLIP photo embeddings (first 3 photos, PCA32 in-fold) | 6.32 | 0.1652 ± 0.0107 | 70,530 | 0.842 | yes |
| OPTUNA-cat | CatBoost Optuna params, refit 5 folds | 6.73 | 0.1663 ± 0.0085 | 72,301 | 0.834 | no |
| BLEND | hill-climb vs ridge blend of: N1c_plist O_lgbm O_cat Z_xgb2 Z_tabpfn2 Z_tabicl2 | 6.41 | 0.1638 ± 0.0104 | 69,951 | 0.841 | yes |
| N6-tight-comps | + tight comps (<=3 same-type, <=0.25 mi, ±20% sqft; median ppsf + count) | 6.31 | 0.1654 ± 0.0101 | 70,385 | 0.842 | no |
| N7-bge-large | swap text embeddings bge-small -> bge-large (PCA32 in-fold) | 6.28 | 0.1656 ± 0.0105 | 70,560 | 0.840 | no |
| ZOO-cat | CatBoost (Optuna params) + photos | 6.37 | 0.1598 ± 0.0078 | 69,495 | 0.843 | yes |
| ZOO-lgbm | LightGBM (Optuna params) + photos | 6.49 | 0.1620 ± 0.0107 | 70,176 | 0.849 | no |
| ZOO-tabpfn | TabPFN on N4 features (+photos) | 6.21 | 0.1712 ± 0.0085 | 72,198 | 0.823 | no |
| BLEND | hill vs ridge vs lgbm-L2 blend of: N4_img N7_textL O_cat2 O_lgbm2 O_cat Z_xgb2 Z_tabpfn3 Z_tabicl2 | 6.01 | 0.1566 ± 0.0093 | 67,276 | 0.847 | yes |
| FIX2-scrub | N4 with descriptions scrubbed of $ amounts / price-event phrases (re-embedded, kw recomputed) | 6.34 | 0.1655 ± 0.0109 | 70,798 | 0.838 | no |
| FIX4-obj | LightGBM objective l1 on log ppsf (N4c features) | 6.44 | 0.1745 ± 0.0107 | 73,317 | 0.818 | no |
| FIX4-obj | LightGBM objective huber on log ppsf (N4c features) | 6.32 | 0.1640 ± 0.0110 | 70,524 | 0.837 | no |

## Vacant land (separate model)

Best **REBASE**: MdAPE **27.80%** vs B0 57.46% (52% lower); RMSE_log 0.5785 vs 1.2046; MAE $301,085 vs $490,473.

| step | change | MdAPE % | RMSE_log | MAE $ | R² | kept |
|---|---|---|---|---|---|---|
| B0 | median price by ZIP (naive) | 57.46 | 1.2046 ± 0.0498 | 490,473 | -0.027 | yes |
| F6s (one model) | single all-listings model, scored on land only | 27.75 | 0.5949 ± 0.0423 | 308,059 | 0.382 | yes |
| SEG-land | separate land-only LightGBM (F6s features) | 28.76 | 0.6059 ± 0.0416 | 313,975 | 0.350 | no |
| SEG-land | land-only LightGBM + KNN land comps (log price) | 29.33 | 0.6151 ± 0.0456 | 319,981 | 0.336 | no |
| F7c (one model) | all-listings model + comps, scored on land | 27.73 | 0.6041 ± 0.0453 | 321,182 | 0.342 | no |
| B0 | median price by ZIP (rebased on teammate-cleaned data) | 57.32 | 1.2050 ± 0.0500 | 491,876 | -0.027 | yes |
| REBASE | F6s all-listings model scored on land, rebased | 27.80 | 0.5785 ± 0.0202 | 301,085 | 0.419 | yes |

## All listings

Best **REBASE**: MdAPE **8.67%** vs B0 25.35% (66% lower); RMSE_log 0.2631 vs 0.6521; MAE $106,073 vs $251,044.

| step | change | MdAPE % | RMSE_log | MAE $ | R² | kept |
|---|---|---|---|---|---|---|
| B0 | median price by ZIP (naive) | 25.35 | 0.6521 ± 0.0125 | 251,044 | 0.056 | yes |
| B1 | LightGBM, raw features | 8.94 | 0.2771 ± 0.0068 | 110,086 | 0.618 | yes |
| F1 | + Houston hub distances & bearing | 8.76 | 0.2710 ± 0.0080 | 107,731 | 0.621 | yes |
| F2 | + rotated lat/lon (15/30/45/60°) | 8.75 | 0.2697 ± 0.0072 | 107,455 | 0.612 | no |
| F3 | + fold-only KNN comps (k=5/10/25) | 8.43 | 0.2717 ± 0.0099 | 107,373 | 0.604 | no |
| F3b | + fold-only KNN comps, same home type | 8.36 | 0.2756 ± 0.0105 | 106,972 | 0.619 | no |
| F4 | + fold-only ZIP & ZIP×type encodings (m=20) | 8.79 | 0.2753 ± 0.0072 | 109,391 | 0.607 | no |
| F5 | + structure (age, sqft/bed, baths/bed, lot ratio, new build) | 8.71 | 0.2712 ± 0.0076 | 107,726 | 0.625 | no |
| X1 | F1 + train without top/bottom 0.5% prices | 8.77 | 0.3088 ± 0.0141 | 115,637 | 0.475 | no |
| F1+F2+F5 | hubs + rotations + structure together | 8.66 | 0.2693 ± 0.0076 | 107,564 | 0.617 | yes |
| F1+F2+F5+F3 | + KNN comps on combined set | 8.32 | 0.2698 ± 0.0106 | 106,471 | 0.610 | no |
| ZOO-xgb | XGBoost (GPU) on F6s features | 8.47 | 0.2734 ± 0.0077 | 107,729 | 0.605 | no |
| ZOO-cat | CatBoost (CPU) on F6s features | 8.59 | 0.2671 ± 0.0077 | 106,203 | 0.629 | no |
| REBASE | F6s config (all listings), rebased on teammate-cleaned data | 8.67 | 0.2631 ± 0.0048 | 106,073 | 0.632 | yes |

