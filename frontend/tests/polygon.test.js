import test from 'node:test'
import assert from 'node:assert/strict'
import {
  polygonSite,
  validPolygon,
  midpoint,
  translatePolygon,
  pointInPolygon,
} from '../src/polygon.js'
import { selectedSite } from '../src/sites.js'
import { inside } from '../src/geo.js'
import { readFileSync } from 'node:fs'
const rect = [
  [-95.6, 29.65],
  [-95.599, 29.65],
  [-95.599, 29.651],
  [-95.6, 29.651],
]
test('inserting a midpoint preserves area and moving it reshapes the site', () => {
  const original = polygonSite(rect),
    extended = [rect[0], midpoint(rect[0], rect[1]), ...rect.slice(1)]
  assert.ok(validPolygon(extended))
  assert.ok(Math.abs(polygonSite(extended).area - original.area) < 0.001)
  const reshaped = extended.map((p) => [...p])
  reshaped[1][1] -= 0.0003
  assert.ok(validPolygon(reshaped))
  assert.ok(polygonSite(reshaped).area > original.area)
})
test('self-crossing, collapsed and out-of-bounds boundaries are rejected', () => {
  assert.equal(validPolygon([rect[0], rect[2], rect[1], rect[3]]), false)
  assert.equal(validPolygon([rect[0], rect[0], rect[1]]), false)
  assert.equal(validPolygon([[0, 0], rect[1], rect[2]]), false)
})
test('polygon area and center agree with rectangle measurements', () => {
  const p = polygonSite(rect),
    r = selectedSite(rect[0], rect[2])
  assert.ok(Math.abs(p.area - r.area) < 1)
  assert.ok(pointInPolygon(p.center, rect))
  assert.deepEqual(
    p.geometry.coordinates[0][0],
    p.geometry.coordinates[0].at(-1),
  )
})
test('moving an entire site preserves its shape and stays within the play area', () => {
  const moved = translatePolygon(rect, [100, 100])
  assert.ok(moved.every((p) => inside(...p)))
  assert.ok(validPolygon(moved))
  assert.ok(
    Math.abs(moved[1][0] - moved[0][0] - (rect[1][0] - rect[0][0])) < 1e-10,
  )
})
test('Sugar Land import contains real stable OSM links and no fabricated addresses', () => {
  const data = JSON.parse(
    readFileSync(
      new URL('../public/data/sugar-land-homes.json', import.meta.url),
    ),
  )
  assert.equal(data.homes.length, 1111)
  assert.equal(new Set(data.homes.map((h) => h.id)).size, 1111)
  assert.equal(data.homes.filter((h) => h.address).length, 443)
  assert.ok(
    data.homes.every(
      (h) =>
        h.existing &&
        !h.demo &&
        h.sourceUrl === `https://www.openstreetmap.org/way/${h.osmId}` &&
        inside(h.lng, h.lat),
    ),
  )
})
