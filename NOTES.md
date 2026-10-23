# NOTES
- Setup: see SETUP_REPORT.md. LGBM n_jobs=12 (24 is 40x slower). CatBoost CPU default (GPU 20x slower on small data, eats all VRAM).
- transformers pinned 4.57.6 (DeBERTa diverges on 5.x). TabPFN token in .env (gitignored).
- Demo runs (prefix d_) were on california housing / imdb; archived before contest.
- GO: put files in data/, edit config.yaml, then: python src/make_folds.py --force (once; demo folds still on disk).
- NLP: group_by_length removed (reorders predict output). eval bs = train bs (VRAM spill = 10x slower).

## Houston (FINAL_PROMPT.md) — 2026-10-23
- Data: Kaggle mohamedalmansop/houston-housing-market-2024-clean-dataset (properties_clean_v2.csv, 25,922 rows, no creds needed). No streetAddress -> CV groups = lat/lon 5dp (20,668 groups, max 66 = builder communities).
- Kaggle "clean" file is median-imputed: lot CONDO=3.9775 / SFR=6050.484 / TOWNHOUSE=1869.5, LOT yearBuilt=2001.5, zestimate=376400 where has_zestimate=0 -> all set NaN (logs/prep.log). Lot < 100 = acres.
- daysOnZillow excluded (market reaction, unknown for a new home). 102 exact dups dropped -> 25,820 rows.
- Pipeline: src/prep.py -> src/make_folds.py (frozen) -> src/exp.py (one experiment) -> src/promote.py (artifacts + smoke). eval.py is the only scorer.
- model.pkl is a gzip pickle. Streamlit Cloud: app/requirements.txt + packages.txt (libgomp1).
- 2026-10-23 teammate data merged (data/houston-housing-pipeline @89ca2ba). SOURCE=teammate; their lot_sqft is all blank (units unknown) -> filled from Light JSON explicit units (19,895 rows). 122 exact dups (all fields but ids) dropped -> 25,800 rows. Folds rebuilt; rebased rows R_*.
- External (homes): census (no home value) REVERT 2/5; census_median_home_value passes keep rule by +0.0008 (5/5) but NOT adopted (ZIP price proxy, gain within noise; teammate flagged needs approval); zhvi REVERT. No flood file delivered -> app shows no flood context.
- Spatial CV row for "all" (S1) is from the raw-data run; homes spatial CV (S3_homes) is current.
- Heavy JSON (600 MB zip, 6.7 GB JSON) now used — user-approved for priceHistory/description/schools (not in Light). src/heavy.py streams it with ijson; leakage filter applied at extraction. TX is non-disclosure: Sold events have null price -> prior features = has/count/years-since-sale only.
- Prior list price (user-approved w/ conditions): last asking price of a PREVIOUS listing episode that ended (Sold/Listing removed) >= 12 months before current listing date; ZHVI 5y-change adjusted. Never current-listing events.
- Homes target switched to log(price/livingArea) (N2, kept on RMSE rule; MdAPE ~flat). Text = bge-small, PCA32 in-fold. Photos = CLIP ViT-B-32 on first 3 photos (data/img cache, ~2.5 GB).
- sentence-transformers install bumped transformers to 5.x -> re-pinned 4.57.6 (DeBERTa note above).
