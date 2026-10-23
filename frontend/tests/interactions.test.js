import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { inSearchScope, localSuggestions, photonPlace } from '../src/search.js'
import {
  distanceKm,
  nearestEssentials,
  mockPrice,
} from '../src/property-details.js'

test('search permits Greater Houston destinations and rejects outside coordinates', () => {
  assert.ok(inSearchScope({ lng: -95.3698, lat: 29.7604 }))
  assert.ok(inSearchScope({ lng: -95.6349, lat: 29.6197 }))
  assert.equal(inSearchScope({ lng: -96.797, lat: 32.777 }), false)
  assert.equal(inSearchScope({ lng: NaN, lat: 29.7 }), false)
  assert.equal(inSearchScope({ lng: -95.3 }), false)
  assert.ok(localSuggestions('sugar').every(inSearchScope))
  assert.equal(localSuggestions('dallas').length, 0)
  assert.ok(localSuggestions('university')[0].label.includes('University'))
})
test('geocoder address suggestions retain coordinates and supplied address', () => {
  const p = photonPlace({
    properties: { housenumber: '123', street: 'Main Street', city: 'Houston' },
    geometry: { coordinates: [-95.3, 29.7] },
  })
  assert.equal(p.label, '123 Main Street')
  assert.equal(p.zoom, 18)
  assert.ok(inSearchScope(p))
})
test('nearest amenities use geography and category rather than data ordering', () => {
  const home = { lng: -95.3, lat: 29.7 }
  const rows = nearestEssentials(home, [
    { category: 'school', name: 'Far', lng: -95.6, lat: 29.7 },
    { category: 'hospital', name: 'Hospital', lng: -95.31, lat: 29.7 },
    { category: 'school', name: 'Near', lng: -95.301, lat: 29.7 },
  ])
  assert.equal(rows[0].place.name, 'Near')
  assert.equal(rows[1].place.name, 'Hospital')
  assert.equal(rows[2].place, null)
  assert.equal(distanceKm(home, home), 0)
  assert.ok(
    Math.abs(distanceKm(home, { lng: -95.3, lat: 30.7 }) - 111.195) < 0.01,
  )
})
test('mock prices remain stable and have a consistent illustrative range', () => {
  const b = { id: 'home-1', type: 'house' }
  const result = mockPrice(b)
  assert.deepEqual(result, mockPrice(b))
  assert.ok(result.low < result.price && result.price < result.high)
  assert.ok(result.price >= 260000)
})
test('amenity sample has valid scope, provenance and original record links', () => {
  const data = JSON.parse(
    readFileSync(
      new URL('../public/data/houston-essentials.json', import.meta.url),
    ),
  )
  assert.ok(data.facilities.length > 0)
  assert.ok(data.sources.every((s) => s.sha256.length === 64))
  assert.ok(
    data.facilities.every(
      (f) =>
        inSearchScope(f) &&
        /^https:\/\/www.openstreetmap.org\/(node|way|relation)\/\d+$/.test(
          f.sourceUrl,
        ),
    ),
  )
  assert.equal(
    new Set(data.facilities.map((f) => f.id)).size,
    data.facilities.length,
  )
})
