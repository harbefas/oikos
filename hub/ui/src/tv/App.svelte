<script>
  import { onMount, onDestroy } from 'svelte'
  import * as api from '../lib/api.js'
  import Ambient from '../lib/components/Ambient.svelte'
  import Shelf from '../lib/components/Shelf.svelte'
  import Vinyl from '../lib/components/Vinyl.svelte'
  import Hero from './Hero.svelte'
  import Clock from './Clock.svelte'

  /* --- data ---------------------------------------------------------------
     Rows load in parallel and render as they land; a slow Jellyfin must not
     hold up the games row. */
  let sections = $state([])
  let loading = $state(true)

  async function load() {
    const [resume, recent, movies, series, games, albums] = await Promise.all([
      api.resume(), api.recent(), api.movies(), api.series(), api.games(), api.albums(),
    ])

    sections = [
      { key: 'resume', title: 'Continuar assistindo', items: resume },
      { key: 'recent', title: 'Adicionados recentemente', items: recent },
      { key: 'movies', title: 'Filmes', items: movies },
      { key: 'series', title: 'Séries', items: series },
      { key: 'games', title: 'Jogos', items: games },
      { key: 'albums', title: 'Música', items: albums, ratio: '1 / 1' },
    ].filter((s) => s.items?.length)

    loading = false
  }

  /* --- focus --------------------------------------------------------------- */
  let row = $state(0)
  let col = $state(0)

  const current = $derived(sections[row]?.items?.[col] ?? null)

  // Wide art for the backdrop, best available: a real backdrop, else the Steam
  // hero, else the poster (the shader's blur and vignette make even a 2:3
  // poster read acceptably as a wash).
  const art = $derived(current?.backdrop ?? current?.hero ?? current?.cover ?? null)

  function move(dr, dc) {
    if (!sections.length) return
    if (dr) {
      row = Math.max(0, Math.min(sections.length - 1, row + dr))
      col = Math.min(col, (sections[row]?.items?.length ?? 1) - 1)
    }
    if (dc) {
      const n = sections[row]?.items?.length ?? 0
      col = Math.max(0, Math.min(n - 1, col + dc))
    }
  }

  function select(item) {
    if (!item) return
    if (item.system) return api.launch({ system: item.system, path: item.path })
    if (item.albums) {
      // artist tile: play the first album straight through
      const a = item.albums[0]
      return api.play({ path: a.path, cover: a.cover, kind: 'music' })
    }
    return api.play({ path: item.path, cover: item.cover, kind: 'video' })
  }

  function onkey(e) {
    const k = e.key
    if (k === 'ArrowUp') { move(-1, 0); e.preventDefault() }
    else if (k === 'ArrowDown') { move(1, 0); e.preventDefault() }
    else if (k === 'ArrowLeft') { move(0, -1); e.preventDefault() }
    else if (k === 'ArrowRight') { move(0, 1); e.preventDefault() }
    else if (k === 'Enter') { select(current); e.preventDefault() }
  }

  /* --- what the box is doing ----------------------------------------------
     Drives two things: which screen shows, and whether the shader runs at all.
     While mpv or a game owns the display the render loop is stopped — the GPU
     belongs to them. */
  let st = $state({ kind: 'home' })
  let poll = 0

  const isMusic = $derived(st.kind === 'media' && st.now?.mkind === 'music')
  const isVideo = $derived(st.kind === 'media' && st.now?.mkind !== 'music')
  const ambientPaused = $derived(isVideo || st.kind === 'game')

  async function tick() {
    st = await api.status()
  }

  onMount(() => {
    load()
    tick()
    poll = setInterval(tick, 2000)
    window.addEventListener('keydown', onkey)
  })

  onDestroy(() => {
    clearInterval(poll)
    window.removeEventListener('keydown', onkey)
  })
</script>

<!-- The vinyl gets the album cover as its ambient wash; browsing gets the
     focused item's art. One canvas, two contexts. -->
<Ambient
  src={isMusic ? st.now?.cover : art}
  paused={ambientPaused}
  bloom={isMusic ? 0.3 : 0.18}
  dark={isMusic ? 0.42 : 0.25}
/>

{#if isMusic}
  <Vinyl
    cover={st.now?.cover}
    title={st.now?.title}
    pos={st.now?.pos ?? 0}
    duration={st.now?.duration ?? 0}
    paused={st.now?.paused ?? false}
  />
{:else}
  <main>
    <header><Clock /></header>

    <div class="rows">
      <Hero item={current} />

      {#if loading}
        <p class="hint">Carregando…</p>
      {:else if !sections.length}
        <p class="hint">Nada na biblioteca ainda.</p>
      {:else}
        {#each sections as s, i (s.key)}
          <Shelf
            title={s.title}
            items={s.items}
            ratio={s.ratio ?? '2 / 3'}
            focus={i === row ? col : -1}
            onselect={select}
          />
        {/each}
      {/if}
    </div>
  </main>
{/if}

<style>
  main {
    position: relative;
    z-index: 1;
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  header {
    position: absolute;
    top: 0;
    right: 0;
    left: 0;
    height: 118px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 0 52px;
    z-index: 5;
    /* the rows scroll under this; without a wash the clock lands on artwork */
    background: linear-gradient(var(--scrim) 40%, transparent);
    pointer-events: none;
  }

  .rows {
    height: 100%;
    overflow-y: auto;
    scrollbar-width: none;
    padding: 132px 52px 52px;
  }

  .rows::-webkit-scrollbar {
    display: none;
  }

  .hint {
    color: var(--tx-3);
    font-size: 15px;
    padding: 8px 4px;
  }
</style>
