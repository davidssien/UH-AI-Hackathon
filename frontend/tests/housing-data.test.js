import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import * as details from '../src/property-details.js'

const moduleUrl = new URL('../src/housing-data.js', import.meta.url)
const row = {
  rowId: 0,
  lng: -95.3,
  lat: 29.7,
  zip: '77004',
  city: 'Houston',
  homeType: 'SINGLE_FAMILY',
  beds: null,
  baths: 2,
  livingArea: 1200,
  lotSqft: null,
  yearBuilt: null,
}
const snapshot = (homes = [row]) => ({
  metadata: {
    schemaVersion: 1,
    totalRecords: homes.length,
    sourceSha256: 'a'.repeat(64),
    sourceUrl:
      'https://www.kaggle.com/datasets/mohamedalmansop/houston-housing-market-2024-clean-dataset',
  },
  homes,
})
async function module() {
  assert.ok(existsSync(moduleUrl), 'historical catalog adapter is missing')
  return import(moduleUrl)
}

test('historical catalog preserves identity, coordinates and unknown facts', async () => {
  const { prepareHousing } = await module()
  const { homes } = prepareHousing(
    snapshot([{ ...row, price: 500000, zestimate: 600000 }]),
  )
  assert.equal(homes[0].id, 'historical-0')
  assert.equal(homes[0].lng, row.lng)
  assert.equal(homes[0].lat, row.lat)
  assert.equal(homes[0].beds, null)
  assert.equal(homes[0].zip, '77004')
  assert.equal(homes[0].historical, true)
  assert.equal(homes[0].demo, false)
  assert.equal(homes[0].price, undefined)
  assert.equal(homes[0].zestimate, undefined)
})
test('invalid and duplicate records fail instead of creating partial or fake pins', async () => {
  const { prepareHousing } = await module()
  for (const homes of [
    [row, row],
    [{ ...row, lng: null }],
    [{ ...row, lat: NaN }],
    [{ ...row, rowId: '0' }],
  ])
    assert.throws(() => prepareHousing(snapshot(homes)))
  assert.throws(() =>
    prepareHousing({ ...snapshot(), metadata: { schemaVersion: 2 } }),
  )
  assert.throws(() =>
    prepareHousing({
      ...snapshot(),
      metadata: { ...snapshot().metadata, totalRecords: 2 },
    }),
  )
})
test('shared coordinates retain all observations without invented offsets', async () => {
  const { prepareHousing, homesAtLocation } = await module()
  const { homes } = prepareHousing(
    snapshot([
      row,
      { ...row, rowId: 1, beds: 4 },
      { ...row, rowId: 2, lng: -95.4 },
    ]),
  )
  assert.deepEqual(
    homesAtLocation(homes[0], homes).map((h) => h.rowId),
    [0, 1],
  )
  assert.equal(homes[1].lng, row.lng)
})
test('historical pricing is unavailable and never falls back to a mock valuation', () => {
  assert.equal(
    typeof details.pricePresentation,
    'function',
    'historical pricing presentation is missing',
  )
  const presentation = details.pricePresentation({
    ...row,
    id: 'historical-0',
    type: 'house',
    historical: true,
  })
  assert.equal(presentation.price, null)
  assert.match(presentation.label, /unavailable/i)
  assert.doesNotMatch(presentation.note, /demo pricing/i)
  assert.ok(
    details.pricePresentation({ id: 'proposal-1', type: 'house' }).price > 0,
  )
})
test('bundled catalog contains the source record count, unique IDs and no prices', async () => {
  const { prepareHousing } = await module()
  const data = JSON.parse(
    readFileSync(new URL('../public/houston-homes.json', import.meta.url)),
  )
  const { homes, outsideCount } = prepareHousing(data)
  assert.equal(homes.length, 25922)
  assert.equal(new Set(homes.map((h) => h.id)).size, 25922)
  assert.equal(outsideCount, 7)
  assert.equal(data.metadata.uniqueCoordinates, 20679)
  assert.equal(homes.filter((h) => h.address).length, 25799)
  assert.equal(data.metadata.addressMissing, 123)
  assert.equal(
    homes.find((h) => h.rowId === 2085).address,
    '4040 San Felipe St APT 140, Houston TX 77027',
  )
  for (const h of data.homes)
    assert.ok(!('price' in h || 'zestimate' in h || 'rentZestimate' in h))
})

