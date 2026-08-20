<script>
  import { onMount, onDestroy } from 'svelte'
  import { fly } from 'svelte/transition'
  import * as api from '../lib/api.js'
  import Apps from './Apps.svelte'
  import Detail from './Detail.svelte'
  import Downloads from './Downloads.svelte'
  import Gamepad from './Gamepad.svelte'
  import Grid from './Grid.svelte'
  import GroupedGrid from './GroupedGrid.svelte'
  import Home from './Home.svelte'
  import PcFrame from './PcFrame.svelte'
  import Remote from './Remote.svelte'
  import Search from './Search.svelte'
  import Transport from './Transport.svelte'

  /* Tabs load lazily — opening the app should not fetch six libraries. */
  let tabs = $state([
    { id: 'home', label: 'Início', icon: '⌂' },
    { id: 'control', label: 'Controle', icon: '🎮' },
    { id: 'games', label: 'Jogos', icon: '🕹', load: api.games },
    { id: 'movies', label: 'Filmes', icon: '🎬', load: api.movies },
    { id: 'series', label: 'Séries', icon: '📺', load: api.series },
    { id: 'music', label: 'Música', icon: '🎵', load: api.albums, ratio: '1 / 1' },
    { id: 'search', label: 'Busca', icon: '🔍' },
    { id: 'downloads', label: 'Downloads', icon: '📥', load: api.downloads },
    { id: 'apps', label: 'Apps', icon: '⚙️', load: api.apps, ratio: '1 / 1' },
  ])

  let active = $state(new URLSearchParams(location.search).get('tab') || 'home')
  let data = $state({})
  let loading = $state({})
  let hyprpad = $state({ url: '', up: false })
  let tabsOpen = $state(false)
  let tabsTimer = 0
  let detailItem = $state(null)
  let detailInfo = $state({})
  let detailLoading = $state(false)
  let detailEpisodes = $state([])
  let st = $state({ kind: 'home' })
  let poll = 0

  const tab = $derived(tabs.find((t) => t.id === active))
  const items = $derived(data[active] ?? [])
  const inControl = $derived(active === 'control' || active === 'pc')
  // dock some sozinho depois de alguns segundos, uniforme em toda aba. So
  // gamepad com jogo ativo fica sem grip (D-pad precisa da borda inteira).
  const hideChrome = $derived(active === 'control' && st.kind === 'game')
  const isWatch = $derived(active === 'movies' || active === 'series')
  // Filmes e Series moram na mesma aba ("Assistir") pra caber na barra --
  // navTabs troca a entrada 'movies' por um botao virtual 'watch' e some com 'series'.
  const navTabs = $derived(
    tabs
      .filter((t) => t.id !== 'series')
      .map((t) => (t.id === 'movies' ? { id: 'watch', label: 'Assistir', icon: '🎬' } : t))
  )
  const isNavActive = (t) => (t.id === 'watch' ? isWatch : active === t.id)
  const playing = $derived(st.kind === 'media')

  async function ensure(id) {
    if (data[id] || loading[id]) return
    const t = tabs.find((x) => x.id === id)
    if (!t?.load) return
    loading = { ...loading, [id]: true }
    data = { ...data, [id]: await t.load() }
    loading = { ...loading, [id]: false }
  }

  async function reload(id) {
    const t = tabs.find((x) => x.id === id)
    if (!t?.load) return
    loading = { ...loading, [id]: true }
    data = { ...data, [id]: await t.load() }
    loading = { ...loading, [id]: false }
  }

  $effect(() => {
    ensure(active)
  })

  function kindOf(item) {
    if (item?.system) return 'game'
    if (item?.albums) return 'music'
    if (item?.id && !item?.path) return 'series'
    return 'video'
  }

  const isSeries = (item) => item?.id && !item.path && !item.system && !item.albums

  const detailLabel = $derived(
    kindOf(detailItem) === 'game' ? 'Abrir' : detailEpisodes.length ? 'Assistir do início' : 'Tocar'
  )

  async function openDetail(item) {
    detailItem = item
    detailEpisodes = []
    detailInfo = item.albums
      ? {
          name: item.name,
          cover: item.cover ?? item.albums?.[0]?.cover,
          genres: item.genre ? [item.genre] : [],
        }
      : {}
    detailLoading = true
    try {
      if (item.system) detailInfo = { ...detailInfo, ...(await api.gameDetail(item.name, item.system)) }
      else if (item.id) detailInfo = { ...detailInfo, ...(await api.detail(item.id)) }
      if (isSeries(item)) detailEpisodes = await api.episodes(item.id)
    } finally {
      detailLoading = false
    }
  }

  async function select(item = detailItem) {
    if (!item) return
    if (item.cmd) {
      await api.launchApp(item.id)
      active = 'control'
      detailItem = null
      return
    }
    if (item.system) {
      await api.launch({ system: item.system, path: item.path })
      active = 'control'
      detailItem = null
      return
    }
    if (item.albums) {
      const a = item.albums[0]
      await api.play({ path: a.path, cover: a.cover, kind: 'music' })
      active = 'control'
      detailItem = null
      return
    }
    if (isSeries(item)) {
      const eps = detailEpisodes.length ? detailEpisodes : await api.episodes(item.id)
      if (eps.length) {
        await api.play({
          paths: eps.map((ep) => ep.path),
          cover: item.cover,
          kind: 'video',
        })
      }
      active = 'control'
      detailItem = null
      return
    }
    await api.play({ path: item.path, cover: item.cover, kind: 'video' })
    active = 'control'
    detailItem = null
  }

  // toca a partir de um episodio especifico (playlist do resto da temporada
  // pra frente), igual a UI legada -- em vez de sempre comecar do 1o.
  async function selectEpisode(index) {
    const item = detailItem
    const eps = detailEpisodes.slice(index)
    if (!item || !eps.length) return
    await api.play({ paths: eps.map((ep) => ep.path), cover: item.cover, kind: 'video' })
    active = 'control'
    detailItem = null
  }

  async function stop() {
    await api.stop()
    st = await api.status()
  }

  function showTabs() {
    if (hideChrome) return
    tabsOpen = true
    clearTimeout(tabsTimer)
    tabsTimer = setTimeout(() => (tabsOpen = false), 3200)
  }

  function openTab(id) {
    // 'watch' e virtual: mantem filme/serie ja escolhido, ou cai em filmes
    active = id === 'watch' ? (isWatch ? active : 'movies') : id
    showTabs()
  }

  onMount(() => {
    const tick = async () => (st = await api.status())
    tick()
    poll = setInterval(tick, 2000)
    api.hyprpad().then((info) => {
      hyprpad = info
      if (info.up && info.url && !tabs.some((t) => t.id === 'pc')) {
        tabs = [...tabs, { id: 'pc', label: 'PC', icon: '🖥' }]
      }
    })
    if (!hideChrome) showTabs()
  })

  onDestroy(() => {
    clearInterval(poll)
    clearTimeout(tabsTimer)
  })
