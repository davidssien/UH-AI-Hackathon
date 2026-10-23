// Geographic calculations stay independent of MapLibre for deterministic checks.
export const HOUSTON = [-95.3698, 29.7604]
export const PLAY_HALF_SIZE_KM = 60
const latKm = 110.574
const lngKm = 111.32 * Math.cos((HOUSTON[1] * Math.PI) / 180)
export const PLAY_BOUNDS = [
  [HOUSTON[0] - 60 / lngKm, HOUSTON[1] - 60 / latKm],
  [HOUSTON[0] + 60 / lngKm, HOUSTON[1] + 60 / latKm],
]
export const mercatorY = (lat) =>
  (1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2
const latitude = (y) =>
  (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI
export const project = ([lng, lat]) => [(lng + 180) / 360, mercatorY(lat)]
export const unproject = ([x, y]) => [x * 360 - 180, latitude(y)]
const sw = project(PLAY_BOUNDS[0])
const ne = project(PLAY_BOUNDS[1])
export const inside = (lng, lat) =>
  lng >= PLAY_BOUNDS[0][0] &&
  lng <= PLAY_BOUNDS[1][0] &&
  lat >= PLAY_BOUNDS[0][1] &&
  lat <= PLAY_BOUNDS[1][1]
export function minimumZoom(width, height) {
  // Two pixels of breathing room keep antialiased boundary lines offscreen.
  return Math.max(
    Math.log2((width + 4) / (512 * (ne[0] - sw[0]))),
    Math.log2((height + 4) / (512 * (sw[1] - ne[1]))),
  )
}
export function centerLimits(width, height, zoom) {
  const world = 512 * 2 ** zoom
  const hx = (width / 2 + 1) / world
  const hy = (height / 2 + 1) / world
  return [
    [sw[0] + hx, ne[0] - hx],
    [ne[1] + hy, sw[1] - hy],
  ]
}
export function constrainCenter(center, width, height, zoom, elastic = false) {
  const point = project(center)
  const limits = centerLimits(width, height, zoom)
  // 12 km in Houston's projected coordinate system.
  const max = 12 / (40075.017 * Math.cos((HOUSTON[1] * Math.PI) / 180))
  return unproject(
    point.map((value, axis) => {
      let [lo, hi] = limits[axis]
      if (lo > hi) lo = hi = (lo + hi) / 2
      const edge = Math.max(lo, Math.min(hi, value))
      const excess = value - edge
      return (
        edge +
        (elastic
          ? Math.sign(excess) * max * -Math.expm1(-Math.abs(excess) / max)
          : 0)
      )
    }),
  )
}
export function squareFeature() {
  const [[w, s], [e, n]] = PLAY_BOUNDS
  return {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [w, s],
          [e, s],
          [e, n],
          [w, n],
          [w, s],
        ],
      ],
    },
  }
}
