// A single transient canvas animates arriving pins. Settled pins remain GPU
// symbols; no per-house DOM or source rebuilding is needed during navigation.
export function createPinReveal(map, sprite, getHomes) {
  const canvas = document.createElement('canvas')
  canvas.className = 'pin-reveal-canvas'
  canvas.setAttribute('aria-hidden', 'true')
  map.getCanvasContainer().append(canvas)
  const ctx = canvas.getContext('2d'),
    image = document.createElement('canvas')
  image.width = sprite.width
  image.height = sprite.height
  image.getContext('2d').putImageData(sprite, 0, 0)
  const reduced = matchMedia('(prefers-reduced-motion: reduce)')
  let visible = new Set(),
    arriving = new Map(),
    frame = 0,
    timer = 0,
    enabled = true,
    disposed = false
  const state = (id, value) => {
    if (map.getSource('demo-houses'))
      map.setFeatureState({ source: 'demo-houses', id }, value)
  }
  function resize() {
    const dpr = devicePixelRatio || 1
    canvas.width = map.getContainer().clientWidth * dpr
    canvas.height = map.getContainer().clientHeight * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  resize()
  function scan() {
    timer = 0
    if (disposed) return
    const zoom = map.getZoom(),
      tier = zoom >= 16 ? 2 : zoom >= 14 ? 1 : 0,
      show = enabled && zoom >= 12.25
    const bounds = map.getBounds(),
      w = map.getContainer().clientWidth,
      h = map.getContainer().clientHeight,
      next = new Set()
    let stagger = 0
    if (show)
      for (const b of getHomes()) {
        if (
          b.tier > tier ||
          b.lng < bounds.getWest() ||
          b.lng > bounds.getEast() ||
          b.lat < bounds.getSouth() ||
          b.lat > bounds.getNorth()
        )
          continue
        const p = map.project([b.lng, b.lat])
        if (p.x < 0 || p.x > w || p.y < 0 || p.y > h + 30) continue
        next.add(b.id)
        if (!visible.has(b.id)) {
          if (reduced.matches) {
            state(b.id, { revealed: true, arriving: false })
          } else {
            arriving.set(b.id, {
              b,
              start: performance.now() + (stagger++ % 7) * 35,
            })
            state(b.id, { revealed: true, arriving: true })
          }
        }
      }
    for (const id of visible)
      if (!next.has(id)) {
        state(id, { revealed: false, arriving: false })
        arriving.delete(id)
      }
    visible = next
    if (arriving.size && !frame) frame = requestAnimationFrame(draw)
  }
  const knots = [
    [0, 0.12, -12, 0.0],
    [0.35, 1.22, 9, 1],
    [0.53, 0.92, -8, 1],
    [0.7, 1.04, 5, 1],
    [0.85, 1, -2, 1],
    [1, 1, 0, 1],
  ]
  function draw(now) {
    frame = 0
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const zoom = map.getZoom(),
      base =
        zoom < 16
          ? 0.65 + ((zoom - 12) / 4) * 0.17
          : 0.82 + (Math.min(2, zoom - 16) / 2) * 0.18
    for (const [id, entry] of arriving) {
      const t = Math.max(0, (now - entry.start) / 780)
      if (t >= 1 || reduced.matches) {
        state(id, { revealed: true, arriving: false })
        arriving.delete(id)
        continue
      }
      let i = 1
      while (knots[i][0] < t) i++
      const a = knots[i - 1],
        b = knots[i],
        f = (t - a[0]) / (b[0] - a[0]),
        lerp = (n) => a[n] + (b[n] - a[n]) * f
      const p = map.project([entry.b.lng, entry.b.lat]),
        scale = base * lerp(1)
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate((lerp(2) * Math.PI) / 180)
      ctx.scale(scale, scale)
      ctx.globalAlpha = lerp(3) * 0.92
      ctx.drawImage(image, -16, -42, 32, 42)
      ctx.restore()
    }
    if (arriving.size) frame = requestAnimationFrame(draw)
  }
  function schedule() {
    if (!timer) timer = setTimeout(scan, 60)
  }
  const resized = () => {
    resize()
    scan()
  }
  map.on('move', schedule)
  map.on('moveend', scan)
  map.on('idle', scan)
  map.on('resize', resized)
  return {
    refresh: scan,
    setEnabled(value) {
      enabled = value
      scan()
    },
    destroy() {
      disposed = true
      clearTimeout(timer)
      cancelAnimationFrame(frame)
      map.off('move', schedule)
      map.off('moveend', scan)
      map.off('idle', scan)
      map.off('resize', resized)
      canvas.remove()
    },
  }
}