</script>

<div class="app" class:with-player={playing && active !== 'control'} class:control-mode={inControl}>
  <main class:frame={active === 'pc' || active === 'control'}>
    {#if isWatch}
      <div class="segmented">
        <button class:active={active === 'movies'} onclick={() => (active = 'movies')}>Filmes</button>
        <button class:active={active === 'series'} onclick={() => (active = 'series')}>Séries</button>
      </div>
    {/if}

    {#key active}
      <div
        class="page"
        in:fly={{ x: isWatch ? (active === 'movies' ? -24 : 24) : 0, y: isWatch ? 0 : 10, duration: 180, opacity: 0 }}
        out:fly={{ x: isWatch ? (active === 'movies' ? 24 : -24) : 0, y: 0, duration: 120, opacity: 0 }}
      >
        {#if loading[active]}
          <p class="hint">Carregando…</p>
        {:else if active === 'home'}
          <Home onselect={openDetail} onlaunch={() => (active = 'control')} />
        {:else if active === 'search'}
          <Search />
        {:else if active === 'downloads'}
          <Downloads items={items} />
        {:else if active === 'apps'}
          <Apps items={items} onadded={() => reload('apps')} onlaunch={() => (active = 'control')} />
        {:else if active === 'pc'}
          <PcFrame url={hyprpad.url} />
        {:else if active === 'control'}
          <div class="control">
            <div class="body">
              {#if st.kind === 'game'}
                <Gamepad />
              {:else if st.kind === 'media'}
                <Transport now={st.now ?? {}} />
              {:else}
                <Remote />
              {/if}
            </div>
            <button class="close" onclick={() => (active = 'home')} aria-label="Fechar">✕</button>
            {#if st.kind !== 'home'}
              <button class="kill" onclick={stop}>Parar</button>
            {/if}
          </div>
        {:else if isWatch}
          {#if !items.length}
            <p class="hint">Nada aqui.</p>
          {:else}
            <GroupedGrid {items} ratio={tab?.ratio ?? '2 / 3'} onselect={openDetail} />
          {/if}
        {:else if !items.length}
          <p class="hint">Nada aqui.</p>
        {:else}
          <Grid {items} ratio={tab?.ratio ?? '2 / 3'} onselect={openDetail} />
        {/if}
      </div>
    {/key}
  </main>

  {#if detailItem}
    <Detail
      item={detailItem}
      info={detailInfo}
      loading={detailLoading}
      actionLabel={detailLabel}
      episodes={detailEpisodes}
      onclose={() => (detailItem = null)}
      onaction={() => select()}
      onepisode={selectEpisode}
    />
  {/if}

  {#if playing && active !== 'control' && active !== 'pc'}
    <button class="mini" onclick={() => (active = 'control')}>
      {#if st.now?.cover}
        <img src={st.now.cover} alt="" />
      {/if}
      <span>
        <b>{st.now?.title ?? '—'}</b>
        <small>{Math.floor((st.now?.pos ?? 0) / 60)}:{String(Math.floor((st.now?.pos ?? 0) % 60)).padStart(2, '0')}</small>
      </span>
      <i>{st.paused ? '▶' : '⏸'}</i>
    </button>
  {/if}

  {#if active !== 'control' && active !== 'pc' && st.kind === 'game'}
    <button class="control-fab" onclick={() => (active = 'control')}>🎮</button>
  {/if}

  <!-- toque revela o dock, some sozinho depois de alguns segundos -- uniforme
       em toda aba. So gamepad com jogo ativo fica sem grip (D-pad precisa da
       borda inteira; some via mini-player/control-fab, nao pelo grip). -->
  <nav class:open={tabsOpen && !hideChrome}>
    {#each navTabs as t (t.id)}
      <button
        class:active={isNavActive(t)}
        onclick={() => openTab(t.id)}
        aria-current={isNavActive(t) ? 'page' : undefined}
      >
        <span class="icon">{t.icon}</span>
        <span class="label">{t.label}</span>
      </button>
    {/each}
  </nav>

  {#if !hideChrome}
    <button class="grip" onclick={showTabs} aria-label="Abrir menu"><i></i></button>
  {/if}
</div>

<style>
  .app {
    height: 100dvh;
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    display: grid;
    grid-template-rows: 1fr auto;
  }

  :global(html),
  :global(body) {
    max-width: 100vw;
    overflow-x: hidden;
  }

  :global(::-webkit-scrollbar:horizontal) {
    display: none;
  }

  .app.with-player {
    grid-template-rows: 1fr auto auto;
  }

  .app.control-mode {
    grid-template-rows: 1fr;
  }

  main {
    overflow-y: auto;
    overflow-x: hidden;
    padding: var(--space-16);
    -webkit-overflow-scrolling: touch;
  }

  /* wrapper da transicao de pagina -- sem altura propria, o .control (tela do
     controle remoto/gamepad) nao tinha em que "100%" se apoiar e o conteudo
     ficava colado no topo com um vao vazio embaixo. height (nao min-height):
     percentual de filho so resolve contra altura *definida* do pai -- overflow
     continua visible, entao grades mais altas que a tela nao ficam cortadas,
     o scroll de "main" ainda pega o resto. */
  .page {
    height: 100%;
  }

  main.frame {
    overflow: hidden;
    padding: 0;
  }

  .control {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding-bottom: calc(var(--space-24) + env(safe-area-inset-bottom));
  }

  .control > .body {
    flex: 1;
    min-height: 0;
  }

  .control .close,
  .control .kill {
    flex: 0 0 auto;
    justify-self: center;
    margin: var(--space-8) auto 0;
    width: min(100%, 220px);
    min-height: 44px;
    padding: 0 var(--space-12);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--tx);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 600;
    display: block;
  }

  .control .kill {
    border-color: color-mix(in srgb, red 45%, var(--border));
    color: color-mix(in srgb, red 55%, var(--tx));
  }

  .control .close:active {
    border-color: var(--accent);
    background: var(--bg-3);
  }

  .control .kill:active {
    background: color-mix(in srgb, red 12%, var(--bg-3));
  }

  .hint {
    color: var(--tx-3);
    font-size: var(--font-size-sm);
    padding: var(--space-16) var(--space-4);
  }

  .segmented {
    display: flex;
    gap: var(--space-4);
    padding: 3px;
    margin-bottom: var(--space-16);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
  }

  .segmented button {
    flex: 1;
    min-height: 36px;
    border: 0;
    border-radius: calc(var(--radius-md) - 3px);
    background: none;
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 600;
  }

  .segmented button.active {
    background: var(--accent);
    color: var(--bg);
  }

  /* Bottom bar rather than a hamburger — §8 asks for exactly this below 768px.
     Chrome rules apply in full here: flat, 1px line, colour-only transitions. */
  nav {
    position: fixed;
    z-index: 18;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    background: color-mix(in srgb, var(--bg) 86%, transparent);
    backdrop-filter: blur(14px);
    border-top: 1px solid var(--border);
    padding-bottom: env(safe-area-inset-bottom);
    transform: translateY(calc(100% + 4px));
    transition: transform var(--duration-settle) var(--ease-focus);
  }

  :global(::-webkit-scrollbar:horizontal) {
    display: none;
  }

  nav.open {
    transform: translateY(0);
  }

  nav button {
    flex: 1 1 0;
    min-width: 0;
    min-height: 64px;
    background: none;
    border: 0;
    border-top: 3px solid transparent;
    padding: var(--space-8) 1px var(--space-6);
    font-family: var(--font-sans);
    font-size: 8px;
    font-weight: 500;
    letter-spacing: 0;
    text-transform: uppercase;
    color: var(--tx-3);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition:
      color var(--duration-base) var(--ease-standard),
      background var(--duration-base) var(--ease-standard),
      border-color var(--duration-base) var(--ease-standard);
  }

  /* Active item: accent rule + muted wash, the §4 sidebar pattern turned
     horizontal. No pill, no fill, nothing moves. */
  nav button.active {
    color: var(--accent);
    background: none;
    border-top-color: var(--accent);
  }

  .icon {
    font-size: 18px;
    line-height: 1;
  }

  .label {
    display: block;
    width: 100%;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: center;
  }

  .grip {
    position: fixed;
    z-index: 17;
    left: 0;
    right: 0;
    bottom: 0;
    height: 26px;
    border: 0;
    background: transparent;
    display: grid;
    place-items: center;
    padding-bottom: env(safe-area-inset-bottom);
  }

  .grip i {
    width: 44px;
    height: 5px;
    border-radius: 999px;
    background: var(--border-3);
    opacity: 0.8;
  }

  .mini {
    position: fixed;
    z-index: 12;
    left: 0;
    right: 0;
    /* precisa bater com a altura real do nav (64px de botao + safe-area) --
       hardcoded sem o safe-area, a mini-barra cavalgava por cima do nav */
    bottom: calc(64px + env(safe-area-inset-bottom));
    min-height: 58px;
    display: flex;
    align-items: center;
    gap: var(--space-10);
    padding: var(--space-8) var(--space-12);
    background: var(--surface);
    border: 0;
    border-top: 1px solid var(--border);
    color: var(--tx);
    text-align: left;
  }

  .mini img {
    width: 42px;
    height: 42px;
    object-fit: cover;
    border-radius: var(--radius-sm);
    flex: 0 0 auto;
  }

  .mini span {
    min-width: 0;
    flex: 1;
    display: grid;
    gap: 2px;
  }

  .mini b,
  .mini small {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mini small {
    color: var(--tx-4);
    font-family: var(--font-mono);
    font-size: var(--font-size-2xs);
  }

  .mini i {
    flex: 0 0 auto;
    font-size: 22px;
  }

  .control-fab {
    position: fixed;
    right: 14px;
    bottom: 82px;
    z-index: 16;
    width: 48px;
    height: 48px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--accent);
    color: var(--bg);
    font-size: 22px;
  }
</style>
