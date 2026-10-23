// Census supports JSONP for browser clients; its JSON endpoint does not expose
// CORS. No API key, backend proxy, or persisted address history is required.
export const looksLikeAddress = (query) =>
  /^\d+[a-z]?(?:-\d+)?\s+\S/i.test(query.trim())
export function censusQuery(query) {
  const address = query.trim()
  // Default an unqualified street address to Houston. Keep explicit city/ZIP
  // information intact so out-of-region addresses can still be rejected.
  return /,|\s\d{5}(?:-\d{4})?\s*$|\b(?:al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy|dc)\s*$|\b(?:texas|houston|sugar land|katy|pearland|woodlands|dallas|austin)\b/i.test(
    address,
  )
    ? address
    : `${address}, Houston, TX`
}
export function censusPlaces(data) {
  return (data?.result?.addressMatches || [])
    .map((match) => ({
      label: match.matchedAddress,
      address: match.matchedAddress,
      lng: match.coordinates?.x,
      lat: match.coordinates?.y,
      detail: 'US Census · Address-range location',
      zoom: 18,
      source: 'census',
    }))
    .filter(
      (p) => p.address && Number.isFinite(p.lng) && Number.isFinite(p.lat),
    )
}
let nextRequest = 0
export function lookupAddress(query, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const callback = `houstonCensusAddress${++nextRequest}`
    const script = document.createElement('script')
    const params = new URLSearchParams({
      address: censusQuery(query),
      benchmark: 'Public_AR_Current',
      format: 'jsonp',
      callback,
    })
    script.src = `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?${params}`
    script.referrerPolicy = 'no-referrer'
    let complete = false
    const finish = (error, data) => {
      if (complete) return
      complete = true
      clearTimeout(timeout)
      signal?.removeEventListener('abort', abort)
      script.remove()
      // A removed JSONP script can still arrive. Retain a harmless callback
      // briefly so an aborted request cannot update UI or throw a late error.
      window[callback] = () => {}
      setTimeout(() => {
        delete window[callback]
      }, 60000)
      if (error) reject(error)
      else resolve(censusPlaces(data))
    }
    const abort = () => finish(new DOMException('Aborted', 'AbortError'))
    const timeout = setTimeout(
      () => finish(new Error('Address service timed out')),
      10000,
    )
    window[callback] = (data) => finish(null, data)
    script.onerror = () => finish(new Error('Address service unavailable'))
    signal?.addEventListener('abort', abort, { once: true })
    document.head.append(script)
  })
}
