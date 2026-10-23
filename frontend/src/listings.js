// Display results from upstream e3e78e0. Never used as training features.
export const DEAL_COLORS = {
  UNDERPRICED: '#0ca30c',
  FAIR: '#8c8c8c',
  OVERPRICED: '#d03b3b',
}
export const listingById = new Map()
export let listingsMeta = null

export function attachScores(homes, data) {
  const required = [
    'id',
    'lng',
    'lat',
    'address',
    'type',
    'list',
    'fair',
    'p10',
    'p90',
    'gap',
    'deal',
    'factors',
  ]
  if (
    !Array.isArray(data?.meta?.fields) ||
    !Array.isArray(data?.rows) ||
    new Set(data.meta.fields).size !== data.meta.fields.length ||
    !required.every((f) => data.meta.fields.includes(f))
  )
    throw new Error('Invalid model snapshot')
  const seen = new Set()
  const rows = data.rows.map((row) => {
    if (!Array.isArray(row) || row.length !== data.meta.fields.length)
      throw new Error('Invalid model row')
    const r = Object.fromEntries(data.meta.fields.map((f, i) => [f, row[i]]))
    if (
      !/^L\d+$/.test(r.id) ||
      seen.has(r.id) ||
      !['lng', 'lat', 'list', 'fair', 'p10', 'p90', 'gap'].every((f) =>
        Number.isFinite(r[f]),
      ) ||
      r.list <= 0 ||
      r.p10 <= 0 ||
      r.p10 > r.fair ||
      r.fair > r.p90 ||
      !Object.hasOwn(DEAL_COLORS, r.deal) ||
      !Array.isArray(r.factors) ||
      !r.factors.every(
        (f) =>
          Array.isArray(f) && typeof f[0] === 'string' && Number.isFinite(f[1]),
      )
    )
      throw new Error('Invalid model values')
    seen.add(r.id)
    return r
  })
  const byRow = new Map(homes.map((h) => [h.rowId, h]))
  const matches = rows
    .map((r) => [byRow.get(Number(r.id.slice(1))), r])
    .filter(
      ([h, r]) =>
        h &&
        Math.abs(h.lng - r.lng) <= 0.00000051 &&
        Math.abs(h.lat - r.lat) <= 0.00000051 &&
        h.homeType === r.type &&
        (!h.address || h.address === r.address),
    )
  for (const [h, r] of matches)
    Object.assign(h, {
      listing: true,
      list: r.list,
      fair: r.fair,
      p10: r.p10,
      p90: r.p90,
      gap: r.gap,
      deal: r.deal,
      factors: r.factors,
      sqft: h.livingArea,
      year: h.yearBuilt,
      url:
        typeof r.url === 'string' &&
        /^https:\/\/(www\.)?zillow\.com\//.test(r.url)
          ? r.url
          : null,
    })
  return { matched: matches.length, unmatched: rows.length - matches.length }
}

export async function loadScores(homes, fetchImpl = fetch) {
  const response = await fetchImpl('/model-listings.json', {
    signal: AbortSignal.timeout(20000),
  })
  if (!response.ok) throw new Error('Saved model estimates unavailable')
  const data = await response.json()
  const result = attachScores(homes, data)
  listingById.clear()
  for (const h of homes) if (h.listing) listingById.set(h.id, h)
  listingsMeta = data.meta
  return result
}