test('map loader installs source coordinates and never seeds generated homes on failure', async () => {
  const { loadHistoricalHomes } = await import('../src/demo-layer.js')
  const { homeById } = await import('../src/buildings.js')
  assert.equal(homeById.size, 0)
  let geojson = null
  const map = {
    getSource: () => ({
      setData(data) {
        geojson = data
      },
    }),
  }
  await assert.rejects(loadHistoricalHomes(map, async () => ({ ok: false })))
  assert.equal(homeById.size, 0)
  assert.equal(geojson, null)
  await loadHistoricalHomes(map, async (url) => {
    assert.equal(url, '/houston-homes.json')
    return { ok: true, json: async () => snapshot([row, { ...row, rowId: 1 }]) }
  })
  assert.equal(homeById.size, 2)
  assert.ok([...homeById.keys()].every((id) => id.startsWith('historical-')))
  assert.deepEqual(geojson.features[0].geometry.coordinates, [row.lng, row.lat])
  assert.equal(geojson.features[0].properties.id, 'historical-0')
  const before = [...homeById]
  await assert.rejects(
    loadHistoricalHomes(map, async () => ({
      ok: true,
      json: async () => snapshot([row, row]),
    })),
  )
  assert.deepEqual([...homeById], before)
})

test('recorded facts preserve zero and show unknown instead of inventing missing values', () => {
  const facts = new Map(
    details.propertyFacts({
      beds: 0,
      baths: null,
      zip: '77004',
      livingArea: null,
    }),
  )
  assert.equal(facts.get('Bedrooms'), '0')
  assert.equal(facts.get('Bathrooms'), 'Unknown')
  assert.equal(facts.get('Living area'), 'Unknown')
  assert.equal(facts.get('ZIP'), '77004')
})

test('Explore centers a real in-bounds observation visible on a narrow mobile viewport', async () => {
  const { housingExploreCenter, prepareHousing } = await module()
  assert.equal(
    typeof housingExploreCenter,
    'function',
    'Explore must use an actual historical observation',
  )
  const { project, inside } = await import('../src/geo.js')
  const { homes } = prepareHousing(
    JSON.parse(
      readFileSync(new URL('../public/houston-homes.json', import.meta.url)),
    ),
  )
  const center = housingExploreCenter(homes.values())
  assert.ok(inside(...center))
  const scale = 512 * 2 ** 16.5
  const [cx, cy] = project(center)
  const visible = homes.filter((h) => {
    const [x, y] = project([h.lng, h.lat])
    return (
      Math.abs(x - cx) * scale < 390 / 2 && Math.abs(y - cy) * scale < 844 / 2
    )
  })
  assert.ok(visible.length > 0)
  assert.ok(homes.some((h) => h.lng === center[0] && h.lat === center[1]))
})

test('historical titles use the recorded address and never an observation number', async () => {
  const housing = await module()
  assert.equal(
    typeof housing.housingTitle,
    'function',
    'address-based title is missing',
  )
  const { homes } = housing.prepareHousing(
    snapshot([
      { ...row, address: '4040 San Felipe St APT 140, Houston TX 77027' },
    ]),
  )
  assert.equal(
    housing.housingTitle(homes[0]),
    '4040 San Felipe St APT 140, Houston TX 77027',
  )
  assert.equal(
    housing.housingTitle({ ...homes[0], address: null }),
    'Address unavailable',
  )
  assert.equal(
    housing.housingTitle({ ...homes[0], address: '   ' }),
    'Address unavailable',
  )
})
