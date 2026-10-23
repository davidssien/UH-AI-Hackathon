# FINAL PROMPT — UH AI Hackathon, Challenge 2: Houston Housing Market Intelligence

Replaces all previous instructions (HACKATHON_MASTER.md Sections 4–5, HOUSTON_GO.md).

## 1. Context

- Event: one-day hackathon, judged by humans (no leaderboard). Our track: predict Houston home prices and build a useful AI housing tool.
- Hardware: Windows + WSL2 Ubuntu. RTX 5070 Ti (16 GB, sm_120). Core Ultra 7 270K. Env and pipeline already in `~/hack` and tested. LightGBM on CPU (12 threads), CatBoost on CPU, XGBoost/TabPFN/TabICL/AutoGluon/HF on GPU.
- Control: I control you from my laptop via Remote Control. Teammates use ChatGPT/Codex and push data files to our private repo `github.com/Abbas9x/uh-ai-hackathon`.

What the judges reward (every action must serve one):

1. A trained model at the core, with a Before → After metrics table.
2. No target leakage, explicitly checked and stated.
3. Per-house SHAP explanations.
4. A useful Houston tool: fair-price / deal finder plus a true monthly cost calculator, built around a persona (UH grad buying a first home).
5. A clean live demo.

Golden rule: always keep a working end-to-end version. Promote a new model to `artifacts/` only if it beats the current one AND the app smoke test passes.

## 2. Operating rules (always)

- Messages: ≤ 5 lines. Speak only at milestones (MVP READY, each promotion, new teammate data integrated, unfixable errors). Otherwise work silently.
- Logs: all training output goes to `logs/<id>.log`; read only `tail -n 20`. Never print more than 10 rows of any dataframe.
- Experiments: each ≤ 15 min. Run long jobs (AutoGluon, Optuna, full TabPFN) in the background with nohup. Only one GPU job at a time.
- Errors: fix once. If it fails again, log it in NOTES.md and move on. Skip any external source that fails twice.
- Git: commit every kept change; push after every promotion. Never commit `logs/`. Never delete or modify files teammates pushed in `data/`.
- Never invent numbers. Every metric comes from `src/eval.py`.
- Interest rates: never state a current mortgage rate as fact. Rates are user inputs.

## 3. Data sources (priority order)

1. Main dataset (official, per the organizers' brief): Kaggle via kagglehub, `mohamedalmansop/houston-housing-market-2024-clean-dataset`. Download to `data/raw/`. If it needs credentials, STOP and tell me to add `~/.kaggle/kaggle.json`. (The organizers' Google Drive folder contains only the challenge brief, not data files.)
2. `data/houses_clean.csv` from teammates: the same Kaggle data, cleaned. It keeps every row and adds `row_id`, `lot_sqft`, `has_issue`, `issue_note`; ZIP is a 5-digit string; there is no imputation. Switch to it when it arrives (see the teammate data loop below).

Start immediately with the best source available now. Do not wait for teammates.
On load, print the columns, dtypes, row count, NaN %, and `price` describe. Map the real column names in `config.yaml`; never assume them.

Teammate data loop:

- Run `git pull` every ~20 min, and immediately whenever I say "PULL".
- When `houses_clean.csv` arrives:
  - validate it (row count matches `data/cleaning_log.md`, ZIPs are 5-digit strings, no price-derived columns)
  - switch to it, rebuild `folds.csv` once
  - rerun the current best config as the new baseline row, labeled "rebased on teammate-cleaned data"
- When `data/external/*.csv` arrive (census_zip, flood_zip, zhvi_zip, redfin_zip; super_neighborhood keyed by row_id):
  - validate (one row per key, 5-digit ZIP strings, blanks not zeros, no price columns)
  - left-join on ZIP (or row_id)
  - test each file as its own experiment with the keep/revert rule
  - reject any column with |Spearman| > 0.95 vs price
- Optional raw JSON, only after the MVP: `datadetective08/houston-housing-market-2024` Light version (~143 MB), for schools, hoaFee/resoFacts, and description. Never the 6.7 GB Heavy version.

## 4. Leakage firewall (stated in the pitch)

