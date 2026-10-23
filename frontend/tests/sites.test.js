import test from 'node:test'
import assert from 'node:assert/strict'
import { selectedSite, areaLabel } from '../src/sites.js'
import { PLAY_BOUNDS, inside } from '../src/geo.js'
import { demoBuildings } from './fixtures/demo-buildings.js'

test('selection is identical when drawn in either direction', () => {
  const a = [-95.39, 29.77],
    b = [-95.389, 29.771]
  const forward = selectedSite(a, b),
    reverse = selectedSite(b, a)
  assert.deepEqual(forward, reverse)
  assert.ok(forward.area > 10000 && forward.area < 12000)
  assert.deepEqual(
    forward.geometry.coordinates[0][0],
    forward.geometry.coordinates[0].at(-1),
  )
})
test('selection cannot extend outside the playable square', () => {
  const site = selectedSite([-97, 28], [-94, 31])
  for (const corner of site.geometry.coordinates[0])
    assert.ok(inside(...corner))
  assert.deepEqual(site.geometry.coordinates[0][0], PLAY_BOUNDS[0])
  assert.deepEqual(site.geometry.coordinates[0][2], PLAY_BOUNDS[1])
})
test('single point is a zero-area selection and small sites retain useful units', () => {
  assert.equal(selectedSite([-95.39, 29.77], [-95.39, 29.77]).area, 0)
  assert.equal(areaLabel(450), '450 m²')
  assert.equal(areaLabel(15000), '1.50 ha')
})
test('demo homes have unique stable IDs and progressive detail tiers', () => {
  assert.equal(demoBuildings.length, 5760)
  assert.equal(
    new Set(demoBuildings.map((b) => b.id)).size,
    demoBuildings.length,
  )
  assert.ok(demoBuildings.every((b) => inside(b.lng, b.lat)))
  assert.ok(demoBuildings.filter((b) => b.tier === 0).length < 250)
  assert.ok(demoBuildings.filter((b) => b.tier <= 1).length < 1500)
})
