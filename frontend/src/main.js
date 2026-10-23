import './style.css'
import {
  Map as MapLibreMap,
  Marker,
  LngLat,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { HOUSTON, minimumZoom, constrainCenter, squareFeature } from './geo.js'
import { homeById } from './buildings.js'
import {
  DEMO_LAYERS,
  installDemoLayer,
  setDemoVisibility,
  loadSugarLandHomes,
  refreshHouseReveal,
  destroyHouseReveal,
} from './demo-layer.js'
import { areaLabel, installSiteLayers, highlightSite } from './sites.js'
import { createSiteSelector } from './site-selector.js'
import { updateLocation, setSearchedAddress } from './location.js'
import { createLocationSearch } from './search.js'
import { createPropertyDetails } from './property-details.js'
import {
  installListings,
  listingById,
  LISTING_LAYERS,
  renderMapKey,
} from './listings.js'
import { createDealsPanel } from './deals.js'
setWorkerUrl(workerUrl)

// CONFIG / STATE
const BUILDINGS_MIN_ZOOM = 12.25
const TYPES = {
  house: {
    label: 'House',
    symbol: '⌂',
    description: 'Single-family residential',
  },
  apartment: {
    label: 'Apartment',
    symbol: '▥',
    description: 'Multi-family residential',
  },
  factory: {
    label: 'Factory',
    symbol: '▲',
    description: 'Industrial development',
  },
  school: {
    label: 'School',
    symbol: '■',
    description: 'Education & community',
  },
}
const $ = (id) => document.getElementById(id)
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches
const buildingMarkers = new Map()
const userBuildings = []
let selectedId = null
let pending = null
let springing = false
let ready = false
let demoVisible = false
let buildMode = false
let siteSelector
let toastTimer
let editingId = null
let scopeTimer, scopeToastTimer
const propertyDetails = createPropertyDetails()
let selectedToolsMarker
const selectedTools = document.createElement('div')
selectedTools.className = 'boundary-tools'
selectedTools.setAttribute('role', 'toolbar')
selectedTools.setAttribute('aria-label', 'Selected boundary actions')
selectedTools.innerHTML =
  '<button type="button" data-selected-action="edit" aria-label="Edit selected boundary" title="Edit corners">✎</button><button type="button" class="boundary-drag" data-selected-action="move" aria-label="Move selected boundary" title="Drag to move boundary">✥</button><button type="button" class="boundary-delete" data-selected-action="delete" aria-label="Delete selected development" title="Delete development"><svg width="15" height="16" viewBox="0 0 18 20" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M2 5h14M6 5V2h6v3M4 5l1 13h8l1-13M7 8v7M11 8v7"/></svg></button>'
selectedTools.addEventListener('pointerdown', (event) => {
  event.stopPropagation()
  if (
    event.target.closest('[data-selected-action="move"]') &&
    event.button === 0
  ) {
    const b = buildingMarkers.get(selectedId)?.building
    if (b) {
      startEditing(b)
      siteSelector.startMove(event)
    }
  }
})
selectedTools.addEventListener('click', (event) => {
  event.stopPropagation()
  const action = event.target.closest('[data-selected-action]')?.dataset
    .selectedAction
  if (action === 'delete') deleteDevelopment(selectedId)
  else if (action === 'edit' || action === 'move')
    startEditing(buildingMarkers.get(selectedId)?.building)
})

// CAMERA: MapLibre retains an uncompressed requested transform during gestures.
// Only the rendered copy is compressed; never setCenter inside a drag listener.
function transformCamera(next) {
  if (springing) return {}
  const { lng, lat } = next.center
  const center = constrainCenter(
    [lng, lat],
    next.width,
    next.height,
    next.zoom,
    (map?.isMoving() ?? true) && !(map?.isZooming() ?? false),
  )
  return { center: new LngLat(center[0], center[1]) }
}
// Use a separate binding to permit callbacks during constructor initialization.
let map
map = new MapLibreMap({
  container: 'map',
  // PermitWatch look: dark basemap with glowing markers
  style: 'https://tiles.openfreemap.org/styles/dark',
  center: HOUSTON,
  zoom: minimumZoom(innerWidth, innerHeight),
  minZoom: minimumZoom(innerWidth, innerHeight),
  maxZoom: 18,
  renderWorldCopies: false,
  dragRotate: false,
  pitchWithRotate: false,
  maxPitch: 0,
  transformCameraUpdate: transformCamera,
  cancelPendingTileRequestsWhileZooming: false,
  attributionControl: { compact: true },
})
map.touchZoomRotate.disableRotation()
map.touchPitch.disable()
map.addControl(new NavigationControl({ showCompass: false }), 'bottom-right')
map.addControl(
  new ScaleControl({ unit: 'metric', maxWidth: 100 }),
  'bottom-left',
)
map
  .getCanvas()
  .setAttribute(
    'aria-label',
    'Greater Houston development map. Enable Build to select an area for development.',
  )

function springBack() {
  if (springing || map.isMoving()) return
  const current = map.getCenter()
  const target = constrainCenter(
    [current.lng, current.lat],
    map.getContainer().clientWidth,
    map.getContainer().clientHeight,
    map.getZoom(),
  )
  if (
    Math.abs(target[0] - current.lng) + Math.abs(target[1] - current.lat) <
    1e-8
  )
    return
  springing = true
  map.once('moveend', () => {
    springing = false
  })
  map.easeTo({
    center: target,
    duration: reducedMotion ? 0 : 520,
    easing: (t) => 1 - (1 - t) ** 4,
  })
}
map.on('moveend', springBack)
map.on('movestart', () => {
  $('build-menu').classList.add('hidden')
  $('app').classList.add('map-moving')
})
map.on('moveend', () => {
  $('app').classList.remove('map-moving')
  updateNearbyBuildings()
  updateLocation(map)
})
// Reset an interrupted spring before the next user camera update.
map.on('dragstart', () => {
  map.getCanvas().style.cursor = 'grabbing'
})
map.on('dragend', () => {
  map.getCanvas().style.cursor = buildMode ? 'crosshair' : 'grab'
})
map.on('mousedown', () => {
  springing = false
})
map.on('touchstart', () => {
  springing = false
})
map.on('resize', () => {
  map.setMinZoom(
    minimumZoom(
      map.getContainer().clientWidth,
      map.getContainer().clientHeight,
    ),
  )
  closeMenu()
  springBack()
})

function notifyScope(title, message) {
  clearTimeout(scopeTimer)
  clearTimeout(scopeToastTimer)
  $('app').classList.remove('scope-error')
  void $('app').offsetWidth
  $('app').classList.add('scope-error')
  $('scope-toast-title').textContent = title
  $('scope-toast-copy').textContent = message
  $('scope-toast').hidden = false
  scopeTimer = setTimeout(() => $('app').classList.remove('scope-error'), 1000)
  scopeToastTimer = setTimeout(() => {
    $('scope-toast').hidden = true
  }, 3000)
}
const locationSearch = createLocationSearch(map, {
  onNavigate: (place) => {
    setSearchedAddress(place)
    setBuildMode(false)
    selectBuilding(null)
  },
  onReject: notifyScope,
})
function zoomToBuilding(b) {
  if (!b) return
  selectBuilding(b.id)
  // Finish MapLibre's double-click handler before starting the custom flight.
  requestAnimationFrame(() =>
    map.easeTo({
      center: [b.lng, b.lat],
      zoom: Math.min(18, Math.max(17.5, map.getZoom() + 1.5)),
      duration: reducedMotion ? 0 : 750,
    }),
  )
}
function startEditing(b) {
  if (!b?.site) return
  setBuildMode(true)
  editingId = b.id
  siteSelector.edit(b.site)
  $('confirm-area').textContent = 'Save boundary'
  $('mode-hint').textContent =
    'Drag corners, use + to add vertices, or drag the move handle.'
}
function deleteDevelopment(id) {
  const index = userBuildings.findIndex((b) => b.id === id)
  if (index < 0) return
  const [building] = userBuildings.splice(index, 1)
  buildingMarkers.get(id)?.marker.remove()
  buildingMarkers.delete(id)
  if (editingId === id) setBuildMode(false)
  selectBuilding(null)
  syncProposedSites()
  $('proposal-count').textContent = userBuildings.length
  $('announcement').textContent =
    `${TYPES[building.type].label} and boundary deleted.`
}

// MARKER CACHE: one button and one span; no camera-time reconstruction.
function upsertBuilding(building) {
  let entry = buildingMarkers.get(building.id)
  if (!entry) {
    const el = document.createElement('button')
    el.type = 'button'
    el.className = `map-building ${building.demo ? 'is-demo' : 'is-user'}`
    el.innerHTML =
      '<span class="map-building-core" aria-hidden="true"><span></span></span>'
    el.dataset.buildingId = building.id
    el.style.setProperty('--pop-delay', `${(buildingMarkers.size % 7) * 45}ms`)
    const marker = new Marker({ element: el, anchor: 'bottom' })
      .setLngLat([building.lng, building.lat])
      .addTo(map)
    entry = { marker, el, building }
    buildingMarkers.set(building.id, entry)
    el.addEventListener('dblclick', (event) => {
      event.preventDefault()
      event.stopPropagation()
      zoomToBuilding(entry.building)
    })
    el.addEventListener('click', (event) => {
      event.stopPropagation()
      closeMenu()
      selectBuilding(building.id)
    })
  }
  entry.building = building
  entry.marker.setLngLat([building.lng, building.lat])
  entry.el.firstElementChild.firstElementChild.textContent =
    TYPES[building.type].symbol
  entry.el.title = `${building.demo ? 'Demo' : 'Proposed'} ${TYPES[building.type].label.toLowerCase()}`
  entry.el.setAttribute('aria-label', entry.el.title)
  entry.el.dataset.buildingType = building.type
  entry.el.classList.toggle('is-visible', !building.demo)
  entry.el.tabIndex = building.demo && !demoVisible ? -1 : 0
}
function selectBuilding(id) {
  if (selectedId) {
    buildingMarkers.get(selectedId)?.el.classList.remove('is-selected')
    buildingMarkers.get(selectedId)?.el.setAttribute('aria-pressed', 'false')
  }
  selectedId = id
  const entry = buildingMarkers.get(id)
  const b = entry?.building || homeById.get(id) || listingById.get(id)
  selectedToolsMarker?.remove()
  selectedToolsMarker = null
  if (b?.site && !buildMode)
    selectedToolsMarker = new Marker({
      element: selectedTools,
      anchor: 'bottom',
      offset: [0, -48],
    })
      .setLngLat(b.site.center)
      .addTo(map)
  $('selection').hidden = !b
  highlightSite(map, id)
  if (map.getLayer('demo-selected'))
    map.setFilter('demo-selected', [
      '==',
      ['get', 'id'],
      b?.demo || b?.existing ? id : '',
    ])
  if (!b) return
  propertyDetails.show(b)
  entry?.el.classList.add('is-selected')
  entry?.el.setAttribute('aria-pressed', 'true')
  if (b.listing) {
    showListing(b)
    return
  }
  $('selection-title').textContent =
    b.existing && b.address ? b.address : TYPES[b.type].label
  $('selection-description').textContent = b.existing
    ? `Sugar Land, TX · mapped ${b.building.replaceAll('_', ' ')}`
    : TYPES[b.type].description
  $('selection-coords').textContent =
    `${b.lat.toFixed(5)}° N · ${Math.abs(b.lng).toFixed(5)}° W`
  $('selection-kind').textContent = b.existing
    ? 'OPENSTREETMAP · MAPPED HOME'
    : b.demo
      ? 'EXISTING · DEMO'
      : 'PROPOSED DEVELOPMENT'
  $('selection-note').textContent = b.existing
    ? `${b.address ? 'Address as recorded in OpenStreetMap.' : 'No street address recorded for this building.'} Community-mapped building location; not a property listing.`
    : b.demo
      ? 'Illustrative house location, not a verified parcel.'
      : `${areaLabel(b.site.area)} development site. Highlighted area is your proposed footprint.`
  $('source-record').hidden = !b.existing
  if (b.existing) $('source-record').href = b.sourceUrl
  $('edit-site-button').hidden = !b.site
}
// Real listing scored by the model: honest out-of-fold fair price, not the demo estimate.
function showListing(b) {
  const fmt = (v, unit) => (v == null ? '—' : `${v.toLocaleString()}${unit}`)
  $('selection-title').textContent = b.address
  $('selection-description').textContent = [
    b.homeType.replaceAll('_', ' ').toLowerCase(),
    `${fmt(b.beds, ' bd')} · ${fmt(b.baths, ' ba')}`,
    fmt(b.sqft, ' sqft'),
    b.year ? `built ${b.year}` : null,
  ]
    .filter(Boolean)
    .join(' · ')
  $('selection-coords').textContent =
    `${b.lat.toFixed(5)}° N · ${Math.abs(b.lng).toFixed(5)}° W`
  $('selection-kind').textContent = `FOR SALE · ${b.deal}`
  $('selection-note').textContent =
    'Fair price is our model’s out-of-fold estimate (it never saw this home); range is a calibrated 80% interval. Not an appraisal.'
  $('source-record').hidden = !b.url
  if (b.url) $('source-record').href = b.url
  $('edit-site-button').hidden = true
}
function updateNearbyBuildings() {
  if (!ready || map.isMoving()) return
  const features = demoVisible
    ? map.queryRenderedFeatures({ layers: DEMO_LAYERS })
    : []
  const count = new Set(features.map((f) => f.properties.id)).size
  const mapped = new Set(
    features.filter((f) => f.properties.mapped).map((f) => f.properties.id),
  ).size
  $('tip-title').textContent = count
    ? `${mapped} mapped · ${count - mapped} demo homes`
    : 'Explore Sugar Land homes'
  $('tip-copy').textContent = count
    ? 'Select a pin to see its details and source.'
    : 'Explore jumps to real mapped homes.'
}
function updateZoomUI() {
  demoVisible = map.getZoom() >= BUILDINGS_MIN_ZOOM && $('demo-toggle').checked
  if (!demoVisible && homeById.has(selectedId)) selectBuilding(null)
  $('zoom-level').textContent = map.getZoom().toFixed(1)
  $('demo-status').textContent =
    map.getZoom() >= 16
      ? 'All available homes visible at this zoom'
      : 'More pins at zoom 14 · all homes at 16'
}
map.on('zoom', updateZoomUI)
map.on('idle', () => {
  updateNearbyBuildings()
  updateLocation(map)
})

// CONTEXTUAL PLACEMENT
function closeMenu() {
  $('build-menu').classList.add('hidden')
  pending = null
  siteSelector?.clear()
  if (buildMode)
    $('mode-hint').textContent = 'Drag an area, or click two opposite corners.'
}
function openMenu(site, point) {
  selectBuilding(null)
  pending = site
  $('build-location').textContent =
    `${areaLabel(site.area)} · ${Math.round(site.width)} × ${Math.round(site.height)} m`
  const menu = $('build-menu')
  menu.classList.remove('hidden')
  const { width, height } = menu.getBoundingClientRect()
  const gap = 14
  const w = map.getContainer().clientWidth,
    h = map.getContainer().clientHeight
  let x = point.x + gap,
    y = point.y - 24
  if (x + width > w - gap) x = point.x - width - gap
  if (y + height > h - gap) y = point.y - height - gap
  menu.style.left = `${Math.max(gap, Math.min(w - width - gap, x))}px`
  menu.style.top = `${Math.max(gap, Math.min(h - height - gap, y))}px`
  $('mode-hint').textContent = 'Area selected. Choose what to build.'
  menu.querySelector('.build-option').focus({ preventScroll: true })
}
siteSelector = createSiteSelector(map, {
  onDelete: () => {
    if (editingId) deleteDevelopment(editingId)
    else {
      siteSelector.clear()
      $('mode-hint').textContent = 'Boundary cleared. Draw a new area.'
    }
  },
  onComplete: (site) => {
    pending = site
    $('area-editor').hidden = false
  },
  onChange: (site, state) => {
    pending = site
    $('area-editor').hidden = !site
    $('build-menu').classList.add('hidden')
    if (site)
      $('editor-summary').textContent =
        `${state.vertices} corners · ${areaLabel(site.area)}`
    $('undo-area').disabled = !state.canUndo
  },
  onStart: () => {
    closeMenu()
    selectBuilding(null)
  },
  onHint: (text) => {
    $('mode-hint').textContent = text
  },
})
function setBuildMode(value) {
  buildMode = value
  editingId = null
  $('confirm-area').textContent = 'Choose building →'
  closeMenu()
  selectBuilding(null)
  siteSelector.setEnabled(value)
  $('app').classList.toggle('build-mode-active', value)
  $('build-mode-button').setAttribute('aria-pressed', String(value))
  $('mode-hint').textContent = value
    ? 'Drag an area, or click two opposite corners.'
    : 'Explore the map. Select Build to choose an area.'
}
map.on('click', (event) => {
  if (!ready || buildMode) return
  const layers = [
    ...DEMO_LAYERS,
    ...LISTING_LAYERS,
    'proposed-sites-fill',
  ].filter((id) => map.getLayer(id))
  const hit = map.queryRenderedFeatures(event.point, { layers })[0]
  selectBuilding(hit?.properties.id || null)
})
map.on('dblclick', (event) => {
  if (!ready || buildMode) return
  const hits = map.queryRenderedFeatures(event.point)
  const home = hits.find((f) =>
    [
      ...DEMO_LAYERS,
      ...LISTING_LAYERS,
      'demo-selected',
      'proposed-sites-fill',
    ].includes(f.layer.id),
  )
  if (home) {
    event.preventDefault()
    zoomToBuilding(
      buildingMarkers.get(home.properties.id)?.building ||
        homeById.get(home.properties.id) ||
        listingById.get(home.properties.id),
    )
    return
  }
  const icon = hits.find(
    (f) =>
      f.layer.type === 'symbol' &&
      f.layer.layout?.['icon-image'] &&
      f.geometry.type === 'Point',
  )
  if (icon) {
    event.preventDefault()
    requestAnimationFrame(() =>
      map.easeTo({
        center: icon.geometry.coordinates,
        zoom: Math.min(18, Math.max(17.5, map.getZoom() + 1.5)),
        duration: reducedMotion ? 0 : 750,
      }),
    )
  }
})
map.on('mousemove', (event) => {
  if (buildMode) return
  const hits = ready
    ? map.queryRenderedFeatures(event.point, {
        layers: [...DEMO_LAYERS, 'proposed-sites-fill'],
      })
    : []
  map.getCanvas().style.cursor = map.isMoving()
    ? 'grabbing'
    : hits.length
      ? 'pointer'
      : 'grab'
})
function syncProposedSites() {
  map.getSource('proposed-sites').setData({
    type: 'FeatureCollection',
    features: userBuildings.map((b) => ({
      type: 'Feature',
      id: b.id,
      properties: { id: b.id, type: b.type },
      geometry: b.site.geometry,
    })),
  })
}
$('undo-area').addEventListener('click', () => siteSelector.undo())
$('redraw-area').addEventListener('click', () => {
  siteSelector.clear()
  $('mode-hint').textContent = 'Drag a new area, or click two opposite corners.'
})
$('confirm-area').addEventListener('click', () => {
  const site = siteSelector.getSite()
  if (!site) return
  if (editingId) {
    const b = userBuildings.find((b) => b.id === editingId)
    b.site = site
    b.lng = site.center[0]
    b.lat = site.center[1]
    upsertBuilding(b)
    syncProposedSites()
    setBuildMode(false)
    selectBuilding(b.id)
  } else openMenu(site, map.project(site.center))
})
$('edit-site-button').addEventListener('click', () =>
  startEditing(buildingMarkers.get(selectedId)?.building),
)
$('close-build-menu').addEventListener('click', closeMenu)
for (const button of document.querySelectorAll('.build-option'))
  button.addEventListener('click', () => {
    if (!pending || !TYPES[button.dataset.building]) return
    const b = {
      id: crypto.randomUUID(),
      type: button.dataset.building,
      lng: pending.center[0],
      lat: pending.center[1],
      site: pending,
      demo: false,
    }
    userBuildings.push(b)
    upsertBuilding(b)
    syncProposedSites()
    setBuildMode(false)
    selectBuilding(b.id)
    $('proposal-count').textContent = userBuildings.length
    if (!reducedMotion)
      $('proposal-count').animate(
        [
          { transform: 'scale(1)' },
          { transform: 'scale(1.5)' },
          { transform: 'scale(1)' },
        ],
        { duration: 420, easing: 'ease-out' },
      )
    clearTimeout(toastTimer)
    $('toast-title').textContent = `${TYPES[b.type].label} added!`
    $('build-toast').hidden = false
    toastTimer = setTimeout(() => {
      $('build-toast').hidden = true
    }, 2800)
    $('announcement').textContent =
      `${TYPES[b.type].label} placed. ${userBuildings.length} proposed developments.`
    buildingMarkers.get(b.id).el.focus({ preventScroll: true })
  })
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    setBuildMode(false)
    $('layers-panel').hidden = true
    $('layers-button').setAttribute('aria-expanded', 'false')
    deals.setOpen(false)
    map.getCanvas().focus()
  }
})
$('build-mode-button').addEventListener('click', () => setBuildMode(!buildMode))
$('close-selection').addEventListener('click', () => selectBuilding(null))
$('home-button').addEventListener('click', () => {
  setBuildMode(false)
  map.easeTo({
    center: HOUSTON,
    zoom: map.getMinZoom(),
    duration: reducedMotion ? 0 : 700,
  })
})
$('neighborhood-button').addEventListener('click', () => {
  setBuildMode(false)
  map.easeTo({
    center: [-95.6046, 29.6508],
    zoom: 16.5,
    duration: reducedMotion ? 0 : 900,
  })
})
$('layers-button').addEventListener('click', () => {
  $('layers-panel').hidden = !$('layers-panel').hidden
  $('layers-button').setAttribute(
    'aria-expanded',
    String(!$('layers-panel').hidden),
  )
})
// Fair-price model: Deals panel (filters + what's in view) and the listings layer toggle.
const deals = createDealsPanel(map, {
  onPick: (id) => zoomToBuilding(listingById.get(id)),
})
function setListingsVisible(visible) {
  for (const id of LISTING_LAYERS)
    if (map.getLayer(id))
      map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
  $('map-key').hidden = !visible
}
$('listings-toggle').addEventListener('change', () =>
  setListingsVisible($('listings-toggle').checked),
)
$('demo-toggle').addEventListener('change', () => {
  setDemoVisibility(map, $('demo-toggle').checked)
  updateZoomUI()
  updateNearbyBuildings()
})
$('planning-toggle').addEventListener('change', () => {
  if (map.getLayer('planning-lines'))
    map.setLayoutProperty(
      'planning-lines',
      'visibility',
      $('planning-toggle').checked ? 'visible' : 'none',
    )
})

