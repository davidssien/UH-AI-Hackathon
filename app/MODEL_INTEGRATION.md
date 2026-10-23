# Model features in the existing map

User direction: preserve the current building/pin interface, historical catalog,
and street-address titles while retaining the features from upstream commit
`e3e78e036edc27927e5831d30cd91e9d3864a3d3`.

## Design and approach

Attach the upstream exported scores to the existing 25,922 observations by row
identity, rounded coordinates, home type, and matching recorded address. Reuse
the current GPU pin layer, source coordinates, reveal animation, and duplicate
record chooser. Do not introduce the upstream circle layer or a second catalog.
Keep Deals closed initially; collapse monthly costs and offer drafting to keep
the map uncluttered. Preserve historical labels and unavailable estimates.

Alternative considered: install the upstream circle layer independently. Rejected
because it duplicates houses and recreates the clutter the user asked to remove.

## Implementation and checks

- Exported results: `frontend/public/model-listings.json`, copied from
  upstream `frontend/public/data/listings.json` at the commit above, with JSON formatting normalized. Its location
  avoids this checkout's broad `data/` ignore rule without editing root config.
  These are display results, never training features or live listings.
- `listings.js`: validate rows before mutation, then attach only identity-checked
  matches; retain all unmatched historical observations without estimates.
- `deals.js`: user-selected verdict/maximum historical asking price, view summary,
  and navigation to scored properties; filter the existing pins.
- `model-card.js`: reuse upstream verdict, interval, SHAP, financing and draft
  offer features. Interest starts blank and requires the user's quote. All
  financing assumptions must be valid; down payment cannot exceed 100%.
- `property-details.js`: show saved estimates and preserve calculator/draft state
  across asynchronous amenity loading. Historical facts/addresses remain intact.
- Test matching, mismatches, malformed rows, missing estimates, median/filtering,
  financing edge cases, loading failures, and shared-coordinate selection.
- Run frontend tests, build and formatting. Run exporter tests. Attempt Python
  smoke and live preview; record dependency/sandbox blockers accurately.

## Constraints and provenance

No changes to model, artifacts, folds, training sources, or root config. Existing
local edits remain. No commits, pushes, or deployment were performed during implementation. Git pull was attempted and
failed because `.git/FETCH_HEAD` is read-only.

The snapshot identifies model `BL3:N4_img+R_all`, median absolute percentage error
5.65%, and calibrated interval coverage 80.2%. These are export metadata, not a
new validation run or metrics for the older local artifacts. All 22,764 rows
match existing properties; 3,158 observations remain without connected scores.
Redistribution permissions and current availability remain unverified.


## Verification completed

- Frontend suite: `npm test` passed (eight test files).
- Production build: `npm run build` passed; Vite reports its bundle-size warning.
- Formatting: `npm run format:check` passed.
- Exporter suite: `python3 -m unittest app/test_export_housing.py` passed (three tests).
- Whitespace: `git diff --check` passed. Protected paths remain unchanged.
- Independent code review found fractional input rejection and an empty offer
  becoming a copyable $0 draft. Both were reproduced by a failing DOM/event
  regression test, corrected, and verified passing. Loading failure and pin
  filtering/reset behavior also have regression coverage.
- Live preview remains unverified: Vite cannot bind `127.0.0.1:5173` (EPERM).
- Python smoke remains blocked by missing NumPy; no SMOKE PASS is claimed.
- No commits, pushes, or deployment were performed at the implementation handoff.

Source Git blob: `13a10ee38531484fa605a697c68b45333545eecc`.
Access date: 2026-10-23.
Local display snapshot SHA-256: `9a90766c20b5790040a08306717b5dfb0482a55624fa78f0fba2a5a4df800abe`.


## Publication preparation

The user subsequently requested publication to davidssien/UH-AI-Hackathon and
explicitly waived the Python smoke test on 2026-10-23. The final pre-push checks
passed: 40 frontend tests, production build, formatting, three exporter tests,
and whitespace verification. The obsolete upstream listing test was adapted to
the joined historical-catalog API. Publication is based on upstream main
`055587cfc56ce6d310b35be497e199e422396ffa`, preserving the newer model/runtime
and export changes while replacing the dark/clustered map presentation with the
user's preferred existing pin UI. Local Git metadata remains read-only, so
publication uses a separate temporary checkout. Python smoke remains unverified.
