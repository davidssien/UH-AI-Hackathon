import test from 'node:test'
import assert from 'node:assert/strict'
import {
  HOUSTON,
  PLAY_BOUNDS,
  minimumZoom,
  centerLimits,
  constrainCenter,
  project,
  unproject,
  inside,
} from '../src/geo.js'

const near = (a, b, epsilon = 1e-8) =>
  assert.ok(Math.abs(a - b) < epsilon, `${a} differs from ${b}`)
test('minimum zoom covers wide, portrait and mobile viewports', () => {
  for (const [w, h] of [
    [1920, 1080],
    [880, 915],
    [390, 844],
    [2560, 720],
  ]) {
    const zoom = minimumZoom(w, h)
    const [west, south] = project(PLAY_BOUNDS[0]),
      [east, north] = project(PLAY_BOUNDS[1])
    const scale = 512 * 2 ** zoom
    assert.ok((east - west) * scale >= w)
    assert.ok((south - north) * scale >= h)
    const center = constrainCenter(HOUSTON, w, h, zoom)
    const [x, y] = project(center)
    assert.ok(x - w / 2 / scale >= west && x + w / 2 / scale <= east)
    assert.ok(y - h / 2 / scale >= north && y + h / 2 / scale <= south)
  }
})
test('released overscroll restores every viewport edge inside play area', () => {
  for (const zoom of [10, 12.25, 18])
    for (const center of [[-97, 28], [-94, 31], HOUSTON]) {
      const target = constrainCenter(center, 1440, 900, zoom)
      const [x, y] = project(target),
        [[loX, hiX], [loY, hiY]] = centerLimits(1440, 900, zoom)
      assert.ok(x >= loX - 1e-10 && x <= hiX + 1e-10)
      assert.ok(y >= loY - 1e-10 && y <= hiY + 1e-10)
    }
})
test('elastic motion is continuous, bounded and increasingly resistant', () => {
  const [[, edge]] = centerLimits(1440, 900, 12)
  const [, y] = project(HOUSTON)
  const sample = (d) =>
    project(constrainCenter(unproject([edge + d, y]), 1440, 900, 12, true))[0] -
    edge
  near(sample(0), 0)
  assert.ok(sample(0.001) > sample(0.0005))
  assert.ok(sample(0.001) - sample(0.0005) < sample(0.0005))
  assert.ok(sample(1) < 0.0004)
  const interior = constrainCenter(HOUSTON, 1440, 900, 12, true)
  near(interior[0], HOUSTON[0])
  near(interior[1], HOUSTON[1])
})
test('placements reject exterior and accept square boundary', () => {
  assert.ok(inside(...HOUSTON))
  assert.ok(inside(...PLAY_BOUNDS[0]))
  assert.ok(inside(...PLAY_BOUNDS[1]))
  assert.equal(inside(-97, 29.7), false)
  assert.equal(inside(-95.3, 31), false)
})
