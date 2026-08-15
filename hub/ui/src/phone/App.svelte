<script>
  import { onMount, onDestroy } from 'svelte'
  import * as api from '../lib/api.js'
  import Grid from './Grid.svelte'
  import Transport from './Transport.svelte'

  /* Tabs load lazily — opening the app should not fetch six libraries. */
  const TABS = [
    { id: 'games', label: 'Jogos', load: api.games },
    { id: 'movies', label: 'Filmes', load: api.movies },
    { id: 'series', label: 'Séries', load: api.series },
    { id: 'music', label: 'Música', load: api.albums, ratio: '1 / 1' },
    { id: 'apps', label: 'Apps', load: api.apps, ratio: '1 / 1' },
  ]

  let active = $state('games')
  let data = $state({})
  let loading = $state({})

  const tab = $derived(TABS.find((t) => t.id === active))
  const items = $derived(data[active] ?? [])

  async function ensure(id) {
    if (data[id] || loading[id]) return
    loading = { ...loading, [id]: true }
    const t = TABS.find((x) => x.id === id)
    data = { ...data, [id]: await t.load() }
    loading = { ...loading, [id]: false }
  }

  $effect(() => {
    ensure(active)
  })

  function select(item) {
    if (item.cmd || item.id) return api.post('/api/app', { id: item.id })
    if (item.system) return api.launch({ system: item.system, path: item.path })
    if (item.albums) {
      const a = item.albums[0]
      return api.play({ path: a.path, cover: a.cover, kind: 'music' })
    }
    return api.play({ path: item.path, cover: item.cover, kind: 'video' })
  }

  /* What the TV is doing decides whether the transport bar is on screen. */
  let st = $state({ kind: 'home' })
  let poll = 0

  const playing = $derived(st.kind === 'media')

  onMount(() => {
    const tick = async () => (st = await api.status())
    tick()
    poll = setInterval(tick, 2000)
  })

  onDestroy(() => clearInterval(poll))
</script>

<div class="app" class:with-transport={playing}>
  <main>
    {#if loading[active]}
      <p class="hint">Carregando…</p>
    {:else if !items.length}
      <p class="hint">Nada aqui.</p>
    {:else}
      <Grid {items} ratio={tab?.ratio ?? '2 / 3'} onselect={select} />
    {/if}
  </main>

  {#if playing}
    <Transport now={st.now ?? {}} />
  {/if}

  <nav>
    {#each TABS as t (t.id)}
      <button
        class:active={active === t.id}
        onclick={() => (active = t.id)}
        aria-current={active === t.id ? 'page' : undefined}
      >
        {t.label}
      </button>
    {/each}
  </nav>
</div>

<style>
  .app {
    height: 100dvh;
    display: grid;
    grid-template-rows: 1fr auto;
  }

  .app.with-transport {
    grid-template-rows: 1fr auto auto;
  }

  main {
    overflow-y: auto;
    padding: var(--space-16);
    -webkit-overflow-scrolling: touch;
  }

  .hint {
    color: var(--tx-3);
    font-size: var(--font-size-sm);
    padding: var(--space-16) var(--space-4);
  }

  /* Bottom bar rather than a hamburger — §8 asks for exactly this below 768px.
     Chrome rules apply in full here: flat, 1px line, colour-only transitions. */
  nav {
    display: flex;
    background: var(--bg-2);
    border-top: 1px solid var(--border);
    padding-bottom: env(safe-area-inset-bottom);
  }

  nav button {
    flex: 1;
    min-height: 44px; /* §8 touch target */
    background: none;
    border: 0;
    border-top: 2px solid transparent;
    padding: var(--space-12) var(--space-4);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 500;
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
    color: var(--tx-3);
    transition:
      color var(--duration-base) var(--ease-standard),
      background var(--duration-base) var(--ease-standard),
      border-color var(--duration-base) var(--ease-standard);
  }

  /* Active item: accent rule + muted wash, the §4 sidebar pattern turned
     horizontal. No pill, no fill, nothing moves. */
  nav button.active {
    color: var(--tx);
    background: var(--accent-muted);
    border-top-color: var(--accent);
  }
</style>
