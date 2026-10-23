// Real Houston listings scored by our model (public/data/listings.json, exported from artifacts/ by
// src/export_frontend.py). Fair price is an out-of-fold estimate: the model never saw that home.
//
// Map look follows PermitWatch: dark basemap, glowing deal-colored markers. Zoomed out they are glowing dots;
// zoomed in each home becomes an icon of its residence type, tinted by deal.
export const LISTING_LAYER = 'listings-points'
export const LISTING_LAYERS = [
  'listings-glow',
  'listings-points',
  'listings-icons',
]
export const ICON_MIN_ZOOM = 12.5

/** Card / panel colors (light UI). */
export const DEAL_COLORS = {
  UNDERPRICED: '#0ca30c',
  FAIR: '#8c8c8c',
  OVERPRICED: '#d03b3b',
}
/** Map colors, brighter for the dark basemap. */
export const MAP_COLORS = {
  UNDERPRICED: '#34d399',
  FAIR: '#cbd5e1',
  OVERPRICED: '#fb7185',
}
export const DEAL_LABELS = {
  UNDERPRICED: 'Underpriced',
  FAIR: 'Fair price',
  OVERPRICED: 'Overpriced',
}

/** Residence types in the data, with their map icon. */
export const RESIDENCE_TYPES = [
  { key: 'SINGLE_FAMILY', label: 'Single-family house' },
  { key: 'TOWNHOUSE', label: 'Townhouse' },
  { key: 'CONDO', label: 'Condo / apartment' },
  { key: 'MULTI_FAMILY', label: 'Multi-family' },
  { key: 'MANUFACTURED', label: 'Manufactured home' },
]

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
      properties: { id: l.id, deal: l.deal, list: l.list, kind: l.homeType },
    })),
  }
}

const dealColor = (colors) => [
  'match',
  ['get', 'deal'],
  'UNDERPRICED',
  colors.UNDERPRICED,
  'OVERPRICED',
  colors.OVERPRICED,
  colors.FAIR,
]

/** Draw one residence-type glyph (white on transparent) into a 2D context of size s. */
export function drawResidence(ctx, kind, s) {
  const u = s / 16
  ctx.fillStyle = '#ffffff'
  const roof = (x0, x1, base, peak) => {
    ctx.beginPath()
    ctx.moveTo(x0 * u, base * u)
    ctx.lineTo(((x0 + x1) / 2) * u, peak * u)
    ctx.lineTo(x1 * u, base * u)
    ctx.closePath()
    ctx.fill()
  }
  const hole = (x, y, w, h) => ctx.clearRect(x * u, y * u, w * u, h * u)
  switch (kind) {
    case 'TOWNHOUSE':
      roof(1, 8.5, 7, 2.5)
      roof(7.5, 15, 7, 2.5)
      ctx.fillRect(2 * u, 7 * u, 12 * u, 7.5 * u)
      hole(7.6, 7, 0.8, 7.5)
      hole(3.8, 10.5, 2, 4)
      hole(10.2, 10.5, 2, 4)
      break
    case 'CONDO':
      ctx.fillRect(4 * u, 1.5 * u, 8 * u, 13 * u)
      for (const y of [3, 6, 9]) for (const x of [5.5, 9]) hole(x, y, 1.6, 1.6)
      hole(7, 11.8, 2, 2.7)
      break
    case 'MULTI_FAMILY':
      roof(0.5, 15.5, 6, 2)
      ctx.fillRect(1.5 * u, 6 * u, 13 * u, 8.5 * u)
      for (const x of [3, 6.2, 9.4, 12.2]) hole(x, 7.8, 1.4, 1.6)
      hole(3, 11, 2, 3.5)
      hole(11, 11, 2, 3.5)
      break
    case 'MANUFACTURED':
      ctx.fillRect(0.8 * u, 5 * u, 14.4 * u, 6.5 * u)
      hole(3, 6.6, 2.2, 2)
      hole(6.8, 6.6, 2.2, 2)
      hole(11, 6.6, 2.2, 4.9)
      ctx.beginPath()
      ctx.arc(4.5 * u, 12.6 * u, 1.6 * u, 0, Math.PI * 2)
      ctx.arc(11 * u, 12.6 * u, 1.6 * u, 0, Math.PI * 2)
      ctx.fill()
      break
    default: // SINGLE_FAMILY and anything unknown: a classic house
      roof(1, 15, 7.5, 1.5)
      ctx.fillRect(3 * u, 7.5 * u, 10 * u, 7 * u)
      hole(6.8, 10, 2.4, 4.5)
      hole(4.3, 8.8, 1.6, 1.6)
  }
}

