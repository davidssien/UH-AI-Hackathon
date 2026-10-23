import { PLAY_BOUNDS } from './geo.js'
export const emptyCollection = () => ({
  type: 'FeatureCollection',
  features: [],
})
export function selectedSite(first, last) {
  const [[west, south], [east, north]] = PLAY_BOUNDS
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
  const w = clamp(Math.min(first[0], last[0]), west, east),
    e = clamp(Math.max(first[0], last[0]), west, east)
  const s = clamp(Math.min(first[1], last[1]), south, north),
    n = clamp(Math.max(first[1], last[1]), south, north)
  const width = (e - w) * 111320 * Math.cos((((s + n) / 2) * Math.PI) / 180),
    height = (n - s) * 110574
  return {
    center: [(w + e) / 2, (s + n) / 2],
    area: width * height,
    width,
    height,
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [w, s],
          [e, s],
          [e, n],
          [w, n],
          [w, s],
        ],
      ],
    },
  }
}
export function areaLabel(area) {
  if (area >= 1e6) return `${(area / 1e6).toFixed(2)} km²`
  if (area >= 10000) return `${(area / 10000).toFixed(2)} ha`
  return `${Math.round(area).toLocaleString()} m²`
}
export function installSiteLayers(map, beforeId) {
  map.addSource('proposed-sites', { type: 'geojson', data: emptyCollection() })
  map.addSource('draft-site', { type: 'geojson', data: emptyCollection() })
  map.addLayer(
    {
      id: 'proposed-sites-fill',
      source: 'proposed-sites',
      type: 'fill',
      paint: { 'fill-color': '#6b9568', 'fill-opacity': 0.2 },
    },
    beforeId,
  )
  map.addLayer(
    {
      id: 'proposed-sites-line',
      source: 'proposed-sites',
      type: 'line',
      paint: { 'line-color': '#4a7851', 'line-width': 2 },
    },
    beforeId,
  )
  map.addLayer(
    {
      id: 'draft-site-fill',
      source: 'draft-site',
      type: 'fill',
      paint: { 'fill-color': '#8eb677', 'fill-opacity': 0.3 },
    },
    beforeId,
  )
  map.addLayer(
    {
      id: 'draft-site-line',
      source: 'draft-site',
      type: 'line',
      paint: {
        'line-color': '#4e804f',
        'line-width': 2,
        'line-dasharray': [3, 2],
      },
    },
    beforeId,
  )
}
export function highlightSite(map, id) {
  if (!map.getLayer('proposed-sites-fill')) return
  map.setPaintProperty('proposed-sites-fill', 'fill-opacity', [
    'case',
    ['==', ['get', 'id'], id || ''],
    0.38,
    0.16,
  ])
  map.setPaintProperty('proposed-sites-line', 'line-width', [
    'case',
    ['==', ['get', 'id'], id || ''],
    3,
    1.5,
  ])
}
