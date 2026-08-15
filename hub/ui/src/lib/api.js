// Thin wrapper over the Python hub. Every endpoint here already exists in
// console-hub.py; nothing new is invented on the client.

async function get(path) {
  const r = await fetch(path, { credentials: 'same-origin' })
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.json()
}

async function post(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.status === 204 ? null : r.json().catch(() => null)
}

// Reads. Each returns [] rather than throwing so one dead upstream (Radarr
// down, Jellyfin restarting) degrades a single row instead of the whole screen.
const safe = (p, fallback) => get(p).catch(() => fallback)

export const games = () => safe('/api/games', [])
export const movies = () => safe('/api/movies', [])
export const series = () => safe('/api/series', [])
export const albums = () => safe('/api/albums', [])
export const apps = () => safe('/api/apps', [])
export const recent = () => safe('/api/recent', [])
export const resume = () => safe('/api/resume', [])
export const downloads = () => safe('/api/downloads', [])
// What the TV is doing right now: kind is 'home' | 'media' | 'game'. For
// 'media', now.mkind tells video from music — that is what picks the vinyl
// screen over the video backdrop.
export const status = () => safe('/api/status', { running: false, kind: 'home' })
export const idle = () => safe('/api/idle', { idle: false })
export const detail = (id) => safe(`/api/detail?id=${encodeURIComponent(id)}`, {})
export const episodes = (id) => safe(`/api/episodes?id=${encodeURIComponent(id)}`, [])
export const searchQuery = () => safe('/api/search-query', { q: '' })

export const gameDetail = (name, system) =>
  safe(
    `/api/gamedetail?name=${encodeURIComponent(name)}&system=${encodeURIComponent(system ?? '')}`,
    { name }
  )

// Writes
export const play = (item) => post('/api/play', item)
export const launch = (item) => post('/api/launch', item)
export const mpv = (action) => post('/api/mpv', { action })

export { get, post }
