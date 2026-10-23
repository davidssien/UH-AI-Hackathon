// Real Houston listings scored by our model (public/data/listings.json, exported from artifacts/ by
// src/export_frontend.py). Fair price is an out-of-fold estimate: the model never saw that home.
export const LISTING_LAYER = 'listings-points'
export const DEAL_COLORS = {
  UNDERPRICED: '#0ca30c',
  FAIR: '#8c8c8c',
  OVERPRICED: '#d03b3b',
}
export const listingById = new Map()
export let listingsMeta = null

export function rowToListing(fields, row) {
  const r = Object.fromEntries(fields.map((f, i) => [f, row[i]]))
  return {
    ...r,
    listing: true,
    homeType: r.type, // SINGLE_FAMILY, CONDO, ... ('type' stays 'house' for the map's TYPES lookups)
    lat: r.lat,
    lng: r.lng,
    type: 'house',
  }
}

export function listingsGeoJSON(listings) {
  return {
    type: 'FeatureCollection',
    features: listings.map((l) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [l.lng, l.lat] },
      properties: { id: l.id, deal: l.deal, list: l.list },
    })),
  }
}

export async function installListings(map) {
  const response = await fetch('/data/listings.json')
  if (!response.ok) throw new Error('Listings unavailable')
  const data = await response.json()
  listingsMeta = data.meta
  listingById.clear()
  const listings = data.rows.map((row) => rowToListing(data.meta.fields, row))
  for (const l of listings) listingById.set(l.id, l)
  if (map.getSource('listings')) return listings
  map.addSource('listings', {
    type: 'geojson',
    data: listingsGeoJSON(listings),
  })
  const before = map.getLayer('outside-gray') ? 'outside-gray' : undefined
  map.addLayer(
    {
      id: LISTING_LAYER,
      type: 'circle',
      source: 'listings',
      paint: {
        'circle-color': [
          'match',
          ['get', 'deal'],
          'UNDERPRICED',
          DEAL_COLORS.UNDERPRICED,
          'OVERPRICED',
          DEAL_COLORS.OVERPRICED,
          DEAL_COLORS.FAIR,
        ],
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          2,
          13,
          4,
          16,
          7,
        ],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          0,
          13,
          1,
        ],
        'circle-opacity': 0.85,
      },
    },
    before,
  )
  return listings
}
