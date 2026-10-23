import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as listings from '../src/listings.js'
import { prepareHousing } from '../src/housing-data.js'
import { pricePresentation } from '../src/property-details.js'
import { monthlyCost, suggestedOffer } from '../src/model-card.js'
import { summarize, passes } from '../src/deals.js'

const data = JSON.parse(
  readFileSync(new URL('../public/model-listings.json', import.meta.url)),
)
const housing = () =>
  prepareHousing(
    JSON.parse(
      readFileSync(new URL('../public/houston-homes.json', import.meta.url)),
    ),
  ).homes

test('scores join the original catalog without adding pins or losing addresses', () => {
  const homes = housing()
  const before = homes.map((h) => [h.id, h.lng, h.lat, h.address])
  const result = listings.attachScores(homes, data)
  assert.equal(result.matched, 22764)
  assert.equal(result.unmatched, 0)
  assert.equal(homes.length, 25922)
  assert.deepEqual(
    homes.map((h) => [h.id, h.lng, h.lat, h.address]),
    before,
  )
  assert.equal(homes.filter((h) => h.listing).length, 22764)
  for (const h of homes.filter((h) => h.listing)) {
    assert.ok(h.p10 <= h.fair && h.fair <= h.p90)
    assert.ok(h.historical)
    assert.ok(pricePresentation(h).price > 0)
  }
  assert.equal(pricePresentation(homes.find((h) => !h.listing)).price, null)
})

test('mismatched coordinates never attach another property estimate', () => {
  const homes = housing()
  const copy = structuredClone(data)
  copy.rows = [copy.rows[0]]
  copy.rows[0][1] += 0.1
  assert.deepEqual(listings.attachScores(homes, copy), {
    matched: 0,
    unmatched: 1,
  })
  assert.ok(homes.every((h) => !h.listing))
})

test('malformed scores fail before mutating the catalog', () => {
  const homes = housing()
  const copy = structuredClone(data)
  copy.rows[1][copy.meta.fields.indexOf('fair')] = null
  assert.throws(() => listings.attachScores(homes, copy))
  assert.ok(homes.every((h) => !h.listing))
})

test('deal summary uses the actual median and filters historical asking prices', () => {
  const rows = [
    { list: 100, deal: 'FAIR' },
    { list: 200, deal: 'UNDERPRICED' },
  ]
  assert.equal(summarize(rows).median, 150)
  assert.equal(summarize([]).median, null)
  assert.equal(passes(rows[1], 'UNDERPRICED', 150), false)
  assert.equal(passes(rows[1], 'UNDERPRICED', 200), true)
})

test('monthly cost handles zero interest, cash purchase, and invalid down payments', () => {
  const inputs = { rate: 0, down: 20, tax: 0, ins: 0 }
  assert.equal(monthlyCost(360000, inputs).pi, 800)
  assert.equal(monthlyCost(360000, { ...inputs, down: 100 }).total, 0)
  assert.throws(() => monthlyCost(360000, { ...inputs, down: 101 }))
  assert.throws(() => monthlyCost(360000, { ...inputs, rate: NaN }))
  assert.ok(monthlyCost(300000, { ...inputs, rate: 6.5 }).pi > 1500)
  assert.equal(suggestedOffer({ deal: 'OVERPRICED', fair: 300000 }), 300000)
})

test('score fetch failures preserve the historical catalog and successful loads index its own IDs', async () => {
  const homes = housing()
  await assert.rejects(listings.loadScores(homes, async () => ({ ok: false })))
  assert.ok(homes.every((h) => !h.listing))
  await listings.loadScores(homes, async (url) => {
    assert.equal(url, '/model-listings.json')
    return { ok: true, json: async () => data }
  })
  assert.equal(listings.listingById.size, 22764)
  assert.equal(listings.listingsMeta.model, 'BL3:N4_img+R_all')
  assert.equal(listings.listingById.get('historical-0'), homes[0])
})

test('filtering reuses the pin source and resetting restores unscored records', async () => {
  const { loadHistoricalHomes, filterHistoricalHomes } =
    await import('../src/demo-layer.js')
  const { homeById } = await import('../src/buildings.js')
  let displayed
  const map = {
    getSource(id) {
      assert.equal(id, 'demo-houses')
      return {
        setData(value) {
          displayed = value
        },
      }
    },
  }
  await loadHistoricalHomes(map, async () => ({
    ok: true,
    json: async () =>
      JSON.parse(
        readFileSync(new URL('../public/houston-homes.json', import.meta.url)),
      ),
  }))
  listings.attachScores([...homeById.values()], data)
  filterHistoricalHomes(
    map,
    (h) => h.listing && h.deal === 'UNDERPRICED' && h.list <= 300000,
  )
  assert.ok(displayed.features.length > 0)
  for (const feature of displayed.features) {
    const h = homeById.get(feature.properties.id)
    assert.ok(h.listing && h.deal === 'UNDERPRICED' && h.list <= 300000)
    assert.deepEqual(feature.geometry.coordinates, [h.lng, h.lat])
  }
  assert.equal(homeById.size, 25922)
  filterHistoricalHomes(map, () => true)
  assert.equal(displayed.features.length, 25922)
})
