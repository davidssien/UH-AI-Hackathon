# Greater Houston Development Simulator

A map-first planning sandbox using Vite, vanilla JavaScript, Tailwind CSS v4 and MapLibre GL JS. OpenFreeMap Positron provides the basemap.

## Run

Run from the repository root (`uh-ai-hackathon/`):

```sh
npm install
npm run dev
```

```sh
npm run build
npm test
```

Start in Explore mode. Select **Build**, then drag a rectangle or tap two opposite corners. Drag its corners to reshape it, use the + edge handles to add vertices, or drag inside to move the whole boundary. Undo reverses edits; focused corners support arrow keys (Shift for larger steps) and Delete. Choose a house, apartment, factory or school to develop the highlighted site. Existing proposals offer Edit boundary to revise and save their shape. The footprint persists and can be selected again. Escape cancels a draft and returns to exploring. **Explore** takes you to historical Houston property records; **World** returns to the region. **Layers** controls planning districts and historical property pins.

The root `vite.config.js` serves `frontend/` and builds to `frontend/dist/`. npm dependencies and formatter configuration also live at the repository root. File paths below are relative to `frontend/`.

## Rendering and interaction

- `src/main.js`: map lifecycle, cached proposal markers, UI and optional GIS data.
- `src/geo.js`: playable square, dynamic minimum zoom, viewport-aware limits and elastic camera compression.
- `src/buildings.js`: live home catalog, initially empty. `src/housing-data.js` validates and adapts the bundled historical housing snapshot. Generated houses remain only in `tests/fixtures/demo-buildings.js` as a legacy test fixture; they are never seeded into the live map or used as a loading-error fallback.
- `src/demo-layer.js`: shared traditional pin sprite and GPU-rendered GeoJSON symbol layers. A sparse sample appears near zoom 12.25, more at 14, and every home at 16. `src/pin-reveal.js` uses one transient canvas for inflate-and-wobble arrivals, then hands off to GPU symbols; reduced motion is respected. Existing homes do not allocate individual DOM markers.
- `src/site-selector.js`: polygon boundary editor with draggable corners, vertex insertion, whole-shape translation, Undo, keyboard editing and pointer capture. `src/polygon.js` validates geometry and prevents self-intersections.
- `src/sites.js`: selected-area geometry, area measurement, persistent footprint layers and selection highlights.
- `src/location.js`: map-center context from loaded OpenMapTiles place and road features. Region, nearby locality, neighborhood and street labels follow zoom. Full addresses are shown only if a feature supplies actual address fields; ordinary basemap tiles often lack these, so street context and coordinates remain the fallback. Near a historical property, city context uses its recorded city; locality labels describe proximity, not verified municipal containment.
- `tests/`: viewport coverage, elastic resistance, selection bounds, area calculations and demo dataset checks.

The camera transform compresses the rendered camera before drawing; MapLibre retains the requested gesture transform. One ease returns the camera after movement settles. Rotation and pitch remain disabled so viewport limits are exact. Resize updates the minimum zoom. Proposal markers are cached and never recreated while moving. No animation changes a MapLibre-owned marker transform.

City of Houston Super Neighborhood layer 3 is loaded as optional GeoJSON with timeout/fallback. These are planning districts, not zoning. Basemap and GIS require internet access. Proposals last for the current browser session; cost and feasibility analysis are deferred. Search uses Photon geocoding only while typing or submitting a query; map panning does not send geocoding requests. Complete house coverage still requires a more comprehensive building/parcel dataset.

