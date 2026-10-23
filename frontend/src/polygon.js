import { inside, PLAY_BOUNDS } from './geo.js'
export const midpoint = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
export function pointInPolygon(point, vertices) {
  let result = false
  for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
    const a = vertices[i],
      b = vertices[j]
    if (
      a[1] > point[1] !== b[1] > point[1] &&
      point[0] < ((b[0] - a[0]) * (point[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      result = !result
  }
  return result
}
function crosses(a, b, c, d) {
  const turn = (p, q, r) =>
    (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
  const between = (p, q, r) =>
    Math.abs(turn(p, q, r)) < 1e-14 &&
    r[0] >= Math.min(p[0], q[0]) - 1e-12 &&
    r[0] <= Math.max(p[0], q[0]) + 1e-12 &&
    r[1] >= Math.min(p[1], q[1]) - 1e-12 &&
    r[1] <= Math.max(p[1], q[1]) + 1e-12
  const t1 = turn(a, b, c),
    t2 = turn(a, b, d),
    t3 = turn(c, d, a),
    t4 = turn(c, d, b)
  return (
    (t1 * t2 < 0 && t3 * t4 < 0) ||
    between(a, b, c) ||
    between(a, b, d) ||
    between(c, d, a) ||
    between(c, d, b)
  )
}
export function polygonSite(vertices) {
  const origin = vertices[0],
    sx = 111320 * Math.cos((origin[1] * Math.PI) / 180),
    sy = 110574
  const local = vertices.map((p) => [
    (p[0] - origin[0]) * sx,
    (p[1] - origin[1]) * sy,
  ])
  let twiceArea = 0,
    cx = 0,
    cy = 0
  for (let i = 0; i < local.length; i++) {
    const a = local[i],
      b = local[(i + 1) % local.length],
      cross = a[0] * b[1] - b[0] * a[1]
    twiceArea += cross
    cx += (a[0] + b[0]) * cross
    cy += (a[1] + b[1]) * cross
  }
  const xs = vertices.map((p) => p[0]),
    ys = vertices.map((p) => p[1]),
    w = Math.min(...xs),
    e = Math.max(...xs),
    s = Math.min(...ys),
    n = Math.max(...ys)
  let center =
    Math.abs(twiceArea) > 1e-8
      ? [
          origin[0] + cx / (3 * twiceArea) / sx,
          origin[1] + cy / (3 * twiceArea) / sy,
        ]
      : midpoint([w, s], [e, n])
  if (!pointInPolygon(center, vertices)) {
    outer: for (let y = 1; y < 20; y++)
      for (let x = 1; x < 20; x++) {
        const p = [w + ((e - w) * x) / 20, s + ((n - s) * y) / 20]
        if (pointInPolygon(p, vertices)) {
          center = p
          break outer
        }
      }
  }
  return {
    center,
    area: Math.abs(twiceArea) / 2,
    width: (e - w) * sx,
    height: (n - s) * sy,
    geometry: {
      type: 'Polygon',
      coordinates: [[...vertices.map((p) => [...p]), [...vertices[0]]]],
    },
  }
}
export function validPolygon(vertices) {
  if (
    vertices.length < 3 ||
    vertices.length > 32 ||
    !vertices.every(
      (p) => Number.isFinite(p[0]) && Number.isFinite(p[1]) && inside(...p),
    )
  )
    return false
  for (let i = 0; i < vertices.length; i++) {
    const a = vertices[i],
      b = vertices[(i + 1) % vertices.length]
    if (Math.hypot((b[0] - a[0]) * 96000, (b[1] - a[1]) * 110574) < 1)
      return false
    for (let j = i + 1; j < vertices.length; j++) {
      if (j === i + 1 || (i === 0 && j === vertices.length - 1)) continue
      if (crosses(a, b, vertices[j], vertices[(j + 1) % vertices.length]))
        return false
    }
  }
  return polygonSite(vertices).area >= 9
}
export function translatePolygon(vertices, delta) {
  const [[w, s], [e, n]] = PLAY_BOUNDS
  const xs = vertices.map((p) => p[0]),
    ys = vertices.map((p) => p[1])
  const dx = Math.max(
    w - Math.min(...xs),
    Math.min(e - Math.max(...xs), delta[0]),
  )
  const dy = Math.max(
    s - Math.min(...ys),
    Math.min(n - Math.max(...ys), delta[1]),
  )
  return vertices.map((p) => [p[0] + dx, p[1] + dy])
}
