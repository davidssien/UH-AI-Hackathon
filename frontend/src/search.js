import { HOUSTON, PLAY_BOUNDS, inside } from './geo.js'
import { homeById } from './buildings.js'
import { looksLikeAddress, lookupAddress } from './address-search.js'

export const normalizeQuery = (value) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
export const inSearchScope = (place) =>
  Number.isFinite(place?.lng) &&
  Number.isFinite(place?.lat) &&
  inside(place.lng, place.lat)
const places = [
  ['Houston, Texas', -95.3698, 29.7604, 13],
  ['Sugar Land, Texas', -95.6349, 29.6197, 14],
  ['Katy, Texas', -95.8244, 29.7858, 14],
  ['Pearland, Texas', -95.286, 29.5636, 14],
  ['The Woodlands, Texas', -95.4613, 30.1658, 14],
  ['University of Houston', -95.3422, 29.7199, 16],
  ['Rice University', -95.4018, 29.7174, 16],
  ['Texas Medical Center', -95.3975, 29.7079, 15],
  ['Hermann Park', -95.3892, 29.7135, 16],
  ['Memorial Park', -95.4335, 29.7675, 15],
  ['Downtown Houston', -95.362, 29.757, 15],
  ['Montrose, Houston', -95.391, 29.744, 15],
  ['Houston Heights', -95.399, 29.798, 15],
].map(([label, lng, lat, zoom]) => ({
  label,
  lng,
  lat,
  zoom,
  detail: 'Greater Houston · Place',
}))
export function localSuggestions(query) {
  const q = normalizeQuery(query)
  const homes = [...homeById.values()]
    .filter((h) => h.existing && h.address)
    .map((h) => ({
      ...h,
      label: h.address,
      detail: 'Sugar Land · Mapped address',
      zoom: 18,
    }))
  const seen = new Set()
  return [...places, ...homes]
    .filter((p) => {
      const key = normalizeQuery(p.label)
      if (!inSearchScope(p) || (q && !key.includes(q)) || seen.has(key))
        return false
      seen.add(key)
      return true
    })
    .sort(
      (a, b) =>
        Number(normalizeQuery(b.label).startsWith(q)) -
        Number(normalizeQuery(a.label).startsWith(q)),
    )
    .slice(0, 6)
}
export function photonPlace(feature) {
  const p = feature.properties || {},
    [lng, lat] = feature.geometry?.coordinates || []
  const address = [p.housenumber, p.street].filter(Boolean).join(' ')
  return {
    lng,
    lat,
    label: address || p.name || p.city || p.district || 'Mapped location',
    address:
      p.housenumber && p.street
        ? [address, p.city || p.district, p.state, p.postcode]
            .filter(Boolean)
            .join(', ')
        : null,
    detail: [
      ...new Set(
        [p.name && address, p.city || p.district, p.state].filter(Boolean),
      ),
    ].join(' · '),
    zoom: p.housenumber ? 18 : p.street || p.osm_key === 'amenity' ? 16.5 : 14,
  }
}
export function createLocationSearch(map, { onNavigate, onReject }) {
  const $ = (id) => document.getElementById(id)
  const heading = $('location-heading'),
    trigger = $('location-trigger'),
    form = $('location-search'),
    input = $('location-input'),
    list = $('location-results'),
    status = $('search-status')
  let results = [],
    active = -1,
    timer,
    controller,
    serial = 0,
    opened = false,
    disposed = false,
    currentPlace = null,
    currentController,
    lastDestination = null
  const cache = new Map()
  const addressCache = new Map()
  const currentButton = $('current-address')
  const nearCenter = (p, center, meters) =>
    p &&
    Math.hypot((p.lng - center.lng) * 96700, (p.lat - center.lat) * 110574) <
      meters
  function showCurrent(place, detail) {
    currentPlace = { ...place, zoom: 18 }
    $('current-address-value').textContent = detail
    currentButton.title = detail
  }
  async function updateCurrent() {
    currentController?.abort()
    currentController = new AbortController()
    const request = currentController
    const center = map.getCenter()
    const point = { lng: center.lng, lat: center.lat }
    const home = [...homeById.values()]
      .filter((h) => h.existing && h.address && nearCenter(h, center, 25))
      .sort(
        (a, b) =>
          Math.hypot(
            (a.lng - center.lng) * 96700,
            (a.lat - center.lat) * 110574,
          ) -
          Math.hypot(
            (b.lng - center.lng) * 96700,
            (b.lat - center.lat) * 110574,
          ),
      )[0]
    const known =
      nearCenter(lastDestination, center, 20) && lastDestination.address
        ? lastDestination
        : home
    if (known) {
      showCurrent(
        { ...point, label: known.address, address: known.address },
        `${known.address} · ${known === lastDestination ? 'Map center' : 'Near map center'}`,
      )
      return
    }
    const coords = `${center.lat.toFixed(5)}, ${center.lng.toFixed(5)}`
    showCurrent(
      { ...point, label: 'Current map center' },
      `Finding address at map center… · ${coords}`,
    )
    try {
      const params = new URLSearchParams({
        lon: center.lng,
        lat: center.lat,
        radius: 0.05,
        limit: 5,
        lang: 'en',
      })
      const key = `reverse:${center.lng.toFixed(5)},${center.lat.toFixed(5)}`
      let found = cache.get(key)
      if (!found) {
        const response = await fetch(
          `https://photon.komoot.io/reverse?${params}`,
          {
            signal: AbortSignal.any([
              request.signal,
              AbortSignal.timeout(7000),
            ]),
          },
        )
        if (!response.ok) throw new Error('Address unavailable')
        found = (await response.json()).features.map(photonPlace)
        cache.set(key, found)
      }
      if (!opened || request.signal.aborted) return
      const match = found.find((p) => p.address && nearCenter(p, center, 50))
      if (match)
        showCurrent(
          { ...point, label: match.address, address: match.address },
          `${match.address} · Near map center`,
        )
      else
        showCurrent(
          { ...point, label: 'Current map center' },
          `No house address mapped here · ${coords}`,
        )
    } catch {
      if (opened && !request.signal.aborted)
        showCurrent(
          { ...point, label: 'Current map center' },
          `Address unavailable · ${coords}`,
        )
    }
  }
  async function addresses(query, signal) {
    const key = normalizeQuery(query)
    if (addressCache.has(key)) return addressCache.get(key)
    const found = await lookupAddress(query, signal)
    addressCache.set(key, found)
    return found
  }
  currentButton.addEventListener('click', () => {
    if (currentPlace) go(currentPlace)
  })
  async function lookup(query, bounded, signal) {
    const key = `${bounded}:${normalizeQuery(query)}`
    if (cache.has(key)) return cache.get(key)
    const params = new URLSearchParams({
      q: query,
      limit: bounded ? 7 : 1,
      lang: 'en',
    })
    if (bounded) {
      params.set('bbox', [...PLAY_BOUNDS[0], ...PLAY_BOUNDS[1]].join(','))
      params.set('lon', HOUSTON[0])
      params.set('lat', HOUSTON[1])
    }
    const response = await fetch(`https://photon.komoot.io/api/?${params}`, {
      signal,
    })
    if (!response.ok) throw new Error('Search unavailable')
    const data = await response.json()
    const found = (data.features || [])
      .map(photonPlace)
      .filter((p) => Number.isFinite(p.lng) && Number.isFinite(p.lat))
    cache.set(key, found)
    return found
  }
  function render(found, message = '') {
    results = found.filter(inSearchScope).slice(0, 6)
    active = -1
    input.removeAttribute('aria-activedescendant')
    list.replaceChildren()
    results.forEach((place, index) => {
      const item = document.createElement('li')
      item.id = `location-result-${index}`
      item.role = 'option'
      item.setAttribute('aria-selected', 'false')
      const title = document.createElement('b'),
        detail = document.createElement('small')
      title.textContent = place.label
      detail.textContent = place.detail || 'Greater Houston'
      item.append(title, detail)
      item.addEventListener('pointerdown', (event) => event.preventDefault())
      item.addEventListener('click', () => go(place))
      list.append(item)
    })
    status.textContent =
      message ||
      (results.length
        ? '↑ ↓ to choose · Enter to go · Esc to close'
        : 'No matching places inside Greater Houston.')
  }
  function close() {
    opened = false
    serial++
    clearTimeout(timer)
    controller?.abort()
    currentController?.abort()
    form.hidden = true
    trigger.hidden = false
    heading.classList.remove('is-searching')
    input.setAttribute('aria-expanded', 'false')
    trigger.setAttribute('aria-expanded', 'false')
  }
  function open() {
    if (opened) return
    opened = true
    form.hidden = false
    trigger.hidden = true
    heading.classList.add('is-searching')
    input.value = ''
    input.setAttribute('aria-expanded', 'true')
    trigger.setAttribute('aria-expanded', 'true')
    render(
      localSuggestions(''),
      'Search places, streets or addresses · Greater Houston only',
    )
    input.focus()
    updateCurrent()
  }
  function go(place) {
    if (!inSearchScope(place)) {
      reject()
      return
    }
    lastDestination = place
    close()
    onNavigate(place)
    map.easeTo({
      center: [place.lng, place.lat],
      zoom: place.zoom || 16,
      duration: matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 0
        : 950,
    })
  }
  function reject() {
    status.textContent =
      'Out of scope · Choose a location inside Greater Houston.'
    onReject(
      'Out of scope',
      'Choose a location inside the Greater Houston map area.',
    )
  }
  async function suggest() {
    const query = input.value.trim(),
      token = ++serial
    controller?.abort()
    const local = localSuggestions(query)
    render(
      local,
      query.length < 3
        ? 'Type at least 3 characters · Greater Houston only'
        : 'Searching Greater Houston…',
    )
    if (query.length < 3) return
    controller = new AbortController()
    const request = controller
    timer = setTimeout(
      async () => {
        try {
          const isAddress = looksLikeAddress(query)
          const remote = isAddress
            ? await addresses(query, request.signal)
            : await lookup(
                query,
                true,
                AbortSignal.any([request.signal, AbortSignal.timeout(7000)]),
              )
          if (disposed || !opened || token !== serial) return
          const found = [
            ...local,
            ...remote.filter(
              (p) =>
                !local.some(
                  (l) => normalizeQuery(l.label) === normalizeQuery(p.label),
                ),
            ),
          ]
          render(found)
        } catch (error) {
          if (token === serial && opened && error.name !== 'AbortError')
            render(
              local,
              'Online search unavailable. Try a suggested place or mapped address.',
            )
        }
      },
      looksLikeAddress(query) ? 750 : 450,
    )
  }
  input.addEventListener('input', () => {
    clearTimeout(timer)
    suggest()
  })
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      close()
      trigger.focus()
      return
    }
    if (!['ArrowDown', 'ArrowUp'].includes(event.key) || !results.length) return
    event.preventDefault()
    active =
      (active + (event.key === 'ArrowDown' ? 1 : -1) + results.length) %
      results.length
    Array.from(list.children).forEach((item, i) =>
      item.setAttribute('aria-selected', String(i === active)),
    )
    input.setAttribute('aria-activedescendant', `location-result-${active}`)
    list.children[active].scrollIntoView({ block: 'nearest' })
  })
  form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const query = input.value.trim()
    if (!query) return
    if (active >= 0 && results[active]) return go(results[active])
    const local = localSuggestions(query)
    const exact = local.find(
      (p) =>
        normalizeQuery(p.label) === normalizeQuery(query) ||
        normalizeQuery(p.label).replace(/ (texas|houston)$/, '') ===
          normalizeQuery(query),
    )
    if (exact) return go(exact)
    clearTimeout(timer)
    controller?.abort()
    const token = ++serial
    controller = new AbortController()
    status.textContent = 'Checking location…'
    try {
      // Resolve the submitted name globally so an out-of-region city cannot
      // silently become a similarly named Houston street.
      const isAddress = looksLikeAddress(query)
      const found = isAddress
        ? await addresses(query, controller.signal)
        : await lookup(
            query,
            false,
            AbortSignal.any([controller.signal, AbortSignal.timeout(7000)]),
          )
      if (!opened || token !== serial) return
      if (!found.length) {
        status.textContent = looksLikeAddress(query)
          ? 'Address not found. Include the house number, street, city and ZIP code.'
          : 'Location not found. Choose a suggestion or try a fuller address.'
        return
      }
      if (!inSearchScope(found[0])) return reject()
      go(found[0])
    } catch (error) {
      if (token === serial && opened && error.name !== 'AbortError')
        status.textContent =
          'Search unavailable. Choose a local suggestion or try again.'
    }
  })
  trigger.addEventListener('click', open)
  $('close-search').addEventListener('click', () => {
    close()
    trigger.focus()
  })
  const outside = (event) => {
    if (opened && !heading.contains(event.target)) close()
  }
  document.addEventListener('pointerdown', outside)
  const moved = () => {
    if (opened) updateCurrent()
  }
  map.on('moveend', moved)
  return {
    close,
    destroy() {
      disposed = true
      close()
      document.removeEventListener('pointerdown', outside)
      map.off('moveend', moved)
    },
  }
}
