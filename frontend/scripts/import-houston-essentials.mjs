// node scripts/import-houston-essentials.mjs /path/to/photon-responses-directory
// Each response uses /api/?q=<category>&osm_tag=<tag>&bbox=<PLAY_BOUNDS>
// &lat=29.7604&lon=-95.3698&limit=100&lang=en (Photon currently caps at 50).
// Responses named houston-{schools,hospitals,supermarkets,pharmacies}.json.
import { readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { PLAY_BOUNDS, inside } from '../src/geo.js'
const files = [
  [
    'houston-schools',
    'school',
    'school',
    'amenity:school',
    -95.3698,
    29.7604,
    100,
  ],
  [
    'houston-hospitals',
    'hospital',
    'hospital',
    'amenity:hospital',
    -95.3698,
    29.7604,
    50,
  ],
  [
    'houston-supermarkets',
    'supermarket',
    'supermarket',
    'shop:supermarket',
    -95.3698,
    29.7604,
    100,
  ],
  [
    'houston-pharmacies',
    'pharmacy',
    'pharmacy',
    'amenity:pharmacy',
    -95.3698,
    29.7604,
    100,
  ],
  [
    'sugar-land-schools',
    'school',
    'school',
    'amenity:school',
    -95.6349,
    29.6197,
    100,
  ],
  [
    'sugar-land-hospitals',
    'hospital',
    'hospital',
    'amenity:hospital',
    -95.6349,
    29.6197,
    100,
  ],
  [
    'sugar-land-pharmacies',
    'pharmacy',
    'pharmacy',
    'amenity:pharmacy',
    -95.6349,
    29.6197,
    100,
  ],
  [
    'sugar-land-heb',
    'supermarket',
    'H-E-B',
    'shop:supermarket',
    -95.6349,
    29.6197,
    100,
  ],
  [
    'sugar-land-kroger',
    'supermarket',
    'Kroger',
    'shop:supermarket',
    -95.6349,
    29.6197,
    100,
  ],
  [
    'sugar-land-aldi',
    'supermarket',
    'ALDI',
    'shop:supermarket',
    -95.6349,
    29.6197,
    100,
  ],
]
const facilities = [],
  sources = []
for (const [file, category, query, tag, lon, lat, limit] of files) {
  const raw = await readFile(`${process.argv[2]}/${file}.json`, 'utf8')
  const data = JSON.parse(raw)
  if (!Array.isArray(data.features))
    throw new Error(`Invalid response: ${file}`)
  sources.push({
    file,
    sha256: createHash('sha256').update(raw).digest('hex'),
    queryUrl: `https://photon.komoot.io/api/?${new URLSearchParams({ q: query, osm_tag: tag, lon, lat, limit, lang: 'en', bbox: '-95.991,29.2178,-94.7486,30.3031' })}`,
  })
  for (const feature of data.features) {
    const p = feature.properties,
      [lng, lat] = feature.geometry.coordinates
    if (!inside(lng, lat)) continue
    const kind = { N: 'node', W: 'way', R: 'relation' }[p.osm_type]
    if (!kind || !p.osm_id) continue
    facilities.push({
      id: `osm-${kind}-${p.osm_id}`,
      category,
      name: p.name || `Mapped ${category}`,
      lng,
      lat,
      sourceUrl: `https://www.openstreetmap.org/${kind}/${p.osm_id}`,
    })
  }
}
const data = {
  source: 'OpenStreetMap contributors via Photon',
  sourceUrl: 'https://photon.komoot.io/',
  license: 'ODbL-1.0',
  accessedAt: new Date().toISOString(),
  bounds: PLAY_BOUNDS,
  scope:
    'Name-search sample of schools, hospitals, supermarkets and pharmacies within the playable Greater Houston region. Photon caps each category response; this is not a complete amenity inventory. Nearest means nearest within this sample, using straight-line distance.',
  sources,
  facilities: [...new Map(facilities.map((f) => [f.id, f])).values()],
}
await writeFile(
  new URL('../public/data/houston-essentials.json', import.meta.url),
  JSON.stringify(data),
)
console.log(`${data.facilities.length} mapped amenities`)
