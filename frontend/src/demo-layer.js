import { homeById } from './buildings.js'
import { prepareHousing } from './housing-data.js'
import { createPinReveal } from './pin-reveal.js'
let displayedHomes = []
let activeFilter = () => true
export function filterHistoricalHomes(map, predicate) {
  activeFilter = predicate
  map
    .getSource('demo-houses')
    .setData(homesGeoJSON(displayedHomes.filter(activeFilter)))
  reveal?.refresh()
}
let reveal
export function refreshHouseReveal() {
  reveal?.refresh()
}
export function destroyHouseReveal() {
  reveal?.destroy()
}
export async function loadHistoricalHomes(map, fetchImpl = fetch) {
  const response = await fetchImpl('/houston-homes.json', {
    signal: AbortSignal.timeout(15000),
  })
  if (!response.ok)
    throw new Error('Historical housing snapshot could not be loaded')
  const data = prepareHousing(await response.json())
  homeById.clear()
  for (const home of data.homes) homeById.set(home.id, home)
  displayedHomes = data.homes
  map.getSource('demo-houses').setData(homesGeoJSON(displayedHomes))
  reveal?.refresh()
  return data
}
function homesGeoJSON(homes) {
  return {
    type: 'FeatureCollection',
    features: homes.map((b) => ({
      type: 'Feature',
      id: b.id,
      properties: { id: b.id, tier: b.tier, mapped: !!b.existing },
      geometry: { type: 'Point', coordinates: [b.lng, b.lat] },
    })),
  }
}
export const DEMO_LAYERS = ['demo-overview', 'demo-neighborhood', 'demo-detail']
// One raster sprite shared by every GPU-rendered pin. No per-house DOM.
function pinImage(selected = false) {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 84
  const ctx = canvas.getContext('2d')
  ctx.scale(2, 2)
  ctx.fillStyle = '#29483225'
  ctx.beginPath()
  ctx.ellipse(16, 40, 5, 1.5, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.moveTo(16, 39)
  ctx.bezierCurveTo(12, 32, 2, 24, 2, 15)
  ctx.bezierCurveTo(2, -2, 30, -2, 30, 15)
  ctx.bezierCurveTo(30, 24, 20, 32, 16, 39)
  ctx.closePath()
  ctx.fillStyle = selected ? '#427650' : '#7b9870'
  ctx.fill()
  ctx.strokeStyle = selected ? '#ecc66f' : '#fffef6'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 1.7
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(9, 15)
  ctx.lineTo(16, 9)
  ctx.lineTo(23, 15)
  ctx.moveTo(11, 14)
  ctx.lineTo(11, 22)
  ctx.lineTo(21, 22)
  ctx.lineTo(21, 14)
  ctx.moveTo(15, 22)
  ctx.lineTo(15, 18)
  ctx.lineTo(18, 18)
  ctx.lineTo(18, 22)
  ctx.stroke()
  return ctx.getImageData(0, 0, 64, 84)
}
export function installDemoLayer(map, beforeId) {
  map.addImage('house-pin', pinImage(), { pixelRatio: 2 })
  map.addImage('house-pin-selected', pinImage(true), { pixelRatio: 2 })
  map.addSource('demo-houses', {
    type: 'geojson',
    promoteId: 'id',
    data: homesGeoJSON(displayedHomes),
  })
  const levels = [
    [12.25, 14, 0],
    [14, 16, 1],
    [16, 24, 2],
  ]
  levels.forEach(([minzoom, maxzoom, tier], i) =>
    map.addLayer(
      {
        id: DEMO_LAYERS[i],
        type: 'symbol',
        source: 'demo-houses',
        minzoom,
        maxzoom,
        filter: ['<=', ['get', 'tier'], tier],
        layout: {
          'icon-image': 'house-pin',
          'icon-anchor': 'bottom',
          'icon-size': [
            'interpolate',
            ['linear'],
            ['zoom'],
            12,
            0.65,
            16,
            0.82,
            18,
            1,
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
        paint: {
          'icon-opacity': [
            'case',
            ['boolean', ['feature-state', 'arriving'], false],
            0,
            ['boolean', ['feature-state', 'revealed'], false],
            0.92,
            0,
          ],
        },
      },
      beforeId,
    ),
  )
  map.addLayer(
    {
      id: 'demo-selected',
      type: 'symbol',
      source: 'demo-houses',
      minzoom: 12.25,
      filter: ['==', ['get', 'id'], ''],
      layout: {
        'icon-image': 'house-pin-selected',
        'icon-anchor': 'bottom',
        'icon-size': 1.12,
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
      },
    },
    beforeId,
  )
  reveal = createPinReveal(map, pinImage(), () =>
    displayedHomes.filter(activeFilter),
  )
}
export function setDemoVisibility(map, visible) {
  reveal?.setEnabled(visible)
  for (const id of [...DEMO_LAYERS, 'demo-selected'])
    if (map.getLayer(id))
      map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
}
