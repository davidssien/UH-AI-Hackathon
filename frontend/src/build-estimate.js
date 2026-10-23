// Price estimate for a house the user BUILDS on the map (no listing exists yet): comps from the model.
// Takes the 10 nearest scored homes of the same residence type, uses their model fair price per sqft, and applies it
// to the new home's living area. Living area defaults from the drawn lot (Houston median: house ≈ 35% of lot).
const SQM_TO_SQFT = 10.7639

function miles(a, b) {
  const rad = Math.PI / 180
  const dlat = (b.lat - a.lat) * rad
  const dlng = (b.lng - a.lng) * rad
  const s =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dlng / 2) ** 2
  return 3958.8 * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s))
}

const quantile = (sorted, q) =>
  sorted[
    Math.min(
      sorted.length - 1,
      Math.max(0, Math.round(q * (sorted.length - 1))),
    )
  ]

/** Living area for a new house from the drawn site area (m²): 35% of the lot, clamped to 900–4,500 sqft. */
export function livingAreaFromSite(siteAreaM2) {
  const lot = siteAreaM2 * SQM_TO_SQFT
  return Math.round(Math.min(4500, Math.max(900, lot * 0.35)))
}

/**
 * @param listings scored homes ({lat, lng, sqft, fair, homeType})
 * @param at {lat, lng}; sqft living area; kind residence type; exclude optional id (for honest tests)
 * @returns {price, low, high, comps, radiusMiles} or null
 */
export function estimateBuild(
  listings,
  at,
  sqft,
  kind = 'SINGLE_FAMILY',
  k = 10,
  exclude = null,
) {
  const near = []
  for (const l of listings) {
    if (l.id === exclude || !l.sqft || l.homeType !== kind) continue
    near.push([miles(at, l), l.fair / l.sqft])
  }
  if (near.length < 3) return null
  near.sort((a, b) => a[0] - b[0])
  const top = near.slice(0, k)
  const ppsf = top.map((x) => x[1]).sort((a, b) => a - b)
  const round = (v) => Math.round(v / 1000) * 1000
  const price = quantile(ppsf, 0.5) * sqft
  // 80% range calibrated on 3,000 leave-one-out builds at real listings: asking price fell within 0.80x–1.22x.
  return {
    price: round(price),
    low: round(price * 0.8),
    high: round(price * 1.22),
    comps: top.length,
    radiusMiles: top[top.length - 1][0],
  }
}
