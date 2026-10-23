// Fair-price model features for a selected real listing, rendered inside David's selection card:
// verdict + calibrated 80% range bar, top SHAP factors, true monthly cost (rate = user input), offer drafter.
import { DEAL_COLORS } from './listings.js'

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})
const fmt = (v) => money.format(Math.round(v))

const VERDICT = {
  UNDERPRICED: (gap) =>
    `Listed ${gap} below our fair price and under the fair range. Worth a closer look; check condition and inspection.`,
  FAIR: () => 'Priced within the fair range for a home like this here.',
  OVERPRICED: (gap) =>
    `Listed ${gap} above our fair price and above the fair range. Room to negotiate.`,
}

export function monthlyCost(price, { rate, down, tax, ins }) {
  const loan = price * (1 - down / 100)
  const r = rate / 100 / 12
  const n = 360
  const pi = r === 0 ? loan / n : (loan * r * (1 + r) ** n) / ((1 + r) ** n - 1)
  const parts = {
    pi,
    tax: (price * tax) / 100 / 12,
    ins: (price * ins) / 100 / 12,
    pmi: down < 20 ? (loan * 0.005) / 12 : 0,
  }
  return {
    ...parts,
    total: parts.pi + parts.tax + parts.ins + parts.pmi,
    cash: (price * down) / 100,
  }
}

export function suggestedOffer(l) {
  const raw =
    l.deal === 'UNDERPRICED'
      ? l.list
      : l.deal === 'OVERPRICED'
        ? l.fair
        : Math.min(l.list, Math.max(l.p10, l.fair * 0.97))
  return Math.round(raw / 1000) * 1000
}

function el(tag, cls, text) {
  const e = document.createElement(tag)
  if (cls) e.className = cls
  if (text != null) e.textContent = text
  return e
}

function numberField(label, value, step, suffix, onInput) {
  const wrap = el('label', 'mc-field')
  wrap.append(el('span', null, label))
  const row = el('span', 'mc-input')
  const input = document.createElement('input')
  input.type = 'number'
  input.min = '0'
  input.step = String(step)
  input.value = String(value)
  input.inputMode = 'decimal'
  input.addEventListener('input', () =>
    onInput(Math.max(0, Number(input.value) || 0)),
  )
  row.append(input, el('small', null, suffix))
  wrap.append(row)
  return wrap
}

// Inputs persist across homes during the visit (rate is always the user's own input).
const inputs = { rate: 6.5, down: 10, tax: 2.2, ins: 1.0, income: 65000 }

