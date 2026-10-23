// Location context uses already loaded basemap tiles. It is not a legal boundary
// lookup, and a nearby house number is never fabricated into a street address.
import { homeById } from './buildings.js'
const nameOf = (p) => p['name:en'] || p.name_en || p.name
const cities = new Map()
let searchedAddress = null
export function setSearchedAddress(place) {
  searchedAddress = place?.address ? place : null
}
function squaredDistance(map, geometry, center) {
  if (geometry.type === 'Point') {
    const p = map.project(geometry.coordinates)
    return (p.x - center.x) ** 2 + (p.y - center.y) ** 2
  }
  const lines =
    geometry.type === 'LineString'
      ? [geometry.coordinates]
      : geometry.type === 'MultiLineString'
        ? geometry.coordinates
        : []
  let best = Infinity
  for (const line of lines)
    for (let i = 1; i < line.length; i++) {
      const a = map.project(line[i - 1]),
        b = map.project(line[i]),
        dx = b.x - a.x,
        dy = b.y - a.y
      const t = Math.max(
        0,
        Math.min(
          1,
          ((center.x - a.x) * dx + (center.y - a.y) * dy) /
            (dx * dx + dy * dy || 1),
        ),
      )
      best = Math.min(
        best,
        (a.x + t * dx - center.x) ** 2 + (a.y + t * dy - center.y) ** 2,
      )
    }
  return best
}
export function updateLocation(map) {
  if (!map.getSource('openmaptiles') || map.isMoving()) return
  const zoom = map.getZoom(),
    center = map.project(map.getCenter())
  const places = map.querySourceFeatures('openmaptiles', {
    sourceLayer: 'place',
  })
  for (const feature of places)
    if (
      ['city', 'town', 'village'].includes(feature.properties.class) &&
      nameOf(feature.properties)
    )
      cities.set(nameOf(feature.properties), feature)
  const nearest = (features) =>
    features
      .map((f) => ({ f, d: squaredDistance(map, f.geometry, center) }))
      .sort((a, b) => a.d - b.d)[0]
  const city = nearest([...cities.values()])
  const position = map.getCenter()
  const nearbyHome =
    zoom >= 13
      ? [...homeById.values()]
          .filter((home) => home.existing)
          .map((home) => ({
            home,
            distance: Math.hypot(
              (home.lng - position.lng) * 96700,
              (home.lat - position.lat) * 110574,
            ),
          }))
          .sort((a, b) => a.distance - b.distance)[0]
      : null
  const locality =
    nearbyHome?.distance < 200
      ? nearbyHome.home.city || 'Unknown city'
      : city
        ? nameOf(city.f.properties)
        : 'Houston'
  let title = zoom < 10.75 ? 'Greater Houston, Texas' : `${locality}, TX`
  let detail = zoom < 10.75 ? 'REGION VIEW' : 'NEARBY LOCALITY · MAP CENTER'
  if (zoom >= 13) {
    const neighborhood = nearest(
      places.filter(
        (f) =>
          ['suburb', 'quarter', 'neighbourhood'].includes(f.properties.class) &&
          nameOf(f.properties),
      ),
    )
    if (neighborhood && neighborhood.d < 300 ** 2) {
      title = nameOf(neighborhood.f.properties)
      detail = `${locality.toUpperCase()}, TX · NEIGHBORHOOD`
    }
  }
  if (zoom >= 14.5) {
    const roads = map
      .querySourceFeatures('openmaptiles', {
        sourceLayer: 'transportation_name',
      })
      .filter(
        (f) =>
          nameOf(f.properties) &&
          !['motorway', 'trunk'].includes(f.properties.class),
      )
    const road = nearest(roads)
    if (road && road.d < 120 ** 2) {
      title = nameOf(road.f.properties)
      detail = `NEAR MAP CENTER · ${locality.toUpperCase()}, TX`
    }
  }
  if (zoom >= 17) {
    const features = map.queryRenderedFeatures([
      [center.x - 14, center.y - 14],
      [center.x + 14, center.y + 14],
    ])
    const address = features.find(
      (f) =>
        f.properties?.['addr:full'] ||
        (f.properties?.['addr:housenumber'] && f.properties?.['addr:street']),
    )
    if (nearbyHome?.distance < 25 && nearbyHome.home.address) {
      title = nearbyHome.home.address
      detail = `${locality.toUpperCase()}, TX · NEARBY RECORDED ADDRESS`
    } else if (address) {
      const p = address.properties
      title = p['addr:full'] || `${p['addr:housenumber']} ${p['addr:street']}`
      detail = `${locality.toUpperCase()}, TX · MAPPED ADDRESS`
    } else
      detail += ` · ${map.getCenter().lat.toFixed(4)}, ${map.getCenter().lng.toFixed(4)}`
  }
  if (
    searchedAddress &&
    zoom >= 16 &&
    Math.hypot(
      (searchedAddress.lng - position.lng) * 96700,
      (searchedAddress.lat - position.lat) * 110574,
    ) < 20
  ) {
    title = searchedAddress.address
    detail =
      searchedAddress.source === 'census'
        ? 'ADDRESS SEARCH · US CENSUS'
        : 'MAPPED ADDRESS · MAP CENTER'
  }
  document.getElementById('location-title').title = title
  document.getElementById('location-title').textContent = title
  document.getElementById('location-detail').textContent = detail
}
