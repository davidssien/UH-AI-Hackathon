// Minimal DOM for testing card rendering/events without a browser dependency.
export class Element {
  constructor(tag) {
    this.tagName = tag
    this.children = []
    this.style = {}
    this.dataset = {}
    this.listeners = {}
    this.value = ''
    this.textContent = ''
  }
  append(...children) {
    this.children.push(...children)
  }
  replaceChildren(...children) {
    this.children = children
  }
  setAttribute(name, value) {
    this[name] = value
  }
  addEventListener(name, callback) {
    this.listeners[name] = callback
  }
  querySelectorAll(selector) {
    return this.children.flatMap((child) => [
      ...((
        selector.startsWith('.')
          ? child.className?.split(' ').includes(selector.slice(1))
          : child.tagName === selector
      )
        ? [child]
        : []),
      ...child.querySelectorAll(selector),
    ])
  }
  get validity() {
    const value = Number(this.value),
      step = Number(this.step)
    return {
      valid:
        this.value !== '' &&
        Number.isFinite(value) &&
        (this.min == null || value >= Number(this.min)) &&
        (this.max == null || value <= Number(this.max)) &&
        (this.step === 'any' ||
          !step ||
          Math.abs(value / step - Math.round(value / step)) < 1e-7),
    }
  }
  input(value) {
    this.value = value
    this.listeners.input?.({ target: this })
  }
}

export function installDocument(ids = []) {
  const elements = Object.fromEntries(ids.map((id) => [id, new Element('div')]))
  const previous = globalThis.document
  globalThis.document = {
    createElement: (tag) => new Element(tag),
    getElementById: (id) => elements[id],
    querySelectorAll: () => [],
  }
  return {
    elements,
    restore: () => {
      globalThis.document = previous
    },
  }
}