Marker architecture and worker setup reference [PermitWatch Houston](https://github.com/Abbas9x/permitwatch-houston).

## Historical housing data

`public/houston-homes.json` bundles **25,922 historical property observations**
from the other UH hackathon repository's cleaned housing CSV. The browser loads
this display artifact once; there is no backend requirement, raw-data read at
startup, or live link to another local checkout. Refresh the snapshot explicitly:

```sh
python3 app/export_housing.py --input /path/to/other-repo/data/houses_clean.csv --addresses-artifact artifacts/houses_scored.parquet
```

The address enrichment step requires PyArrow (`python3 -m pip install pyarrow==24.0.0`), already listed in the app dependencies. The browser needs no Python packages. Omitting `--addresses-artifact` intentionally exports property facts without street addresses. The exporter preserves row IDs, original
coordinates, recorded property type, city, ZIP, bedrooms, bathrooms, floor/lot
area, and year built. Missing values display as Unknown; source prices,
Zestimates, rent estimates, owner information, and training-only features are
excluded. The snapshot records the source CSV and address artifact SHA-256 checksums and source attribution.
Source: [Kaggle Houston Housing Market 2024 clean dataset](https://www.kaggle.com/datasets/mohamedalmansop/houston-housing-market-2024-clean-dataset).
Public redistribution rights are unverified; this integration is an internal
local prototype, with no deployment or publishing performed.

There are **20,679 distinct coordinate pairs**; **6,435 observations** share
coordinates with another observation. Pins stay at their source coordinates;
select a shared pin and choose the observation from the details card dropdown.
The catalog includes source property types such as vacant lots and labels them
as recorded. **Seven records** are outside the existing playable map boundary;
they remain in the snapshot but cannot be explored within that boundary. Counts
refer to observations, not independently verified unique homes.

These are historical observations, not verified current sale listings. The
cleaned CSV has no street address, photo, or observation date columns. Recorded street addresses are joined from `artifacts/houses_scored.parquet` only when row ID, Zillow property ID, coordinates, and ZIP all agree with the CSV. **25,799 properties** have a street address; **123** show Address unavailable (122 absent from the scored artifact, one containing only city/ZIP). Property card titles and overlapping-record choices use these addresses. The city/ZIP-only label is not treated as a street address. No missing addresses or valuations are invented. Saved model estimates attach to 22,764 matching observations; the remaining
3,158 show Estimate unavailable. Proposed buildings retain explicitly labeled mock pricing. The existing Parquet artifacts
are unchanged. See `app/HISTORICAL_HOUSING.md` for the implementation scope.

The older `public/data/sugar-land-homes.json` OSM dataset remains in the repository
but is no longer loaded as the active property catalog.

## Search and property details

Click the location heading to search. Local suggestions cover well-known places and recorded house addresses, when available; online autocomplete uses [Photon](https://github.com/komoot/photon/blob/master/docs/api-v1.md) with a 450 ms debounce, cancellation, and a session cache. Suggestions are filtered to the playable Greater Houston square (including Sugar Land), and destinations are checked again before navigation. Submitting an unselected query resolves without location bias so an outside city is rejected instead of silently matching a similarly named Houston street. Outside destinations trigger a one-second red flash/shake and an Out of scope notification. Arrow keys select a suggestion, Enter goes there, and Escape closes search. Online search depends on the public Photon demo service; local suggestions remain available if it fails.

Historical property details show recorded facts and saved model estimates where available. Proposed development details retain a stable, generated **mock suggested price and range**, clearly labeled as demo pricing. Neither is a live appraisal or current listing price. Nearby schools, hospitals, groceries and pharmacies use `public/data/houston-essentials.json`: 387 unique OSM amenities retrieved through Photon on 2026-10-23. This is a capped, name-search sample focused on Houston and Sugar Land, not an exhaustive amenity inventory. The card reports the nearest record in the sample by haversine distance, with links to original OSM records; distances are straight-line, not route distances or travel times. Data © OpenStreetMap contributors, ODbL 1.0. `scripts/import-houston-essentials.mjs` records reproducible query URLs and raw-response SHA-256 checksums.

Double-click a proposed icon or mapped home to center and zoom into it. Basemap POI icons also support this. Selecting a proposed boundary shows on-map Edit, Move and Delete controls. Drag Move to open its editor and translate it; Save boundary commits the result. Draft boundaries have their own Move and Delete controls. Deleting a built boundary removes its development and updates the session count. The move control also supports arrow keys (Shift for 10 m steps) while editing. Reduced-motion preferences disable screen shake and camera animation.

### Full street-address search

Numbered addresses now use the [US Census Geocoder](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html), with address suggestions after a 750 ms pause and direct resolution on Enter. A street-only query defaults to Houston, TX; include city and ZIP for addresses in other Greater Houston communities. Each resolved coordinate still passes the playable-area check. Census uses address-range interpolation, so its location may not be an exact rooftop. Named-place search continues to use Photon. Requests are cached in memory, cancelled when replaced, and time out; there is no saved address history. Census's documented JSONP format enables static browser clients without a backend API key or a development-only proxy.

The first search row is **Current address**, describing the current map center (not device GPS). It uses the last searched address or a nearby mapped house record, then Photon reverse geocoding as a fallback. When no nearby recorded house address exists, it shows the center coordinates and says no address is mapped. Selecting the row returns to that map point. A resolved searched address stays in the title while zoomed in near its destination.

## Saved fair-price features

The Deals dock button opens view summaries, verdict filters and a maximum
historical asking price. Filters operate on the existing animated house pins;
there is no second circle layer. Original addresses, shared-location record
choices, Build tools, search and amenities remain available. Reset filters to
restore every historical observation, including unscored ones.

`public/model-listings.json` contains upstream exported results from commit
`e3e78e036edc27927e5831d30cd91e9d3864a3d3` in davidssien/UH-AI-Hackathon.
`src/listings.js` validates and matches scores using row IDs, coordinates rounded
to six decimal places, home type and recorded address. Original coordinates and
addresses are preserved. This display snapshot is separate from training data
and the older local model artifacts. The export identifies model
`BL3:N4_img+R_all`, with reported median absolute percentage error 5.65% and
calibrated interval coverage 80.2%; these metrics have not been rerun here.

Scored cards include fair price, the calibrated 80% interval, historical asking
price, verdict and top SHAP factors. Monthly costs and offer drafts are
collapsible. The mortgage rate starts blank and requires the user's quote;
other calculator assumptions are editable examples. The 30-year estimate includes
principal/interest, property tax, insurance and assumed PMI, and explicitly
excludes HOA, maintenance, flood insurance, utilities and closing costs.
Offers stay local and can be copied; no offer is sent. These records do not
establish current availability. No deployment was performed. See
`app/MODEL_INTEGRATION.md` for scope and verification.
