import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { prepareHousing } from '../src/housing-data.js'
import { attachScores } from '../src/listings.js'

// The historical catalog now owns identity and pin rendering. Keep coverage of
// the upstream model export while checking the joined-catalog contract.
test('saved model results cover the historical catalog without duplicate pins', () => {
  const homes = prepareHousing(
    JSON.parse(
      readFileSync(new URL('../public/houston-homes.json', import.meta.url)),
    ),
  ).homes
  const data = JSON.parse(
    readFileSync(new URL('../public/model-listings.json', import.meta.url)),
  )
  assert.equal(data.meta.fields.length, data.rows[0].length)
  assert.deepEqual(attachScores(homes, data), { matched: 22764, unmatched: 0 })
  assert.equal(new Set(homes.map((h) => h.id)).size, 25922)
  for (const h of homes.filter((h) => h.listing)) {
    assert.ok(h.p10 <= h.fair && h.fair <= h.p90)
    assert.ok(['UNDERPRICED', 'FAIR', 'OVERPRICED'].includes(h.deal))
    assert.ok(Math.abs(h.lat - 29.8) < 1 && Math.abs(h.lng + 95.4) < 1.2)
  }
})
