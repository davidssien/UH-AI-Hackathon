import { HOUSTON, inside } from './geo.js'

export const HOUSING_SOURCE_URL =
  'https://www.kaggle.com/datasets/mohamedalmansop/houston-housing-market-2024-clean-dataset'

const fact = (value) => (Number.isFinite(value) && value >= 0 ? value : null)

export function prepareHousing(data) {
  if (
    data?.metadata?.schemaVersion !== 1 ||
    !/^[a-f0-9]{64}$/.test(data.metadata.sourceSha256) ||
    !Array.isArray(data.homes) ||
    !data.homes.length ||
    data.metadata.totalRecords !== data.homes.length
  )
    throw new Error('Invalid historical housing snapshot')
  const ids = new Set()
  const homes = data.homes.map((row) => {
    if (
      !Number.isSafeInteger(row?.rowId) ||
      row.rowId < 0 ||
      ids.has(row.rowId) ||
      !Number.isFinite(row.lng) ||
      !Number.isFinite(row.lat) ||
      Math.abs(row.lng) > 180 ||
      Math.abs(row.lat) > 90
    )
      throw new Error('Invalid housing identity or coordinates')
    ids.add(row.rowId)
    return {
      id: `historical-${row.rowId}`,
      rowId: row.rowId,
      type: 'house',
      historical: true,
      existing: true,
      demo: false,
      lng: row.lng,
      lat: row.lat,
      // Preserve the existing sparse-to-detailed pin animation.
      tier: row.rowId % 30 === 0 ? 0 : row.rowId % 5 === 0 ? 1 : 2,
      zip:
        typeof row.zip === 'string' && /^(?!00000)[0-9]{5}$/.test(row.zip)
          ? row.zip
          : null,
      address:
        typeof row.address === 'string' && row.address.trim()
          ? row.address.trim()
          : null,
      city: typeof row.city === 'string' ? row.city : null,
      homeType: typeof row.homeType === 'string' ? row.homeType : null,
      beds: fact(row.beds),
      baths: fact(row.baths),
      livingArea: fact(row.livingArea),
      lotSqft: fact(row.lotSqft),
      yearBuilt: fact(row.yearBuilt),
      sourceUrl: HOUSING_SOURCE_URL,
    }
  })
  return {
    homes,
    metadata: data.metadata,
    outsideCount: homes.filter((home) => !inside(home.lng, home.lat)).length,
  }
}

export function homesAtLocation(home, homes) {
  return [...homes].filter(
    (candidate) => candidate.lng === home.lng && candidate.lat === home.lat,
  )
}

// Center Explore on a source observation rather than an arbitrary neighborhood.
export function housingExploreCenter(homes) {
  let nearest = null,
    best = Infinity
  for (const home of homes) {
    if (!inside(home.lng, home.lat)) continue
    const distance = Math.hypot(home.lng - HOUSTON[0], home.lat - HOUSTON[1])
    if (distance < best) {
      nearest = home
      best = distance
    }
  }
  return nearest ? [nearest.lng, nearest.lat] : HOUSTON
}

export function housingTitle(home) {
  return typeof home.address === 'string' && home.address.trim()
    ? home.address.trim()
    : 'Address unavailable'
}