// PLAY AREA: GPU mask, feather and dotted edge, installed before GIS requests.
map.on('style.load', () => {
  const square = squareFeature()
  map.addSource('play-square', { type: 'geojson', data: square })
  map.addSource('outside-world', {
    type: 'geojson',
    data: {
      type: 'Feature',
      properties: {},
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-180, -85],
            [180, -85],
            [180, 85],
            [-180, 85],
            [-180, -85],
          ],
          square.geometry.coordinates[0].slice().reverse(),
        ],
      },
    },
  })
  map.addLayer({
    id: 'outside-gray',
    type: 'fill',
    source: 'outside-world',
    paint: { 'fill-color': '#bcbcbc', 'fill-opacity': 0.9 },
  })
  map.addLayer({
    id: 'play-feather',
    type: 'line',
    source: 'play-square',
    paint: {
      'line-color': '#9f9f9f',
      'line-width': 6,
      'line-blur': 5,
      'line-opacity': 0.18,
    },
  })
  map.addLayer({
    id: 'play-border',
    type: 'line',
    source: 'play-square',
    paint: {
      'line-color': '#737373',
      'line-width': 1.2,
      'line-dasharray': [1, 3],
      'line-opacity': 0.6,
    },
  })
  installSiteLayers(map, 'outside-gray')
  installDemoLayer(map, 'outside-gray')
  setDemoVisibility(map, $('demo-toggle').checked)
  ready = true
  $('map-status').textContent = 'Ready to explore'
  updateZoomUI()
  updateNearbyBuildings()
  loadSugarLandHomes(map)
    .then((data) => {
      $('map-status').textContent =
        `${data.homes.length.toLocaleString()} Sugar Land homes mapped`
      map.once('idle', refreshHouseReveal)
    })
    .catch((error) => {
      console.warn(error)
      $('map-status').textContent = 'Mapped homes unavailable · demo map ready'
    })
  installListings(map)
    .then(() => {
      deals.applyFilter()
      deals.refresh()
      renderMapKey($('map-key'))
      setListingsVisible($('listings-toggle').checked)
    })
    .catch((error) => console.warn(error))
  loadPlanning()
})

