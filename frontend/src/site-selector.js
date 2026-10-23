import { Marker } from 'maplibre-gl'
import { inside } from './geo.js'
import { selectedSite, emptyCollection, areaLabel } from './sites.js'
import {
  midpoint,
  pointInPolygon,
  polygonSite,
  validPolygon,
  translatePolygon,
} from './polygon.js'

export function createSiteSelector(
  map,
  { onComplete, onStart, onHint, onChange, onDelete },
) {
  const canvas = map.getCanvas(),
    container = map.getCanvasContainer()
  let enabled = false,
    first = null,
    startPoint = null,
    pointerId = null,
    awaitingCorner = false,
    secondClick = false
  let vertices = null,
    action = null,
    origin = null,
    before = null,
    history = [],
    selectedVertex = -1
  const handles = []
  const tools = document.createElement('div')
  tools.className = 'boundary-tools'
  tools.setAttribute('role', 'toolbar')
  tools.setAttribute('aria-label', 'Boundary actions')
  tools.innerHTML =
    '<button type="button" class="boundary-drag" data-boundary-action="move" aria-label="Drag to move boundary" title="Drag to move boundary">✥</button><button type="button" class="boundary-delete" data-boundary-action="delete" aria-label="Delete boundary" title="Delete boundary"><svg width="15" height="16" viewBox="0 0 18 20" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M2 5h14M6 5V2h6v3M4 5l1 13h8l1-13M7 8v7M11 8v7"/></svg></button>'
  let toolsMarker
  tools.addEventListener('click', (event) => {
    event.stopPropagation()
    if (event.target.closest('[data-boundary-action="delete"]')) onDelete?.()
  })
  tools.querySelector('.boundary-drag').addEventListener('keydown', (event) => {
    const direction = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, 1],
      ArrowDown: [0, -1],
    }[event.key]
    if (!vertices || !direction) return
    event.preventDefault()
    pushHistory()
    const step = event.shiftKey ? 10 : 1
    vertices = translatePolygon(vertices, [
      (direction[0] * step) / 96000,
      (direction[1] * step) / 110574,
    ])
    refresh()
  })
  const point = (e) => {
    const r = canvas.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }
  const coordinates = (p) => {
    const ll = map.unproject(p)
    return [ll.lng, ll.lat]
  }
  const copy = (v) => v.map((p) => [...p])
  function show(site) {
    map.getSource('draft-site')?.setData(
      site
        ? {
            type: 'FeatureCollection',
            features: [
              { type: 'Feature', properties: {}, geometry: site.geometry },
            ],
          }
        : emptyCollection(),
    )
  }
  function pushHistory(v = vertices) {
    if (v) {
      history.push(copy(v))
      if (history.length > 40) history.shift()
    }
  }
  function release() {
    if (pointerId !== null && canvas.hasPointerCapture(pointerId))
      canvas.releasePointerCapture(pointerId)
    pointerId = null
    action = null
  }
  function syncHandles() {
    if (vertices) {
      if (!toolsMarker)
        toolsMarker = new Marker({
          element: tools,
          anchor: 'bottom',
          offset: [0, -42],
        })
          .setLngLat(polygonSite(vertices).center)
          .addTo(map)
      else toolsMarker.setLngLat(polygonSite(vertices).center)
    } else {
      toolsMarker?.remove()
      toolsMarker = null
    }
    const needed = vertices ? vertices.length * 2 : 0
    while (handles.length > needed) handles.pop().marker.remove()
    while (handles.length < needed) {
      const el = document.createElement('button')
      el.type = 'button'
      el.className = 'site-handle'
      const entry = {
        el,
        marker: new Marker({ element: el, anchor: 'center' })
          .setLngLat([0, 0])
          .addTo(map),
      }
      el.addEventListener('keydown', (event) => {
        const index = Number(el.dataset.index)
        if (
          el.dataset.kind === 'mid' &&
          (event.key === 'Enter' || event.key === ' ')
        ) {
          event.preventDefault()
          insert(index)
          return
        }
        if (el.dataset.kind !== 'vertex') return
        if (
          ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(
            event.key,
          )
        ) {
          event.preventDefault()
          const v = copy(vertices),
            step = event.shiftKey ? 10 : 1
          v[index][0] +=
            ((event.key === 'ArrowRight'
              ? 1
              : event.key === 'ArrowLeft'
                ? -1
                : 0) *
              step) /
            96000
          v[index][1] +=
            ((event.key === 'ArrowUp'
              ? 1
              : event.key === 'ArrowDown'
                ? -1
                : 0) *
              step) /
            110574
          if (validPolygon(v)) {
            pushHistory()
            vertices = v
            refresh()
          }
        } else if (event.key === 'Delete' || event.key === 'Backspace') {
          event.preventDefault()
          removeVertex(index)
        }
      })
      handles.push(entry)
    }
    handles.forEach(({ el, marker }, i) => {
      const index = Math.floor(i / 2),
        mid = i % 2 === 1
      el.dataset.kind = mid ? 'mid' : 'vertex'
      el.dataset.index = index
      el.classList.toggle('site-midpoint', mid)
      el.classList.toggle('site-vertex', !mid)
      el.classList.toggle('selected', !mid && index === selectedVertex)
      el.textContent = mid ? '+' : ''
      el.setAttribute(
        'aria-label',
        mid
          ? `Add vertex on edge ${index + 1}`
          : `Corner ${index + 1}. Drag or use arrow keys to move; Delete to remove.`,
      )
      el.title = mid
        ? 'Add a vertex'
        : 'Drag corner · arrows move · Delete removes'
      marker.setLngLat(
        mid
          ? midpoint(vertices[index], vertices[(index + 1) % vertices.length])
          : vertices[index],
      )
    })
  }
  function refresh() {
    const site = vertices ? polygonSite(vertices) : null
    show(site)
    syncHandles()
    onChange?.(site, {
      vertices: vertices?.length || 0,
      canUndo: history.length > 0,
    })
  }
  function clear() {
    release()
    first = null
    vertices = null
    history = []
    selectedVertex = -1
    awaitingCorner = false
    startPoint = null
    show(null)
    syncHandles()
    onChange?.(null, { vertices: 0, canUndo: false })
  }
  function hit(p) {
    if (!vertices) return null
    for (let i = 0; i < vertices.length; i++) {
      const v = map.project(vertices[i])
      if (Math.hypot(v.x - p.x, v.y - p.y) < 13)
        return { kind: 'vertex', index: i }
    }
    for (let i = 0; i < vertices.length; i++) {
      const v = map.project(
        midpoint(vertices[i], vertices[(i + 1) % vertices.length]),
      )
      if (Math.hypot(v.x - p.x, v.y - p.y) < 11)
        return { kind: 'mid', index: i }
    }
    return pointInPolygon(coordinates(p), vertices) ? { kind: 'move' } : null
  }
  function insert(index) {
    if (vertices.length >= 32) {
      onHint('Up to 32 corners per site.')
      return false
    }
    pushHistory()
    vertices.splice(
      index + 1,
      0,
      midpoint(vertices[index], vertices[(index + 1) % vertices.length]),
    )
    selectedVertex = index + 1
    refresh()
    return true
  }
  function removeVertex(index = selectedVertex) {
    if (!vertices || index < 0 || vertices.length <= 3) return
    const next = vertices.filter((_, i) => i !== index)
    if (validPolygon(next)) {
      pushHistory()
      vertices = next
      selectedVertex = -1
      refresh()
    }
  }
  function startMove(e) {
    if (!vertices || !enabled) return
    e.preventDefault()
    e.stopImmediatePropagation()
    pushHistory()
    before = copy(vertices)
    origin = coordinates(point(e))
    action = { kind: 'move' }
    selectedVertex = -1
    pointerId = e.pointerId
    canvas.setPointerCapture(pointerId)
    canvas.style.cursor = 'grabbing'
  }
  function down(e) {
    if (
      !enabled ||
      e.button !== 0 ||
      !e.isPrimary ||
      !map.getSource('draft-site')
    )
      return
    const control = e.target.closest?.('[data-boundary-action]')
    if (control?.dataset.boundaryAction === 'delete') return
    if (control?.dataset.boundaryAction === 'move') {
      startMove(e)
      return
    }
    e.preventDefault()
    e.stopImmediatePropagation()
    const p = point(e),
      ll = coordinates(p)
    if (vertices) {
      const target = hit(p)
      if (!target) {
        onHint('Drag a corner, use + to add a vertex, or choose a building.')
        return
      }
      if (target.kind === 'mid') {
        if (!insert(target.index)) return
        action = { kind: 'vertex', index: target.index + 1 }
      } else {
        pushHistory()
        action = target
      }
      selectedVertex = action.kind === 'vertex' ? action.index : -1
      before = copy(vertices)
      origin = ll
      syncHandles()
      canvas.style.cursor = action.kind === 'move' ? 'grabbing' : 'crosshair'
    } else {
      if (!inside(...ll)) return
      secondClick = awaitingCorner
      if (!awaitingCorner) {
        onStart()
        first = ll
      }
      action = { kind: 'draw' }
      startPoint = p
    }
    pointerId = e.pointerId
    canvas.setPointerCapture(pointerId)
  }
  function move(e) {
    if (!enabled) return
    const p = point(e)
    if (pointerId !== null && action?.kind !== 'draw') {
      e.preventDefault()
      e.stopImmediatePropagation()
      const ll = coordinates(p)
      const next =
        action.kind === 'move'
          ? translatePolygon(before, [ll[0] - origin[0], ll[1] - origin[1]])
          : copy(vertices)
      if (action.kind === 'vertex') next[action.index] = ll
      if (validPolygon(next)) {
        vertices = next
        refresh()
        onHint(
          `${areaLabel(polygonSite(vertices).area)} · drag corners or + handles to reshape`,
        )
      } else
        onHint('Keep the boundary inside the map and avoid crossing edges.')
      return
    }
    if (first) {
      e.preventDefault()
      e.stopImmediatePropagation()
      const site = selectedSite(first, coordinates(p))
      show(site)
      onHint(
        `${areaLabel(site.area)} · ${awaitingCorner ? 'Choose the opposite corner' : 'Release to edit the boundary'}`,
      )
      return
    }
    const target = hit(p)
    canvas.style.cursor =
      target?.kind === 'move'
        ? 'grab'
        : target?.kind === 'mid'
          ? 'copy'
          : target?.kind === 'vertex'
            ? 'crosshair'
            : vertices
              ? 'default'
              : 'crosshair'
  }
  function up(e) {
    if (!enabled || pointerId !== e.pointerId) return
    e.preventDefault()
    e.stopImmediatePropagation()
    const kind = action?.kind,
      p = point(e)
    release()
    if (kind !== 'draw') {
      canvas.style.cursor = 'grab'
      refresh()
      return
    }
    if (!first) return
    const moved = Math.hypot(p.x - startPoint.x, p.y - startPoint.y) > 6
    if (!moved && !secondClick) {
      awaitingCorner = true
      onHint('Now choose the opposite corner.')
      return
    }
    const site = selectedSite(first, coordinates(p))
    first = null
    awaitingCorner = false
    if (site.width < 3 || site.height < 3) {
      show(null)
      onHint('Choose an area at least 3 m wide and tall.')
      return
    }
    vertices = site.geometry.coordinates[0].slice(0, -1)
    refresh()
    onComplete(polygonSite(vertices), p)
    onHint('Drag corners to resize · + adds a vertex · drag inside to move')
  }
  const cancel = () => {
    if (!enabled || pointerId === null) return
    if (before && action?.kind !== 'draw') {
      vertices = copy(before)
      release()
      refresh()
    } else clear()
  }
  container.addEventListener('pointerdown', down, true)
  container.addEventListener('pointermove', move, true)
  container.addEventListener('pointerup', up, true)
  container.addEventListener('pointercancel', cancel)
  return {
    clear,
    startMove,
    getSite: () => (vertices ? polygonSite(vertices) : null),
    undo() {
      if (history.length) {
        vertices = history.pop()
        selectedVertex = -1
        refresh()
      }
    },
    removeVertex,
    edit(site) {
      clear()
      vertices = site.geometry.coordinates[0].slice(0, -1).map((p) => [...p])
      refresh()
    },
    setEnabled(value) {
      enabled = value
      clear()
      for (const h of [
        map.dragPan,
        map.boxZoom,
        map.doubleClickZoom,
        map.touchZoomRotate,
      ])
        value ? h.disable() : h.enable()
      map.touchZoomRotate.disableRotation()
      canvas.style.cursor = value ? 'crosshair' : 'grab'
      canvas.style.touchAction = value ? 'none' : ''
    },
    destroy() {
      clear()
      container.removeEventListener('pointerdown', down, true)
      container.removeEventListener('pointermove', move, true)
      container.removeEventListener('pointerup', up, true)
      container.removeEventListener('pointercancel', cancel)
    },
  }
}
