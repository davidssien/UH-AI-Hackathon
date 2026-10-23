import test from 'node:test'
import assert from 'node:assert/strict'
import {
  looksLikeAddress,
  censusQuery,
  censusPlaces,
} from '../src/address-search.js'
import { inSearchScope, photonPlace } from '../src/search.js'

test('numbered street addresses are sent to the address service', () => {
  assert.ok(looksLikeAddress('1600 Smith St, Houston, TX'))
  assert.ok(looksLikeAddress('12345 Main Street'))
  assert.equal(looksLikeAddress('Sugar Land'), false)
  assert.equal(looksLikeAddress('77002'), false)
  assert.equal(
    censusQuery('12345 Main Street'),
    '12345 Main Street, Houston, TX',
  )
  assert.equal(
    censusQuery('1600 Smith St, Houston, TX'),
    '1600 Smith St, Houston, TX',
  )
  assert.equal(censusQuery('123 Main St Seattle WA'), '123 Main St Seattle WA')
  assert.equal(censusQuery('123 Main St 75201'), '123 Main St 75201')
})
test('Census matches preserve full addresses and outside destinations fail the map scope', () => {
  const result = censusPlaces({
    result: {
      addressMatches: [
        {
          matchedAddress: '1600 SMITH ST, HOUSTON, TX, 77002',
          coordinates: { x: -95.371616685248, y: 29.755053017327 },
        },
        {
          matchedAddress: 'OUTSIDE ADDRESS, DALLAS, TX',
          coordinates: { x: -96.8, y: 32.8 },
        },
        { matchedAddress: 'Invalid', coordinates: {} },
      ],
    },
  })
  assert.equal(result.length, 2)
  assert.equal(result[0].address, '1600 SMITH ST, HOUSTON, TX, 77002')
  assert.equal(result[0].zoom, 18)
  assert.equal(result[0].source, 'census')
  assert.ok(inSearchScope(result[0]))
  assert.equal(inSearchScope(result[1]), false)
  assert.deepEqual(censusPlaces({ result: { addressMatches: [] } }), [])
})
test('reverse-geocoded addresses prefer the supplied house address over a business name', () => {
  const place = photonPlace({
    properties: {
      name: 'Business',
      housenumber: '1600',
      street: 'Smith Street',
      city: 'Houston',
      state: 'Texas',
      postcode: '77002',
    },
    geometry: { coordinates: [-95.37, 29.75] },
  })
  assert.equal(place.label, '1600 Smith Street')
  assert.equal(place.address, '1600 Smith Street, Houston, Texas, 77002')
  assert.equal(
    photonPlace({
      properties: { street: 'Main Street' },
      geometry: { coordinates: [-95.37, 29.75] },
    }).address,
    null,
  )
})