// GIS: optional and independent of core map readiness.
async function loadPlanning() {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: 'OBJECTID',
    returnGeometry: 'true',
    outSR: '4326',
    f: 'geojson',
    maxAllowableOffset: '0.0001',
  })
  try {
    const response = await fetch(
      `https://mycity2.houstontx.gov/gisweb01/rest/services/HoustonMap/Administrative_Boundary/MapServer/3/query?${params}`,
      { signal: AbortSignal.timeout(15000) },
    )
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    if (
      data.type !== 'FeatureCollection' ||
      !Array.isArray(data.features) ||
      data.exceededTransferLimit
    )
      throw new Error('Incomplete GIS response')
    map.addSource('planning', { type: 'geojson', data, tolerance: 0.5 })
    map.addLayer(
      {
        id: 'planning-lines',
        type: 'line',
        source: 'planning',
        minzoom: 11,
        layout: {
          visibility: $('planning-toggle').checked ? 'visible' : 'none',
        },
        paint: {
          'line-color': '#858585',
          'line-width': 0.8,
          'line-dasharray': [1, 3],
          'line-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            11,
            0,
            12,
            0.18,
            15,
            0.35,
          ],
        },
      },
      'outside-gray',
    )
    $('planning-status').textContent = 'City of Houston · Super Neighborhoods'
  } catch (error) {
    console.warn('Planning boundaries unavailable', error)
    $('planning-status').textContent =
      'Planning data unavailable · map still usable'
    $('planning-toggle').disabled = true
  }
}
const slowTimer = setTimeout(() => {
  if (!ready)
    $('map-status').textContent =
      'Map is taking longer to load. Check your connection.'
}, 12000)
map.once('idle', () => clearTimeout(slowTimer))
map.on('error', (event) => {
  console.warn('Map resource:', event.error?.message)
})
if (import.meta.hot)
  import.meta.hot.dispose(() => {
    clearTimeout(slowTimer)
    clearTimeout(toastTimer)
    clearTimeout(scopeTimer)
    clearTimeout(scopeToastTimer)
    locationSearch.destroy()
    propertyDetails.destroy()
    selectedToolsMarker?.remove()
    siteSelector.destroy()
    destroyHouseReveal()
    map.remove()
  })
