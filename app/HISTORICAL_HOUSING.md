# Historical housing integration

Goal: replace the generated frontend home catalog with the historical records from
`/home/omar/uh-ai-hackathon/data/houses_clean.csv`, retaining the map design.
User authorized frontend edits on 2026-10-23. No commits, pushes, or deployment.

## Design and constraints

Use a bundled display snapshot, generated explicitly before startup. This suits
the existing static Vite app and avoids an extra running API. A Python API was
considered, but would add a server requirement; a direct cross-repository file
link would break on other machines. The browser never reads raw CSV or trains.
Keep source files and `artifacts/` unchanged. Never export source price,
Zestimate, rentZestimate, zpid, or training fields. These are historical records,
not verified active listings. Nulls remain unknown. Keep stable row IDs and exact
coordinates; offer a chooser for colocated observations. Retain out-of-bounds
records in the snapshot and report their count without expanding map boundaries.
Only export recorded property fields; join recorded addresses from the scored artifact after matching row ID, zpid, coordinates and ZIP. Do not invent addresses, images, or prices.
Saved-model pricing is deferred: the local Parquet reader is unavailable and its
installation failed because DNS is restricted. No mock fallback for real records.

## Plan

1. Test and implement `app/export_housing.py`: stdlib CSV-to-JSON display export,
   strict IDs, finite coordinates, missing values, allowlisted fields, checksum
   and attribution. Write `frontend/public/houston-homes.json`.
2. Test and implement `frontend/src/housing-data.js`: validate snapshot, prepare
   pin records, retain IDs, group colocated observations, load once into the
   existing house layer with no generated fallback.
3. Adapt existing selection card and map copy. Add property facts and colocated
   record selector. Historical properties never use mock prices. Preserve
   proposal tools, address search, amenities, and existing pin animation.
4. Run exporter tests, full frontend tests, build, formatting checks, and source
   checksum/export comparison. Review the diff; do not write Git state.

Review focus: duplicates, partial/missing values, failed/malformed snapshot,
shared-coordinate selection, historical versus proposal pricing, locality labels,
and records outside the current playable area.

## Reproduce

```sh
python3 app/export_housing.py --input /path/to/other-repo/data/houses_clean.csv --addresses-artifact artifacts/houses_scored.parquet
npm run dev
```

Address enrichment requires PyArrow 24.0.0 at export time only (listed in requirements_app.txt). Without `--addresses-artifact`, the standard-library exporter intentionally creates a properties-only snapshot. The snapshot is self-contained once generated. Regenerate explicitly after an
approved source update; there is no live synchronization between repositories.
Source: Kaggle Houston Housing Market 2024 clean dataset, as identified in the
other checkout's handoff. Public redistribution rights remain unverified; this
change is for the internal local prototype. Do not infer an unrestricted license.

## Progress and verification

- Implemented: allowlisted display exporter and bundled snapshot; historical-only
  live catalog; original pin presentation; recorded facts; colocated record
  selector; source-based city context; no mock estimates on historical records.
- The snapshot lives at `frontend/public/houston-homes.json`, outside `data/`,
  because the root ignore rule ignores every directory named data. This makes
  the self-contained display artifact visible to ordinary Git review.
- Source CSV SHA-256: `0a9cb290f73284142a595d4e5183ba986dc3c2fe11210ab076bad67598f64856`.
- Actual export: 25,922 observations, 20,679 distinct coordinate pairs, 6,435
  observations sharing coordinates, seven records outside the existing map.
- No edits to artifacts, model code, source CSVs, root configuration, or Git state.
- `git pull` attempted twice; blocked by read-only `.git/FETCH_HEAD`.
- Live Vite/browser verification blocked: sandbox refuses the localhost listener
  with EPERM. `app/smoke_test.py` blocked at its first import: NumPy is absent.
  No SMOKE PASS is claimed. No app runtime/model code changed.
- Saved pricing was deferred in the original integration (now connected as described below). Address fields have now been extracted and
  joined from the existing scored artifact, whose bytes remain unchanged.
  Export and address enrichment happen before startup, never in the browser.

- Legacy generated house fixtures were moved into frontend tests, so loading the
  live catalog does not generate fake house records even in memory.

- Independent review found Explore could open an empty narrow mobile viewport.
  Fixed by selecting an actual in-bounds observation nearest the region center;
  a 390×844 viewport coverage regression test failed before the fix and passed
  afterward. No other actionable findings were reported.

## Address titles

User requested street addresses instead of observation numbers in property card
headings. The bundled snapshot now contains 25,799 recorded addresses joined
from `artifacts/houses_scored.parquet` (SHA-256
`15f56a3fe553d044b19712e949c73e1c9778c6e1fb197ee8e56694f385ca2568`).
All 25,800 artifact rows matched the CSV by row ID, zpid, exact coordinates and
ZIP with zero mismatches. One artifact row contains only city/ZIP, and 122 CSV
rows are absent from that artifact; those 123 retain a null address and display
Address unavailable. No reverse geocoding or guessed addresses are used.

The current environment lacks PyArrow. This snapshot's address columns were
extracted using a temporary local reader, checking Parquet page sizes/counts,
and cross-checked against all CSV identities/coordinates/ZIPs. The committed
exporter uses standard PyArrow for repeatable future enrichment; no custom
Parquet parser or new runtime dependency is included in the application.

Example: row 2085 displays `4040 San Felipe St APT 140, Houston TX 77027`.
Stable observation IDs remain in supporting details and duplicate-location
choices for disambiguation. No house prices or Zillow IDs are exported.


## Saved model integration

The frontend now joins 22,764 saved estimates from the upstream frontend export
to existing historical records, preserving addresses and coordinates. The
original facts-only exporter remains unchanged. The model snapshot is
`frontend/public/model-listings.json`; it is display output, never a training
feature source. See `app/MODEL_INTEGRATION.md` for identity checks, model
version/metrics and UI scope. The remaining 3,158 observations retain an
unavailable-estimate state. No local Parquet artifact was modified.
