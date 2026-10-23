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

Start in Explore mode. Select **Build**, then drag a rectangle or tap two opposite corners. Drag its corners to reshape it, use the + edge handles to add vertices, or drag inside to move the whole boundary. Undo reverses edits; focused corners support arrow keys (Shift for larger steps) and Delete. Choose a house, apartment, factory or school to develop the highlighted site. Existing proposals offer Edit boundary to revise and save their shape. The footprint persists and can be selected again. Escape cancels a draft and returns to exploring. **Explore** takes you to real mapped Sugar Land homes; **World** returns to the region. **Layers** controls planning districts and illustrative houses.

The root `vite.config.js` serves `frontend/` and builds to `frontend/dist/`. npm dependencies and formatter configuration also live at the repository root. File paths below are relative to `frontend/`.

## Rendering and interaction

- `src/main.js`: map lifecycle, cached proposal markers, UI and optional GIS data.
- `src/geo.js`: playable square, dynamic minimum zoom, viewport-aware limits and elastic camera compression.
- `src/buildings.js`: 5,760 deterministic demo houses across 32 neighborhood clusters, across Houston. The four Sugar Land demo clusters are replaced by imported real buildings when the dataset loads. Demo locations elsewhere remain illustrative.
- `src/demo-layer.js`: shared traditional pin sprite and GPU-rendered GeoJSON symbol layers. A sparse sample appears near zoom 12.25, more at 14, and every home at 16. `src/pin-reveal.js` uses one transient canvas for inflate-and-wobble arrivals, then hands off to GPU symbols; reduced motion is respected. Existing homes do not allocate individual DOM markers.
- `src/site-selector.js`: polygon boundary editor with draggable corners, vertex insertion, whole-shape translation, Undo, keyboard editing and pointer capture. `src/polygon.js` validates geometry and prevents self-intersections.
- `src/sites.js`: selected-area geometry, area measurement, persistent footprint layers and selection highlights.
- `src/location.js`: map-center context from loaded OpenMapTiles place and road features. Region, nearby locality, neighborhood and street labels follow zoom. Full addresses are shown only if a feature supplies actual address fields; ordinary basemap tiles often lack these, so street context and coordinates remain the fallback. Locality labels describe proximity, not verified municipal containment.
- `tests/`: viewport coverage, elastic resistance, selection bounds, area calculations and demo dataset checks.

The camera transform compresses the rendered camera before drawing; MapLibre retains the requested gesture transform. One ease returns the camera after movement settles. Rotation and pitch remain disabled so viewport limits are exact. Resize updates the minimum zoom. Proposal markers are cached and never recreated while moving. No animation changes a MapLibre-owned marker transform.

City of Houston Super Neighborhood layer 3 is loaded as optional GeoJSON with timeout/fallback. These are planning districts, not zoning. Basemap and GIS require internet access. Proposals last for the current browser session; cost and feasibility analysis are deferred. Search uses Photon geocoding only while typing or submitting a query; map panning does not send geocoding requests. Complete house coverage still requires a more comprehensive building/parcel dataset.

Marker architecture and worker setup reference [PermitWatch Houston](https://github.com/Abbas9x/permitwatch-houston).

## Sugar Land house data

`public/data/sugar-land-homes.json` contains 1,111 residential building records (443 with recorded addresses) from OpenStreetMap, snapshot 2026-10-23. Pins use the mapped building centers and link directly to their original OSM way. Addresses are presented as recorded, not independently verified. These are community-mapped buildings, not sale listings or a complete inventory. No owner information is collected.

Data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under ODbL 1.0. The dataset retains source, license, scope and timestamp metadata. `scripts/sugar-land.overpassql` contains the reproducible read-only Overpass query; run `node frontend/scripts/import-sugar-land.mjs <raw-response.json>` to convert an exported response. The browser loads the bundled dataset once and does not scrape while panning. Near imported homes, locality context uses their Sugar Land source area; elsewhere locality labels remain proximity-based.

## Search and property details

Click the location heading to search. Local suggestions cover well-known places and recorded Sugar Land addresses; online autocomplete uses [Photon](https://github.com/komoot/photon/blob/master/docs/api-v1.md) with a 450 ms debounce, cancellation, and a session cache. Suggestions are filtered to the playable Greater Houston square (including Sugar Land), and destinations are checked again before navigation. Submitting an unselected query resolves without location bias so an outside city is rejected instead of silently matching a similarly named Houston street. Outside destinations trigger a one-second red flash/shake and an Out of scope notification. Arrow keys select a suggestion, Enter goes there, and Escape closes search. Online search depends on the public Photon demo service; local suggestions remain available if it fails.

House/development details include a stable, generated **mock suggested price and range**, clearly labeled as demo pricing. No price is read from a real property source, and this is not an appraisal or model prediction. Nearby schools, hospitals, groceries and pharmacies use `public/data/houston-essentials.json`: 387 unique OSM amenities retrieved through Photon on 2026-10-23. This is a capped, name-search sample focused on Houston and Sugar Land, not an exhaustive amenity inventory. The card reports the nearest record in the sample by haversine distance, with links to original OSM records; distances are straight-line, not route distances or travel times. Data © OpenStreetMap contributors, ODbL 1.0. `scripts/import-houston-essentials.mjs` records reproducible query URLs and raw-response SHA-256 checksums.

Double-click a proposed icon or mapped home to center and zoom into it. Basemap POI icons also support this. Selecting a proposed boundary shows on-map Edit, Move and Delete controls. Drag Move to open its editor and translate it; Save boundary commits the result. Draft boundaries have their own Move and Delete controls. Deleting a built boundary removes its development and updates the session count. The move control also supports arrow keys (Shift for 10 m steps) while editing. Reduced-motion preferences disable screen shake and camera animation.

### Full street-address search

Numbered addresses now use the [US Census Geocoder](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html), with address suggestions after a 750 ms pause and direct resolution on Enter. A street-only query defaults to Houston, TX; include city and ZIP for addresses in other Greater Houston communities. Each resolved coordinate still passes the playable-area check. Census uses address-range interpolation, so its location may not be an exact rooftop. Named-place search continues to use Photon. Requests are cached in memory, cancelled when replaced, and time out; there is no saved address history. Census's documented JSONP format enables static browser clients without a backend API key or a development-only proxy.

The first search row is **Current address**, describing the current map center (not device GPS). It uses the last searched address or a nearby mapped house record, then Photon reverse geocoding as a fallback. When no nearby recorded house address exists, it shows the center coordinates and says no address is mapped. Selecting the row returns to that map point. A resolved searched address stays in the title while zoomed in near its destination.

## Fair-price model (HomeWatch features)

`public/data/listings.json`: 22,764 real Houston for-sale homes scored by the team's model
(regenerate with `python src/export_frontend.py` in the model repo). Map layer `listings-points`: green underpriced,
gray fair, red overpriced. **Deals** (dock): filter by deal / max price, market summary for the map view, best deals in
view. Clicking a listing shows the out-of-fold fair price (the model never saw that home), calibrated 80% range bar,
top SHAP factors, true monthly cost (interest rate is the user's input) and an offer-letter drafter.
