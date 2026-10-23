// "Deals" dock panel: filter the model-scored listings layer by deal / max price, and summarize what's in view.
import { DEAL_COLORS, listingById, listingsMeta } from './listings.js'

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

export function dealFilter(deal, max) {
  const parts = ['all']
  if (deal) parts.push(['==', ['get', 'deal'], deal])
  if (max) parts.push(['<=', ['get', 'list'], max])
  return parts.length > 1 ? parts : null
}

export function passes(l, deal, max) {
  return (!deal || l.deal === deal) && (!max || l.list <= max)
}

export function summarize(listings) {
  const count = { UNDERPRICED: 0, FAIR: 0, OVERPRICED: 0 }
  for (const l of listings) count[l.deal]++
  const prices = listings.map((l) => l.list).sort((a, b) => a - b)
  const middle = Math.floor(prices.length / 2)
  const median = prices.length
    ? prices.length % 2
      ? prices[middle]
      : (prices[middle - 1] + prices[middle]) / 2
    : null
  return { total: listings.length, count, median }
}

export function createDealsPanel(map, { onPick, onFilter, onOpen }) {
  const $ = (id) => document.getElementById(id)
  const panel = $('deals-panel')
  const button = $('deals-button')
  let deal = ''
  let max = 0
  let unavailable = false

  function applyFilter() {
    onFilter(deal, max)
  }

  function refresh() {
    if (panel.hidden) return
    if (!listingsMeta) {
      $('deals-market').replaceChildren()
      $('deals-list').textContent = unavailable
        ? 'Model data unavailable. Reload to retry; historical pins still work.'
        : 'Loading saved model estimates…'
      return
    }
    if (listingsMeta)
      $('deals-mdape').textContent = `${listingsMeta.homes_mdape}%`
    const b = map.getBounds()
    const inView = []
    for (const l of listingById.values())
      if (b.contains([l.lng, l.lat]) && passes(l, deal, max)) inView.push(l)
    const s = summarize(inView)
    const market = $('deals-market')
    market.replaceChildren()
    const head = document.createElement('div')
    head.className = 'deals-stats'
    head.innerHTML = `<div><b>${s.total.toLocaleString()}</b><small>homes in view</small></div><div><b>${s.median ? money.format(s.median) : '—'}</b><small>median historical ask</small></div>`
    const bar = document.createElement('div')
    bar.className = 'deals-bar'
    for (const k of ['UNDERPRICED', 'FAIR', 'OVERPRICED']) {
      const seg = document.createElement('span')
      seg.style.width = s.total ? `${(s.count[k] / s.total) * 100}%` : '0'
      seg.style.background = DEAL_COLORS[k]
      bar.append(seg)
    }
    const legend = document.createElement('p')
    legend.className = 'deals-legend'
    legend.textContent = `${s.count.UNDERPRICED} underpriced · ${s.count.FAIR} fair · ${s.count.OVERPRICED} overpriced`
    market.append(head, bar, legend)

    const list = $('deals-list')
    list.replaceChildren()
    const best = inView
      .filter((l) => (deal ? true : l.deal === 'UNDERPRICED'))
      .sort((a, c) => a.gap - c.gap)
      .slice(0, 12)
    if (!best.length) {
      const empty = document.createElement('p')
      empty.className = 'deals-empty'
      empty.textContent = inView.length
        ? 'No underpriced homes in view. Zoom out or pan.'
        : 'No scored historical homes match in this view. Zoom out, pan, or reset filters.'
      list.append(empty)
      return
    }
    for (const l of best) {
      const row = document.createElement('button')
      row.type = 'button'
      row.className = 'deal-row'
      row.style.borderLeftColor = DEAL_COLORS[l.deal]
      const left = document.createElement('span')
      const addr = document.createElement('b')
      addr.textContent = l.address || 'Address unavailable'
      const spec = document.createElement('small')
      spec.textContent = [
        l.beds != null ? `${l.beds} bd` : null,
        l.baths != null ? `${l.baths} ba` : null,
        l.sqft ? `${l.sqft.toLocaleString()} sqft` : null,
      ]
        .filter(Boolean)
        .join(' · ')
      left.append(addr, spec)
      const right = document.createElement('span')
      right.className = 'deal-row-right'
      const price = document.createElement('b')
      price.textContent = money.format(l.list)
      const gap = document.createElement('small')
      gap.textContent = `${l.gap > 0 ? '+' : ''}${l.gap.toFixed(1)}% vs fair`
      gap.style.color = DEAL_COLORS[l.deal]
      right.append(price, gap)
      row.append(left, right)
      row.addEventListener('click', () => onPick(l.id))
      list.append(row)
    }
  }

  function setOpen(open) {
    panel.hidden = !open
    button.setAttribute('aria-expanded', String(open))
    if (open) {
      onOpen?.()
      refresh()
    }
  }

  button.addEventListener('click', () => setOpen(panel.hidden))
  $('close-deals').addEventListener('click', () => setOpen(false))
  for (const chip of panel.querySelectorAll('.deal-chip'))
    chip.addEventListener('click', () => {
      deal = chip.dataset.deal || ''
      for (const c of panel.querySelectorAll('.deal-chip'))
        c.setAttribute('aria-pressed', String(c === chip))
      applyFilter()
      refresh()
    })
  $('deal-max').addEventListener('change', (e) => {
    max = Number(e.target.value) || 0
    applyFilter()
    refresh()
  })
  map.on('moveend', refresh)
  return {
    refresh,
    applyFilter,
    setOpen,
    isOpen: () => !panel.hidden,
    setUnavailable() {
      unavailable = true
      refresh()
    },
  }
}
