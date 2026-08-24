<script>
  import { onMount, onDestroy } from 'svelte'
  import { fly } from 'svelte/transition'
  import * as api from '../lib/api.js'
  import Ambient from '../lib/components/Ambient.svelte'
  import Shelf from '../lib/components/Shelf.svelte'
  import Vinyl from '../lib/components/Vinyl.svelte'
  import Hero from './Hero.svelte'
  import Clock from './Clock.svelte'

  const CATS = [
    { id: 'home', label: 'Início' },
    { id: 'movies', label: 'Filmes' },
    { id: 'series', label: 'Séries' },
    { id: 'music', label: 'Música' },
    { id: 'games', label: 'Jogos' },
    { id: 'search', label: 'Busca' },
    { id: 'downloads', label: 'Downloads' },
    { id: 'apps', label: 'Apps' },
  ]

  /* --- data ---------------------------------------------------------------
     Rows load in parallel and render as they land; a slow Jellyfin must not
     hold up the games row. */
  let libraries = $state({ resume: [], recent: [], movies: [], series: [], games: [], albums: [], apps: [] })
  let sections = $state([])
  let loading = $state(true)
  let screen = $state('home')
  let nav = $state(0)
  let sidebar = $state(false)
  let searchText = $state('')
  let searchTimer = 0
  let downloadsTimer = 0
  let detailOpen = $state(false)
  let detailItem = $state(null)
  let detailInfo = $state({})
  let wallpaper = $state(false)
  let wallpaperSrc = $state('/wallpaper')
  let lastInput = Date.now()
  let idleTimer = 0
  const initialScreen = new URLSearchParams(location.search).get('screen') || 'home'

  async function load() {
    const [resume, recent, movies, series, games, albums, apps] = await Promise.all([
      api.resume(), api.recent(), api.movies(), api.series(), api.games(), api.albums(), api.apps(),
    ])

    libraries = { resume, recent, movies, series, games, albums, apps }
    show(CATS.some((cat) => cat.id === initialScreen) ? initialScreen : 'home')
    loading = false
  }

  function homeSections() {
    return [
      { key: 'resume', title: 'Continuar assistindo', items: libraries.resume },
      { key: 'recent', title: 'Adicionados recentemente', items: libraries.recent },
      { key: 'movies', title: 'Filmes', items: libraries.movies },
      { key: 'series', title: 'Séries', items: libraries.series },
      { key: 'games', title: 'Jogos', items: libraries.games },
      { key: 'albums', title: 'Música', items: libraries.albums, ratio: '1 / 1' },
    ].filter((s) => s.items?.length)
  }

  // Mesmo agrupamento do celular (GroupedGrid), mas cada grupo vira uma
  // shelf propria em vez de uma secao com grid interno -- o layout da TV ja
  // e shelves empilhadas, entao isso cai direto no row/col nav existente.
  function groupSections(key, items, groupBy) {
    const by = new Map()
    for (const item of items) {
      const g = item[groupBy] || 'Outros'
      if (!by.has(g)) by.set(g, [])
      by.get(g).push(item)
    }
    return [...by.entries()]
      .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0], 'pt-BR'))
      .map(([g, group]) => ({ key: `${key}-${g}`, title: g, items: group }))
  }

  function appItems() {
    return libraries.apps.map((app) => ({
      ...app,
      name: app.label,
      cover: null,
      _app: true,
    }))
  }

  function downloadItems(items) {
    return items.map((d) => ({
      ...d,
      name: `${d.title} · ${d.percent ?? 0}%`,
      cover: null,
      _download: true,
    }))
  }

  function show(id) {
    screen = id
    nav = Math.max(0, CATS.findIndex((c) => c.id === id))
    row = 0
    col = 0
    if (id === 'home') sections = homeSections()
    else if (id === 'movies') sections = groupSections('movies', libraries.movies, 'genre')
    else if (id === 'series') sections = groupSections('series', libraries.series, 'genre')
    else if (id === 'music') sections = [{ key: 'music', title: 'Música', items: libraries.albums, ratio: '1 / 1' }]
    else if (id === 'games') sections = groupSections('games', libraries.games, 'label')
    else if (id === 'apps') sections = [{ key: 'apps', title: 'Apps', items: appItems(), ratio: '1 / 1' }]
    else if (id === 'downloads') refreshDownloads()
    else if (id === 'search') runSearch(searchText)
  }

  async function refreshDownloads() {
    const items = await api.downloads()
    sections = [{ key: 'downloads', title: 'Baixando agora', items: downloadItems(items), ratio: '16 / 9' }]
  }

  function resultItems(items, kind) {
    return items.map((item) => ({
      ...item,
      name: kind === 'music' ? item.title : `${item.title} (${item.year || '?'})`,
      cover: item.poster,
      _searchKind: kind,
    }))
  }

  async function runSearch(q) {
    searchText = q
    clearTimeout(searchTimer)
    if (!q) {
      sections = []
      return
    }
    searchTimer = setTimeout(async () => {
      const [movies, series, music] = await Promise.all([
        api.searchMovies(q), api.searchSeries(q), api.searchMusic(q),
      ])
      sections = [
        { key: 'search-movies', title: 'Filmes', items: resultItems(movies, 'movie') },
        { key: 'search-series', title: 'Séries', items: resultItems(series, 'series') },
        { key: 'search-music', title: 'Música', items: resultItems(music, 'music') },
      ].filter((s) => s.items.length)
      row = 0
      col = 0
    }, 250)
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

  /* The vertical twin of the shelf's own scroll effect: moving down a row has
     to carry the viewport with it, or the focused card sits below the fold.
     The row is pinned near the top third rather than scrolled just barely into
     view, so the rows underneath stay visible as the next thing to reach. */
  let rowsEl = $state()

  /* The next row has to stay visible, and no amount of vh math can know how
     tall the hero actually ended up. So measure: size the card so that one
     shelf plus its chrome (label, track padding, card caption) fills ~72% of
     the rows area, which leaves the remaining ~28% as the peek at any window
     size. Safe against feedback loops -- .rows is flex:1 and scrolls, so its
     height depends on the stage, never on the cards inside it. */
  $effect(() => {
    // depends on sections: the first run happens while the rows are still
    // loading, and without this the fit never retries once they render
    const n = sections.length
    if (!rowsEl || !n) return
    const fit = () => {
      // a non-active shelf: the focused card carries a transform: scale, which
      // would inflate every measurement taken from it
      const shelf = rowsEl.querySelector('.shelf:not(.active)')
      const card = shelf?.querySelector('.track > *')
      if (!shelf || !card) return
      const cardH = card.getBoundingClientRect().height
      const curW = parseFloat(getComputedStyle(card).width)
      if (!cardH || !curW) return
      // a card is poster (2/3) plus the caption under it; a shelf is a card
      // plus its label and track padding. Both extras are fixed, so measure
      // them once and solve for the width that hits the target shelf height.
      const caption = cardH - curW * 1.5
      const chrome = shelf.getBoundingClientRect().height - cardH
      const target = rowsEl.clientHeight * 0.62 - chrome - caption
      const w = Math.max(92, Math.min(250, target / 1.5))
      rowsEl.style.setProperty('--card-w', `${Math.round(w)}px`)
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(rowsEl)
    return () => ro.disconnect()
  })

  $effect(() => {
    const n = sections.length
    if (!rowsEl) return
    // row 0 goes all the way up: anything else crops the hero above the shelves
    if (row === 0 || !n) {
      rowsEl.scrollTo({ top: 0, behavior: 'smooth' })
      return
    }
    const el = rowsEl.querySelectorAll('.shelf')[row]
    if (!el) return
    const box = rowsEl.getBoundingClientRect()
    const top = rowsEl.scrollTop + (el.getBoundingClientRect().top - box.top) - 8
    rowsEl.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  })

  async function openDetail(item) {
    if (!item) return
    if (item._download) return
    if (item._app) return api.launchApp(item.id)
    detailItem = item
    detailInfo = { name: item.name, cover: item.cover, backdrop: item.backdrop, overview: item.overview ?? '' }
    detailOpen = true
    if (item._searchKind) {
      detailInfo = {
        name: item.name,
        cover: item.cover,
        backdrop: item.cover,
        overview: item.overview ?? '',
        genres: item.genres ?? [],
        year: item.year,
        runtime: item.runtime,
        rating: item.rating,
        have: item.have,
      }
      return
    }
    if (item.system) {
      detailInfo = await api.gameDetail(item.name, item.system)
      detailInfo = { ...detailInfo, cover: item.cover, backdrop: detailInfo.backdrop ?? item.hero ?? item.cover }
      return
    }
    if (item.id) {
      const info = await api.detail(item.id)
      detailInfo = { ...info, cover: item.cover ?? info.cover, backdrop: info.backdrop ?? item.backdrop ?? item.cover }
    }
  }

  function closeDetail() {
    detailOpen = false
    detailItem = null
    detailInfo = {}
  }

  async function detailAction() {
    const item = detailItem
    if (!item) return
    if (item._searchKind) {
      if (!item.have) {
        if (item._searchKind === 'movie') await api.requestMovie(item.tmdbId)
        else if (item._searchKind === 'series') await api.requestSeries(item.tvdbId)
        else await api.requestMusic(item.mbid)
      }
      closeDetail()
      return
    }
    if (item.system) {
      await api.launch({ system: item.system, path: item.path })
    } else if (item.albums) {
      const a = item.albums[0]
      await api.play({ path: a.path, cover: a.cover, kind: 'music' })
    } else if (detailInfo.type === 'Series' || (!item.path && item.id)) {
      const eps = await api.episodes(item.id)
      if (eps.length) await api.play({ paths: eps.map((ep) => ep.path), cover: item.cover, kind: 'video' })
    } else {
      await api.play({ path: item.path, cover: item.cover, kind: 'video' })
    }
    closeDetail()
  }

  function onkey(e) {
    const k = e.key
    lastInput = Date.now()
    if (wallpaper) {
      wallpaper = false
      e.preventDefault()
      return
    }
    if (detailOpen) {
      if (k === 'Enter') detailAction()
      else if (k === 'Escape' || k === 'Backspace') closeDetail()
      else return
      e.preventDefault()
      return
    }
    if (sidebar) {
      // muda de aba assim que o foco passa por ela -- nao precisa selecionar
      if (k === 'ArrowUp') { nav = Math.max(0, nav - 1); show(CATS[nav].id) }
      else if (k === 'ArrowDown') { nav = Math.min(CATS.length - 1, nav + 1); show(CATS[nav].id) }
      else if (k === 'ArrowRight' || k === 'Escape' || k === 'Enter') sidebar = false
      else return
      e.preventDefault()
      return
    }
    if (k === 'ArrowUp') { move(-1, 0); e.preventDefault() }
    else if (k === 'ArrowDown') { move(1, 0); e.preventDefault() }
    else if (k === 'ArrowLeft') {
      if (col === 0) sidebar = true
      else move(0, -1)
      e.preventDefault()
    }
    else if (k === 'ArrowRight') { move(0, 1); e.preventDefault() }
    else if (k === 'Enter') { openDetail(current); e.preventDefault() }
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

  async function watchSearchQuery() {
    const { q } = await api.searchQuery()
    if (q === searchText) return
    searchText = q
    if (q && screen !== 'search') show('search')
    else if (screen === 'search') runSearch(q)
  }

  async function checkIdle() {
    const state = await api.idle()
    if (state.idle && Date.now() - lastInput > 5 * 60 * 1000) {
      wallpaperSrc = `/wallpaper?t=${Date.now()}`
      wallpaper = true
    }
  }

  onMount(() => {
    load()
    tick()
    poll = setInterval(tick, 2000)
    const searchPoll = setInterval(watchSearchQuery, 700)
    downloadsTimer = setInterval(() => {
      if (screen === 'downloads') refreshDownloads()
    }, 3000)
    idleTimer = setInterval(checkIdle, 15000)
    window.addEventListener('keydown', onkey)
    return () => clearInterval(searchPoll)
  })

  onDestroy(() => {
    clearInterval(poll)
    clearInterval(downloadsTimer)
    clearInterval(idleTimer)
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

    <aside class:open={sidebar}>
        {#each CATS as cat, i (cat.id)}
        <button class:active={screen === cat.id} class:focus={sidebar && nav === i} onclick={() => show(cat.id)}>
          {cat.label}
        </button>
      {/each}
    </aside>

    <div class="stage" class:sidebar-open={sidebar}>
      {#if screen === 'search'}
        <div class="search-bar">
          <span>{searchText || 'Digite no celular'}</span>
          <i></i>
        </div>
      {:else}
        <Hero item={current} />
      {/if}
    </div>

    <div class="rows" class:sidebar-open={sidebar} bind:this={rowsEl}>
      {#key screen}
        <div class="screen" in:fly={{ y: 16, duration: 220, opacity: 0 }} out:fly={{ y: -16, duration: 140, opacity: 0 }}>

          {#if loading}
            <p class="hint">Carregando…</p>
          {:else if !sections.length}
            <p class="hint">{screen === 'search' ? 'Nada encontrado.' : 'Nada aqui.'}</p>
          {:else}
            {#each sections as s, i (s.key)}
              <Shelf
                title={s.title}
                items={s.items}
                ratio={s.ratio ?? '2 / 3'}
                focus={i === row ? col : -1}
                onselect={openDetail}
              />
            {/each}
          {/if}
        </div>
      {/key}
    </div>
  </main>
{/if}

{#if detailOpen}
  <div class="detail">
    <div
      class="detail-bg"
      style:background-image={detailInfo.backdrop || detailInfo.cover ? `url(${detailInfo.backdrop ?? detailInfo.cover})` : 'none'}
    ></div>
    <section>
      <div class="poster" style:background-image={detailInfo.cover ? `url(${detailInfo.cover})` : 'none'}></div>
      <div class="detail-text">
        <h1>{detailInfo.name ?? detailItem?.name}</h1>
        <p class="meta">
          {[detailInfo.year, detailInfo.runtime ? `${detailInfo.runtime} min` : null, detailInfo.rating ? `★ ${detailInfo.rating}` : null, detailInfo.genres?.slice?.(0, 3).join(' · ')].filter(Boolean).join(' · ')}
        </p>
        {#if detailInfo.overview}<p class="overview">{detailInfo.overview}</p>{/if}
        {#if detailInfo.shots?.length}
          <div class="shots">
            {#each detailInfo.shots.slice(0, 4) as shot}
              <img src={shot} alt="" />
            {/each}
          </div>
        {/if}
        <button class="primary" onclick={detailAction}>
          {detailItem?._searchKind ? (detailItem.have ? 'Na biblioteca' : 'Baixar') : 'Tocar'}
        </button>
      </div>
    </section>
  </div>
{/if}

{#if wallpaper}
  <div class="wallpaper">
    <img src={wallpaperSrc} alt="" />
  </div>
{/if}

<style>
  /* the shared tokens.css leaves html/body auto-height for the phone's
     normal page scroll -- on the TV that lets the whole page scroll under
     the absolutely-positioned aside, dragging it along instead of leaving
     it fixed while only .rows scrolls */
  :global(html),
  :global(body),
  :global(#app) {
    height: 100%;
    overflow: hidden;
  }

  main {
    /* TV-only override of the shared token (the phone keeps its 250px): the
       card drives the shelf height, so tying it to the viewport is what leaves
       the next row peeking above the fold at any screen size. Capped at the
       token value so a big panel does not inflate past the intended size. */
    --card-w: min(250px, 20vh);
    /* §6a floors for the 10-foot surface: chrome labels start at --font-size-sm
       and content at --font-size-lg. Declared once here so the components
       shared with the phone stay honest at both distances. */
    --label-size: var(--font-size-sm);
    --content-size: var(--font-size-lg);
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
    height: var(--tv-header);
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 0 var(--tv-safe);
    z-index: 5;
    /* the rows scroll under this; without a wash the clock lands on artwork */
    background: linear-gradient(var(--scrim) 40%, transparent);
    pointer-events: none;
  }

  aside {
    position: absolute;
    z-index: 8;
    top: 0;
    bottom: 0;
    left: 0;
    width: var(--tv-aside-w);
    padding: 0 var(--space-24);
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: var(--space-8);
    background: var(--bg);
    /* mask (nao so background) pra o realce do item focado tambem sumir no
       degrade -- so no background, o fundo do botao ativo ficava com borda
       dura passando por cima do fade, "vazando" pra fora dele */
    mask-image: linear-gradient(90deg, #000 78%, transparent);
    -webkit-mask-image: linear-gradient(90deg, #000 78%, transparent);
    transform: translateX(var(--tv-aside-hidden));
    transition: transform var(--duration-settle) var(--ease-focus);
  }

  aside.open {
    transform: translateX(0);
  }

  aside button {
    min-height: 44px;
    text-align: left;
    background: none;
    border: 0;
    border-left: 2px solid transparent;
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--label-size);
    padding: 0 var(--space-12);
    /* navegacao e via onkey (setas), nao :focus real -- o outline nativo do
       Chromium (essa caixa arredondada solta que sobrava do lado do texto)
       nao tem nada a ver com o .focus/.active daqui, so atrapalha */
    outline: none;
  }

  aside button.active {
    color: var(--tx);
  }

  aside button.focus {
    color: var(--tx);
    border-left-color: var(--accent);
    background: var(--accent-muted);
  }

  /* The hero sits OUTSIDE the scroll container: it is the read-out for whatever
     is focused, so a deeper row must not push it off-screen. Keeping it a
     sibling rather than a sticky child means no row can ever travel above or
     behind it -- only .rows scrolls. */
  .stage {
    flex: 0 0 auto;
    position: relative;
    z-index: 3;
    /* clears the header: the wash is translucent, but it still greys out
       anything under it, and the title is the one thing that cannot afford to
       be dimmed. The peek does not depend on this any more -- the card fit
       below reclaims whatever the hero takes. */
    padding: calc(var(--tv-header) + var(--space-16)) var(--tv-safe) 0;
    /* the aside's collapsed sliver, so content clears the full label list once
       it opens */
    padding-left: var(--tv-aside-peek);
    transition: padding-left var(--duration-settle) var(--ease-focus);
  }

  .rows {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: none;
    padding: 0 var(--tv-safe) var(--tv-safe);
    padding-left: var(--tv-aside-peek);
    transition: padding-left var(--duration-settle) var(--ease-focus);
  }

  .stage.sidebar-open,
  .rows.sidebar-open {
    padding-left: var(--tv-aside-w);
  }

  .search-bar {
    min-height: 30vh;
    display: flex;
    align-items: flex-end;
    gap: var(--space-8);
    padding: 0 var(--space-4) var(--space-32);
    font-family: var(--font-serif);
    font-size: var(--font-size-4xl);
    color: var(--tx);
  }

  .search-bar i {
    width: 2px;
    height: 0.9em;
    background: var(--accent);
    animation: blink 1s steps(1) infinite;
  }

  @keyframes blink {
    50% { opacity: 0; }
  }

  .rows::-webkit-scrollbar {
    display: none;
  }

  .hint {
    color: var(--tx-3);
    font-size: var(--label-size);
    padding: var(--space-8) var(--space-4);
  }

  .detail {
    position: fixed;
    z-index: 20;
    inset: 0;
    display: flex;
    align-items: flex-end;
    background: var(--bg);
  }

  .detail-bg {
    position: absolute;
    inset: 0;
    background: center / cover no-repeat;
    filter: brightness(0.5);
  }

  .detail-bg::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      linear-gradient(0deg, var(--bg) 8%, transparent 68%),
      linear-gradient(90deg, var(--bg) 0%, transparent 62%);
  }

  .detail section {
    position: relative;
    z-index: 1;
    display: flex;
    gap: var(--space-32);
    width: min(1180px, calc(100vw - 104px));
    padding: 0 var(--tv-safe) var(--tv-aside-peek);
  }

  .poster {
    flex: 0 0 230px;
    aspect-ratio: 2 / 3;
    border-radius: var(--radius-art);
    border: 1px solid var(--border);
    background: var(--surface) center / cover no-repeat;
  }

  .detail-text {
    max-width: 720px;
    align-self: flex-end;
  }

  .detail h1 {
    font-family: var(--font-serif);
    font-size: var(--font-size-4xl);
    font-weight: 500;
    line-height: var(--leading-tight);
    color: var(--tx);
  }

  .meta {
    margin-top: var(--space-12);
    min-height: 1.2em;
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--label-size);
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
  }

  .overview {
    margin-top: var(--space-12);
    color: var(--tx-2);
    font-family: var(--font-serif);
    font-size: var(--content-size);
    line-height: var(--leading-prose);
    display: -webkit-box;
    -webkit-line-clamp: 4;
    line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .shots {
    display: flex;
    gap: var(--space-12);
    margin-top: var(--space-16);
  }

  .shots img {
    width: 180px;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
  }

  .primary {
    margin-top: var(--space-20);
    min-width: 160px;
    min-height: 48px;
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--accent);
    color: var(--bg);
    font-family: var(--font-sans);
    font-size: var(--label-size);
    font-weight: 600;
  }

  .wallpaper {
    position: fixed;
    z-index: 40;
    inset: 0;
    background: #000;
  }

  .wallpaper img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
</style>
