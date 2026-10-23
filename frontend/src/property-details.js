export const ESSENTIAL_TYPES = [
  { key: 'school', label: 'School', icon: '▤' },
  { key: 'hospital', label: 'Hospital', icon: '✚' },
  { key: 'supermarket', label: 'Groceries', icon: '▧' },
  { key: 'pharmacy', label: 'Pharmacy', icon: '✥' },
]
export function distanceKm(a, b) {
  const rad = Math.PI / 180,
    dlat = (b.lat - a.lat) * rad,
    dlng = (b.lng - a.lng) * rad
  const s =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dlng / 2) ** 2
  return 6371 * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(Math.max(0, 1 - s)))
}
export function nearestEssentials(home, facilities) {
  return ESSENTIAL_TYPES.map((type) => {
    let nearest = null
    for (const facility of facilities) {
      if (facility.category !== type.key) continue
      const distance = distanceKm(home, facility)
      if (!nearest || distance < nearest.distance)
        nearest = { ...facility, distance }
    }
    return { ...type, place: nearest }
  })
}
export function mockPrice(building) {
  let seed = 2166136261
  for (const c of building.id)
    seed = Math.imul(seed ^ c.charCodeAt(0), 16777619) >>> 0
  const base =
    { house: 260000, apartment: 850000, factory: 1400000, school: 2200000 }[
      building.type
    ] || 260000
  const price =
    Math.round((base + (seed % Math.round(base * 0.9))) / 5000) * 5000
  return {
    price,
    low: Math.round((price * 0.9) / 5000) * 5000,
    high: Math.round((price * 1.1) / 5000) * 5000,
  }
}
export function createPropertyDetails() {
  const $ = (id) => document.getElementById(id)
  const money = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
  let facilities,
    loading,
    current = null,
    disposed = false
  function render(building) {
    const estimates = mockPrice(building)
    $('suggested-price').textContent = money.format(estimates.price)
    $('price-range').textContent =
      `Demo range ${money.format(estimates.low)} – ${money.format(estimates.high)}`
    $('essentials-status').textContent = facilities
      ? 'OSM · straight-line'
      : 'Loading mapped places…'
    const list = $('nearby-essentials')
    list.replaceChildren()
    for (const { label, icon, place } of nearestEssentials(
      building,
      facilities || [],
    )) {
      const row = document.createElement(place ? 'a' : 'div')
      row.className = 'essential-row'
      if (place) {
        row.href = place.sourceUrl
        row.target = '_blank'
        row.rel = 'noopener noreferrer'
        row.title = 'View mapped amenity in OpenStreetMap'
      }
      const glyph = document.createElement('span'),
        text = document.createElement('div'),
        category = document.createElement('small'),
        name = document.createElement('b'),
        distance = document.createElement('span')
      glyph.className = 'essential-icon'
      glyph.textContent = icon
      glyph.setAttribute('aria-hidden', 'true')
      category.textContent = label
      name.textContent =
        place?.name ||
        (facilities ? 'No mapped place in this dataset' : 'Finding nearby…')
      distance.className = 'essential-distance'
      distance.textContent = place
        ? place.distance < 1
          ? `${Math.round(place.distance * 1000)} m ↗`
          : `${place.distance.toFixed(1)} km ↗`
        : '—'
      text.append(category, name)
      row.append(glyph, text, distance)
      list.append(row)
    }
  }
  return {
    show(building) {
      current = building
      render(building)
      if (!loading)
        loading = fetch('/data/houston-essentials.json')
          .then((r) => {
            if (!r.ok) throw new Error('Unavailable')
            return r.json()
          })
          .then((data) => {
            facilities = data.facilities
            if (!disposed && current) render(current)
          })
          .catch(() => {
            if (!disposed) {
              $('essentials-status').textContent = 'Data unavailable'
              document.querySelectorAll('.essential-row b').forEach((el) => {
                el.textContent = 'Mapped data unavailable'
              })
            }
          })
    },
    destroy() {
      disposed = true
      current = null
    },
  }
}
