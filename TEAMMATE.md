# Teammate guide — Houston Housing Market Intelligence

## Run the app
```bash
git clone https://github.com/Abbas9x/uh-ai-hackathon.git
cd uh-ai-hackathon
pip install -r requirements_app.txt        # Python 3.11
streamlit run app/streamlit_app.py
```
The app loads only `artifacts/` (no training). Smoke test: `python app/smoke_test.py` → `SMOKE PASS`.

## Rules
- **Always `git pull` before working.**
- You may edit only: `app/`, `pitch/`, `data/`.
- **Never edit** `src/`, `artifacts/`, `folds.csv`, `src/eval.py` (the model pipeline owns these; commits touching them get reverted).
- `data/` is gitignored — upload data files with `git add -f data/<file>`.
- Never put a house-level price, Zestimate, rent Zestimate, $/sqft, tax assessed value, or Redfin median *sale price* in a feature file. Those are leakage.

## Data drops we can use
| file | key | notes |
|---|---|---|
| `data/houses_clean.csv` + `data/cleaning_log.md` | `row_id` | same Kaggle rows, cleaned; ZIP as 5-digit string; `lot_sqft`, `has_issue`, `issue_note`; no imputation; log states the row count |
| `data/external/census_zip.csv` | `zip` | ACS by ZCTA (income, rent, units, ...) |
| `data/external/flood_zip.csv` | `zip` | flood claims / flood-zone share by ZIP (also shown in the app as context) |
| `data/external/zhvi_zip.csv` | `zip` | Zillow ZHVI by ZIP |
| `data/external/redfin_zip.csv` | `zip` | Redfin market stats (no median sale price) |
| `data/external/super_neighborhood.csv` | `row_id` | super-neighborhood per house |

External file rules: one row per key, ZIP as a **5-digit string**, blanks for missing (not 0), no price columns.