- Never use as features: `zestimate`, `rentZestimate`, `pricePerSquareFoot`, any tax assessed/appraised value, price history containing the current list price, any house-level sale or list price, Redfin median sale price, and anything computed from `price`.
- Benchmark only: keep `zestimate` aside as a benchmark.
- Auto-check every feature set: flag any feature with |Spearman| > 0.95 vs price and drop it unless I approve.
- Dedupe exact duplicates. Build groups from `streetAddress+zipcode` (fallback: lat/lon rounded to 5 decimals) and use GroupKFold(5, seed 42). Save `folds.csv` and freeze it (rebuild only on a data source switch).
- Fold-only target statistics: all target-based features (KNN comps, ZIP encodings) are fitted on training-fold rows only and applied to that fold's validation rows. For final full-data models and the app, fit on all rows.

## 5. Cleaning (if not already done by teammates)

- Lot size: convert to `lot_sqft` (acres × 43,560; unknown units → NaN).
- Impossible values → NaN (log the counts, never drop rows): yearBuilt < 1800 or > 2025, livingArea < 200, beds/baths < 0, price ≤ 0 (drop only these from training).
- Categoricals: `homeType` as a category, with rare (< 30 rows) → OTHER. ZIP as a 5-digit string category.
- Target: `y = log1p(price)`.
- Extreme prices: train with and without the top/bottom 0.5% as one experiment, always validated on untouched folds.

## 6. Metrics (`src/eval.py` is the only scorer; update it now, then freeze it)

- Primary: RMSE on log1p(price). Lower is better.
- Dollar scale (after expm1): MAE ($), Median Absolute % Error (MdAPE), and R².
- Benchmark row: Zestimate vs list price on the same rows (MAE $, MdAPE), labeled "reference, not apples-to-apples".
- Robustness (once, near the end): spatial CV via GroupKFold by ZIP. Report it honestly.
- Keep rule: mean CV improves by > 1 fold-std, OR the change wins ≥ 4 of 5 folds.
- Logging: every experiment appends to `results.tsv` and `pitch/before_after.md` (step, change, RMSE_log, MAE_$, MdAPE, R², kept).

## 7. Model ladder (one logged experiment per step)

1. B0: median price by ZIP (naive baseline row).
2. B1: LightGBM on raw features (beds, baths, livingArea, lot_sqft, homeType, yearBuilt, lat, lon, zip).
3. F1 Houston hubs: Haversine miles to Downtown (29.7604, -95.3698), Texas Medical Center (29.7079, -95.3978), Galleria (29.7399, -95.4617), Energy Corridor (29.7848, -95.6265), and University of Houston (29.7199, -95.3422). Add the min distance and the bearing from Downtown.
4. F2: lat/lon rotated by 15°, 30°, 45°, and 60°.
5. F3 comps, fold-only:
   - BallTree (haversine) on training-fold rows.
   - For k = 5, 10, 25: median and mean log(price/livingArea) of the nearest neighbors (excluding self), plus the distance to the k-th neighbor.
   - `comp_value = exp(median_log_ppsf_k10) × livingArea`.
6. F4 ZIP encodings, fold-only: smoothed (m = 20) mean log price-per-sqft and count per ZIP and per ZIP×homeType.
7. F5 structure: age, log area, sqft per bedroom, baths per bedroom, lot/living ratio, new-construction flag (age ≤ 2).
8. F6 external: teammates' files, one experiment each (Section 3). If teammates haven't delivered census data within ~2 hours of starting, pull ACS 5-year 2023 yourself:
   - B19013_001E income, B25064_001E rent, B25001_001E housing units, by ZCTA
   - cache it to `data/external/`
   - never use B25077 home value as a feature without the 0.95 check
9. F7 raw JSON (post-MVP): school rating mean/min, HOA fee, and description keyword flags ("renovated", "new roof", "granite", "pool", "never flooded", "high and dry", "as-is", "investor", "fixer").
10. Model zoo on the best features:
    - LightGBM, CatBoost, XGBoost (GPU), TabPFN (GPU; subsample or chunk on OOM), TabICL.
    - AutoGluon `extreme` in the background (time_limit 3600, using our folds; fall back to `best_quality` on OOM).
11. Optuna: top 2 GBDTs, 3 folds, timeout 900 s, then refit on 5 folds.
12. Blend: hill climbing (repeats allowed) vs Ridge stacking on OOF; pick by CV. Then 3-seed averaging.

## 8. Artifacts (MVP right after B1; overwrite on each promotion; total < 90 MB, committed to git)