export function renderModelExtras(container, l) {
  container.replaceChildren()
  container.hidden = false

  // --- verdict + range bar
  const verdict = el('div', 'mc-block')
  const lo = Math.min(l.p10, l.list) * 0.97
  const hi = Math.max(l.p90, l.list) * 1.03
  const x = (v) => `${(((v - lo) / (hi - lo)) * 100).toFixed(2)}%`
  const bar = el('div', 'mc-range')
  bar.setAttribute('aria-hidden', 'true')
  const band = el('span', 'mc-band')
  band.style.left = x(l.p10)
  band.style.width = `calc(${x(l.p90)} - ${x(l.p10)})`
  const fair = el('span', 'mc-fair')
  fair.style.left = x(l.fair)
  const list = el('span', 'mc-list')
  list.style.left = x(l.list)
  list.style.background = DEAL_COLORS[l.deal]
  bar.append(band, fair, list)
  const badge = el('span', `mc-badge ${l.deal.toLowerCase()}`, l.deal)
  verdict.append(
    badge,
    bar,
    el(
      'p',
      'mc-legend',
      `▮ list ${fmt(l.list)}   ● fair ${fmt(l.fair)}   80% range ${fmt(l.p10)} – ${fmt(l.p90)}`,
    ),
    el('p', 'mc-verdict', VERDICT[l.deal](`${Math.abs(l.gap).toFixed(1)}%`)),
  )
  container.append(verdict)

  // --- why this price (SHAP)
  if (l.factors?.length) {
    const why = el('div', 'mc-block')
    why.append(el('h3', 'mc-h', 'Why this price'))
    const max = Math.max(...l.factors.map(([, p]) => Math.abs(p)), 1)
    for (const [label, pct] of l.factors) {
      const row = el('div', 'mc-factor')
      const top = el('div', 'mc-factor-top')
      const val = el('b', null, `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`)
      val.style.color =
        pct >= 0 ? DEAL_COLORS.UNDERPRICED : DEAL_COLORS.OVERPRICED
      top.append(el('span', null, label), val)
      const track = el('div', 'mc-track')
      const fill = el('span')
      fill.style.width = `${(Math.abs(pct) / max) * 100}%`
      fill.style.background = val.style.color
      track.append(fill)
      row.append(top, track)
      why.append(row)
    }
    why.append(
      el(
        'p',
        'mc-note',
        'Biggest factors behind the estimate (SHAP). Green raises the price, red lowers it.',
      ),
    )
    container.append(why)
  }

  // --- true monthly cost
  const cost = el('div', 'mc-block')
  cost.append(el('h3', 'mc-h', 'True monthly cost'))
  const grid = el('div', 'mc-grid')
  const out = el('div', 'mc-out')
  const update = () => {
    const c = monthlyCost(l.list, inputs)
    const share =
      inputs.income > 0 ? (c.total / (inputs.income / 12)) * 100 : Infinity
    out.replaceChildren(
      el('p', 'mc-total', `${fmt(c.total)} / month`),
      el(
        'p',
        'mc-line',
        `P&I ${fmt(c.pi)} · tax ${fmt(c.tax)} · insurance ${fmt(c.ins)}${c.pmi ? ` · PMI ${fmt(c.pmi)}` : ''}`,
      ),
      el('p', 'mc-line', `Down payment (cash): ${fmt(c.cash)}`),
    )
    const s = el(
      'p',
      'mc-share',
      Number.isFinite(share)
        ? `${share.toFixed(0)}% of gross monthly income (aim for ≤ 30%)`
        : '—',
    )
    s.style.color =
      share <= 30
        ? DEAL_COLORS.UNDERPRICED
        : share <= 36
          ? '#b45309'
          : DEAL_COLORS.OVERPRICED
    out.append(s)
  }
  grid.append(
    numberField(
      'Interest rate (your quote)',
      inputs.rate,
      0.125,
      '%',
      (v) => ((inputs.rate = v), update()),
    ),
    numberField(
      'Down payment',
      inputs.down,
      1,
      '%',
      (v) => ((inputs.down = v), update()),
    ),
    numberField(
      'Property tax / yr',
      inputs.tax,
      0.05,
      '%',
      (v) => ((inputs.tax = v), update()),
    ),
    numberField(
      'Insurance / yr',
      inputs.ins,
      0.1,
      '%',
      (v) => ((inputs.ins = v), update()),
    ),
    numberField(
      'Household income',
      inputs.income,
      1000,
      '$/yr',
      (v) => ((inputs.income = v), update()),
    ),
  )
  cost.append(
    grid,
    out,
    el(
      'p',
      'mc-note',
      'The interest rate is your input; we never assume today’s rate.',
    ),
  )
  update()
  container.append(cost)

  // --- offer drafter
  const offerBox = el('div', 'mc-block')
  offerBox.append(el('h3', 'mc-h', 'Draft an offer'))
  let offer = suggestedOffer(l)
  let name = ''
  const hint = {
    UNDERPRICED: `Priced below fair value: a full-price offer of ${fmt(offer)} may help you win it.`,
    FAIR: `Fairly priced: a starting offer around ${fmt(offer)} stays inside the fair range.`,
    OVERPRICED: `Overpriced: our fair price ${fmt(offer)} is a data-backed starting offer.`,
  }[l.deal]
  const letter = document.createElement('textarea')
  letter.readOnly = true
  letter.rows = 7
  letter.className = 'mc-letter'
  const write = () => {
    letter.value =
      `Dear Seller,\n\nThank you for showing ${l.address}. I would like to offer ${fmt(offer)} for the home.\n\n` +
      `The home is listed at ${fmt(l.list)}. An independent pricing model trained on Houston listings estimates its fair value at ${fmt(l.fair)}, ` +
      `with a likely range of ${fmt(l.p10)} to ${fmt(l.p90)} for comparable homes nearby. My offer reflects that analysis, and I am ready to move quickly with financing and an inspection.\n\n` +
      `Sincerely,\n${name.trim() || 'Your name'}`
  }
  const nameField = el('label', 'mc-field')
  nameField.append(el('span', null, 'Your name'))
  const nameRow = el('span', 'mc-input')
  const nameInput = document.createElement('input')
  nameInput.maxLength = 60
  nameInput.placeholder = 'Your name'
  nameInput.addEventListener('input', () => ((name = nameInput.value), write()))
  nameRow.append(nameInput)
  nameField.append(nameRow)
  const offerGrid = el('div', 'mc-grid')
  offerGrid.append(
    numberField('Your offer', offer, 1000, '$', (v) => ((offer = v), write())),
    nameField,
  )
  const copy = el('button', 'mc-copy', 'Copy letter')
  copy.type = 'button'
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(letter.value)
      copy.textContent = 'Copied ✓'
    } catch {
      letter.select()
      copy.textContent = 'Select + copy'
    }
    setTimeout(() => (copy.textContent = 'Copy letter'), 1600)
  })
  write()
  offerBox.append(el('p', 'mc-line', hint), offerGrid, letter, copy)
  container.append(offerBox)
}

export function hideModelExtras(container) {
  if (!container) return
  container.hidden = true
  container.replaceChildren()
}
