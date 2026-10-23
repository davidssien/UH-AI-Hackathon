// Refresh: POST scripts/sugar-land.overpassql to an Overpass interpreter, then
// node scripts/import-sugar-land.mjs /path/to/response.json
import { readFile, writeFile } from 'node:fs/promises'
const raw = JSON.parse(await readFile(process.argv[2], 'utf8'))
if (raw.remark || !Array.isArray(raw.elements) || !raw.elements.length)
  throw new Error('Incomplete/empty Overpass response')
const homes = raw.elements
  .filter((e) => e.center && e.type === 'way')
  .map((e) => {
    const t = e.tags || {},
      number = t['addr:housenumber'],
      street = t['addr:street']
    return {
      id: `osm-way-${e.id}`,
      osmId: e.id,
      lng: e.center.lon,
      lat: e.center.lat,
      type: t.building === 'apartments' ? 'apartment' : 'house',
      building: t.building,
      address:
        t['addr:full'] || (number && street ? `${number} ${street}` : null),
      street: street || null,
      postcode: t['addr:postcode'] || null,
      sourceUrl: `https://www.openstreetmap.org/way/${e.id}`,
      tier: e.id % 30 === 0 ? 0 : e.id % 5 === 0 ? 1 : 2,
      existing: true,
      demo: false,
    }
  })
const result = {
  source: 'OpenStreetMap contributors',
  license: 'ODbL-1.0',
  sourceUrl: 'https://www.openstreetmap.org/copyright',
  dataTimestamp: raw.osm3s?.timestamp_osm_base,
  scope:
    'Residential building ways inside the OpenStreetMap administrative area named Sugar Land. This is mapped coverage, not a complete house inventory.',
  homes,
}
await writeFile(
  new URL('../public/data/sugar-land-homes.json', import.meta.url),
  JSON.stringify(result),
)
console.log(
  `${homes.length} mapped buildings; ${homes.filter((h) => h.address).length} recorded addresses`,
)
