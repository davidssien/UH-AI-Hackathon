import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { rowToListing, listingsGeoJSON } from '../src/listings.js'

const data = JSON.parse(
  readFileSync(new URL('../public/data/listings.json', import.meta.url)),
)

test('listings export has metadata, fields and in-range model values', () => {
  assert.equal(data.meta.fields.length, data.rows[0].length)
  assert.ok(data.rows.length > 20000)
  const l = rowToListing(data.meta.fields, data.rows[0])
  assert.ok(l.listing && l.id.startsWith('L'))
  for (const row of data.rows.slice(0, 2000)) {
    const x = rowToListing(data.meta.fields, row)
    assert.ok(x.p10 <= x.fair && x.fair <= x.p90, x.id)
    assert.ok(['UNDERPRICED', 'FAIR', 'OVERPRICED'].includes(x.deal))
    assert.ok(Math.abs(x.lat - 29.8) < 1 && Math.abs(x.lng + 95.4) < 1.2)
  }
})

test('listings GeoJSON keeps ids and deal labels', () => {
  const ls = data.rows.slice(0, 5).map((r) => rowToListing(data.meta.fields, r))
  const g = listingsGeoJSON(ls)
  assert.equal(g.features.length, 5)
  assert.equal(g.features[0].properties.id, ls[0].id)
})