- `artifacts/model.pkl`: LightGBM refit on all data, which the app uses for speed and SHAP. Use the blend only if it beats LightGBM by > 2% MAE; LightGBM SHAP still explains it.
- `artifacts/featurizer.pkl` + `src/featurize_new.py`: turn any new home (lat/lon or ZIP centroid, beds, baths, sqft, lot, type, year) into features, using full-data comps, ZIP stats, hubs, and external joins.
- `artifacts/houses_scored.parquet`: per listing:
  - id, address, lat/lon, zip, type, beds, baths, area, list price
  - OOF predicted price (honest), and P10/P90 from LightGBM quantile models (alpha 0.1/0.9, same features and folds)
  - gap % = (list − pred)/pred
  - deal label: UNDERPRICED if list < P10 AND gap ≤ −10%; OVERPRICED if list > P90 AND gap ≥ +10%; else FAIR
  - zestimate
- `artifacts/shap_values.parquet`: top 10 contributions per house in % terms, `(exp(φ)−1)×100`, with an approximate $ impact. Also `shap_summary.png`.
- `artifacts/metrics.json`: final metrics, the benchmark, and spatial CV.

## 9. Streamlit app (`app/streamlit_app.py`; loads only `artifacts/`, no training at startup, uses `st.cache_resource`)

1. Map explorer:
   - Listings colored by deal label (pydeck or folium).
   - Filters: price, beds, type, ZIP, deals-only.
   - Selecting a house shows the list price vs the P10–P90 fair range, the deal badge, a SHAP waterfall, and the Zestimate.
2. What's it worth? A form that returns the predicted price, the range, and the SHAP explanation.
3. True Monthly Cost:
   - Inputs: price, down payment % (default 10), interest rate (editable user input), term (30 y), property tax (default 2.2%, slider 1.8–3.0%), annual home/windstorm insurance (editable), HOA (prefilled if known), optional flood insurance, PMI % if down payment < 20%.
   - Output: P&I + tax + insurance + HOA + PMI = total monthly.
   - Affordability vs income: green ≤ 30%, yellow ≤ 36%, red above.
   - Flood context: if flood_zip exists, show the ZIP's flood-claim rate as context.
4. Persona mode: "UH grad, income $X, savings $Y" shows the top 10 affordable UNDERPRICED/FAIR homes, ranked by gap %.
5. Model card: before/after table, Zestimate benchmark, leakage firewall, spatial CV, feature importance.

Testing and deployment:

- Smoke test after each promotion: import the app headless, predict 3 houses, compute 1 monthly cost.
- Deploy: add `requirements_app.txt` and make the repo Streamlit Community Cloud-ready. When the MVP works, tell me the deploy steps (I click deploy).

## 10. Pitch assets (`pitch/`, regenerated on each promotion)

- `before_after.md`: the table from B0 → final, with the % error reduction.
- PNGs: predicted vs actual; residual map by ZIP; SHAP summary; MAE before/after bar chart; a deal-finder example card.
- `demo_script.md`: a 90-second UH-grad persona story using 3 real houses from our data (one flagged underpriced, with the monthly cost shown); one sentence on leakage prevention and fold-only comps.
- `numbers.md`: every number quoted in the pitch, copied from `metrics.json`.

## 11. Teammates

Create `AGENTS.md` (for Codex) and `TEAMMATE.md` now, then push. Contents:

- how to clone and run the app (`pip install -r requirements_app.txt`, `streamlit run app/streamlit_app.py`)
- teammates may edit only `app/`, `pitch/`, and `data/` (data uploads via `git add -f`)
- never edit `src/`, `artifacts/`, `folds.csv`, or `eval.py`
- always `git pull` before working

If a teammate commit touches forbidden folders, revert it and tell me.

## 12. Priority order (strict)

1. MVP gate: data → leakage firewall → folds → eval.py → B0, B1 → artifacts → app runs locally → AGENTS.md/TEAMMATE.md → push. Report "MVP READY" + metrics.
2. F1–F5 one at a time with keep/revert, then promote.
3. Quantile range + deal labels + SHAP + monthly cost + persona mode fully working, then promote and push.
4. Pitch assets.
5. Teammate data integration (whenever it lands, interrupt this list), F6–F7, model zoo, AutoGluon, Optuna, blend, seeds. Promote only on real improvement plus a passing smoke test.
6. Spatial-CV robustness and final polish.
7. Loop on step 5 until I say stop.

## 13. Commands I may send

- PULL: git pull now and integrate any new teammate data.
- STATUS: best metrics + last 3 experiments, ≤ 5 lines.
- FREEZE: no new promotions, bug fixes only, final push, final numbers in ≤ 5 lines. Also self-freeze 45 minutes before the contest ends.
- STOP: kill all background jobs.