/** Register SDF icons (tintable by deal color) for every residence type. */
export function addResidenceIcons(map) {
  const s = 64
  for (const { key } of [...RESIDENCE_TYPES, { key: 'OTHER' }]) {
    const name = `res-${key}`
    if (map.hasImage(name)) continue
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = s
    const ctx = canvas.getContext('2d')
    if (!ctx) continue
    drawResidence(ctx, key, s)
    map.addImage(name, ctx.getImageData(0, 0, s, s), {
      sdf: true,
      pixelRatio: 2,
    })
  }
}

/** Small data-URL swatch of a residence icon in a given color (for the map key). */
export function residenceSwatch(kind, color = '#e5e7eb', size = 32) {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''
  drawResidence(ctx, kind, size)
  ctx.globalCompositeOperation = 'source-in'
  ctx.fillStyle = color
  ctx.fillRect(0, 0, size, size)
  return canvas.toDataURL()
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
  addResidenceIcons(map)
  const before = map.getLayer('outside-gray') ? 'outside-gray' : undefined
  // Soft glow under every home (PermitWatch-style halo).
  map.addLayer(
    {
      id: 'listings-glow',
      type: 'circle',
      source: 'listings',
      paint: {
        'circle-color': dealColor(MAP_COLORS),
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          4,
          13,
          9,
          17,
          18,
        ],
        'circle-blur': 1,
        'circle-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          0.35,
          14,
          0.45,
        ],
      },
    },
    before,
  )
  // Zoomed out: glowing dots.
  map.addLayer(
    {
      id: LISTING_LAYER,
      type: 'circle',
      source: 'listings',
      maxzoom: ICON_MIN_ZOOM,
      paint: {
        'circle-color': dealColor(MAP_COLORS),
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          1.8,
          12.5,
          3.6,
        ],
        'circle-stroke-color': '#0b0f14',
        'circle-stroke-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          0,
          12,
          0.8,
        ],
        'circle-opacity': 0.95,
      },
    },
    before,
  )
  // Zoomed in: residence-type icons tinted by deal.
  map.addLayer(
    {
      id: 'listings-icons',
      type: 'symbol',
      source: 'listings',
      minzoom: ICON_MIN_ZOOM,
      layout: {
        'icon-image': [
          'match',
          ['get', 'kind'],
          ...RESIDENCE_TYPES.flatMap(({ key }) => [key, `res-${key}`]),
          'res-OTHER',
        ],
        'icon-size': [
          'interpolate',
          ['linear'],
          ['zoom'],
          12.5,
          0.55,
          15,
          0.8,
          18,
          1.15,
        ],
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
      },
      paint: {
        'icon-color': dealColor(MAP_COLORS),
        'icon-halo-color': '#0b0f14',
        'icon-halo-width': 1.4,
      },
    },
    before,
  )
  return listings
}

/** PermitWatch-style map key: deal colors (glowing dots) + residence-type icons. */
export function renderMapKey(container) {
  if (!container) return
  container.replaceChildren()
  const title = document.createElement('p')
  title.className = 'key-title'
  title.textContent = 'Homes for sale'
  container.append(title)
  const list = document.createElement('ul')
  for (const deal of ['UNDERPRICED', 'FAIR', 'OVERPRICED']) {
    const li = document.createElement('li')
    const dot = document.createElement('span')
    dot.className = 'key-dot'
    dot.style.background = MAP_COLORS[deal]
    dot.style.boxShadow = `0 0 8px ${MAP_COLORS[deal]}`
    li.append(dot, document.createTextNode(DEAL_LABELS[deal]))
    list.append(li)
  }
  const sep = document.createElement('li')
  sep.className = 'key-sep'
  sep.setAttribute('aria-hidden', 'true')
  list.append(sep)
  for (const { key, label } of RESIDENCE_TYPES) {
    const li = document.createElement('li')
    const img = document.createElement('img')
    img.className = 'key-icon'
    img.alt = ''
    img.src = residenceSwatch(key)
    li.append(img, document.createTextNode(label))
    list.append(li)
  }
  const note = document.createElement('li')
  note.className = 'key-note'
  note.textContent = 'Icons appear as you zoom in'
  list.append(note)
  container.append(list)
  container.hidden = false
}
