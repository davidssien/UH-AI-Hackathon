# AGENTS.md (Codex / ChatGPT agents)

Project: UH AI Hackathon, Challenge 2 — Houston home prices + fair-price deal finder + true monthly cost (persona: UH grad buying a first home).

## Setup & run
```bash
git pull
pip install -r requirements_app.txt
streamlit run app/streamlit_app.py
python app/smoke_test.py   # must print SMOKE PASS before you push app changes
```

## Hard rules
- Always `git pull` before working.
- Edit **only** `app/`, `pitch/`, `data/`. Data files are gitignored: `git add -f data/...`.
- **Never edit** `src/`, `artifacts/`, `folds.csv`, `src/eval.py`. Commits touching them are reverted.
- The app loads only `artifacts/` — never train or read raw data at app startup.
- Never state a current mortgage interest rate as fact; rates are user inputs.
- No leakage in data files: no house-level price, Zestimate, rentZestimate, price per sqft, tax assessed/appraised value, or Redfin median sale price. ZIPs as 5-digit strings, blanks (not 0) for missing, one row per key.

## Layout
- `app/streamlit_app.py` UI · `app/core.py` artifact loading/prediction · `app/finance.py` monthly cost
- `artifacts/` model.pkl (gzip pickle), featurizer.pkl, houses_scored.parquet, shap_values.parquet, metrics.json
- `pitch/` before_after.md, numbers.md, demo_script.md, charts
See TEAMMATE.md for data-drop formats.

## Data engineering (from data/houston-housing-pipeline)

### Scope and collaboration
- This repository is shared. Inspect Git status, branches, existing docs and affected code before editing. Preserve unrelated and uncommitted teammate work.
- Housing data engineering belongs on `data/houston-housing-pipeline`; merges into main are coordinated with the ML owner (first merge: 2026-10-23).
- Keep data engineering changes scoped to acquisition, inspection, reproducible cleaning, validation and handoff. Coordinate changes to model code, config and folds with the ML teammate.

### Data integrity
- Preserve source datasets unchanged. Write derived outputs separately; record source URL, access date, version, checksum, license and reproducible commands when acquisition is implemented.
- Never commit secrets or credentials. Check repository limits and team conventions before committing datasets; use Google Drive for large artifacts when appropriate. Do not assume ignored paths are approved storage or safe to publish.
- Establish target, prediction time and split strategy before selecting features. Document target-derived, future-only and otherwise unavailable fields; fit learned preprocessing within training folds.
- Treat demo data and demo folds as unsuitable for Houston modeling until replaced through a coordinated, validated handoff.

### Documentation
- Maintain docs/PROJECT_STATE.md, DATA_PIPELINE.md, DATA_QUALITY.md, DATA_DICTIONARY.md and DATA_HANDOFF.md when data processing changes.
- Distinguish planned, in-progress, blocked and verified work. Use actual evidence; never invent statistics, tests, schema or source provenance.
- Reuse NOTES.md and SETUP_REPORT.md for their existing purposes. Historical setup claims are not current verification.
