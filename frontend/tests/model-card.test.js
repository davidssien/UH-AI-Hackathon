import test from 'node:test'
import assert from 'node:assert/strict'
import { renderModelExtras } from '../src/model-card.js'
import { installDocument, Element } from './fixtures/dom.js'
import { createDealsPanel } from '../src/deals.js'

test('calculator accepts ordinary fractional quotes and does not draft a zero offer from empty input', () => {
  const dom = installDocument()
  try {
    const card = new Element('div')
    renderModelExtras(card, {
      id: 'historical-0',
      list: 350000,
      fair: 300000,
      p10: 250000,
      p90: 330000,
      deal: 'OVERPRICED',
      gap: 16.7,
      factors: [],
      address: '123 Main St',
    })
    const fields = card.querySelectorAll('input')
    const [rate, down, , , income, offer] = fields
    assert.equal(rate.value, '')
    rate.input('6.99')
    down.input('3.5')
    income.input('65500')
    assert.ok(rate.validity.valid)
    assert.ok(down.validity.valid)
    assert.ok(income.validity.valid)
    assert.match(
      card.querySelectorAll('.mc-total')[0]?.textContent || '',
      /month/,
    )
    offer.input('250500')
    const letter = card.querySelectorAll('textarea')[0]
    const copy = card.querySelectorAll('button')[0]
    assert.match(letter.value, /\$250,500/)
    offer.input('')
    assert.equal(copy.disabled, true)
    assert.doesNotMatch(letter.value, /offer \$0/)
    offer.input('250500')
    assert.equal(copy.disabled, false)
    assert.match(letter.value, /\$250,500/)
    down.input('101')
    assert.equal(card.querySelectorAll('.mc-total').length, 0)
  } finally {
    dom.restore()
  }
})

test('model loading failure remains visible when the deals panel refreshes', () => {
  const dom = installDocument([
    'deals-panel',
    'deals-button',
    'deals-mdape',
    'deals-market',
    'deals-list',
    'close-deals',
    'deal-max',
  ])
  try {
    const panel = createDealsPanel(
      { getBounds: () => ({ contains: () => true }), on() {} },
      { onPick() {}, onFilter() {} },
    )
    panel.setUnavailable()
    panel.setOpen(true)
    assert.match(dom.elements['deals-list'].textContent, /unavailable/i)
    panel.refresh()
    assert.match(dom.elements['deals-list'].textContent, /unavailable/i)
  } finally {
    dom.restore()
  }
})
