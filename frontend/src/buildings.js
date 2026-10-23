// Illustrative neighborhoods, not parcel records. Stable IDs can later be replaced
// by parcel/building IDs without changing rendering or selection.
const neighborhoods = [
  [-95.389, 29.771],
  [-95.381, 29.751],
  [-95.373, 29.748],
  [-95.364, 29.754],
  [-95.355, 29.759],
  [-95.395, 29.773],
  [-95.386, 29.779],
  [-95.376, 29.783],
  [-95.365, 29.778],
  [-95.41, 29.742],
  [-95.401, 29.736],
  [-95.39, 29.731],
  [-95.344, 29.742],
  [-95.337, 29.749],
  [-95.421, 29.792],
  [-95.405, 29.8],
  [-95.389, 29.806],
  [-95.357, 29.797],
  [-95.348, 29.806],
  [-95.338, 29.813],
  [-95.633, 29.619],
  [-95.617, 29.606],
  [-95.65, 29.626],
  [-95.604, 29.635],
  [-95.46, 29.705],
  [-95.48, 29.734],
  [-95.543, 29.762],
  [-95.709, 29.786],
  [-95.286, 29.563],
  [-95.215, 29.684],
  [-95.448, 30.002],
  [-95.488, 30.156],
]
let seed = 16793
function random() {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
  return seed / 4294967296
}
export const demoBuildings = neighborhoods.flatMap(([lng, lat], neighborhood) =>
  Array.from({ length: 180 }, (_, index) => {
    const row = Math.floor(index / 15),
      column = index % 15
    // Two irregular rows per block, with small gaps for streets and yards.
    const x = (column - 7) * 0.00034 + (random() - 0.5) * 0.00008
    const y =
      (row - 5.5) * 0.00032 +
      (Math.floor(row / 2) - 2.5) * 0.00016 +
      (random() - 0.5) * 0.00006
    const angle = ((neighborhood % 4) - 1.5) * 0.12
    const detail = random()
    return {
      id: `demo-${neighborhood}-${index}`,
      type: 'house',
      demo: true,
      lng: lng + x * Math.cos(angle) - y * Math.sin(angle),
      lat: lat + x * Math.sin(angle) + y * Math.cos(angle),
      tier: detail < 1 / 30 ? 0 : detail < 0.2 ? 1 : 2,
    }
  }),
)
export const demoById = new Map(
  demoBuildings.map((building) => [building.id, building]),
)

// Existing-home catalog also receives the imported Sugar Land records.
export const homeById = new Map(demoById)
