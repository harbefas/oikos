<script>
  import * as api from '../lib/api.js'

  let query = $state('')
  let results = $state({ movie: [], series: [], music: [] })
  let searching = $state(false)
  let timer = 0
  let msg = $state('')

  const groups = $derived([
    { kind: 'movie', title: 'Filmes', items: results.movie },
    { kind: 'series', title: 'Séries', items: results.series },
    { kind: 'music', title: 'Música', items: results.music },
  ].filter((g) => g.items.length))

  function title(item, kind) {
    if (kind === 'music') return item.title
    return `${item.title} (${item.year || '?'})`
  }

  function schedule() {
    clearTimeout(timer)
    const q = query.trim()
    if (!q) {
      results = { movie: [], series: [], music: [] }
      msg = ''
      return
    }
    timer = setTimeout(run, 450)
  }

  async function run() {
    const q = query.trim()
    if (!q) return
    searching = true
    msg = ''
    const [movie, series, music] = await Promise.all([
      api.searchMovies(q),
      api.searchSeries(q),
      api.searchMusic(q),
    ])
    results = { movie, series, music }
    searching = false
  }

  async function request(item, kind) {
    if (item.have) {
      msg = 'Ja esta na biblioteca.'
      return
    }
    msg = `Pedindo ${item.title}...`
    try {
      if (kind === 'movie') await api.requestMovie(item.tmdbId)
      else if (kind === 'series') await api.requestSeries(item.tvdbId)
      else await api.requestMusic(item.mbid)
      msg = `${item.title} pedido.`
    } catch (_) {
      msg = 'Erro ao pedir.'
    }
  }

  // ---------- streaming direto (tipo Stremio): busca magnet no Prowlarr,
  // toca a melhor fonte no mpv sem esperar o download terminar ----------
  const BAD_SRC = /\bcam\b|\bts\b|\bhdcam\b|\btelesync\b/i
  const bestSource = (opts) => {
    const good = opts.filter((o) => !BAD_SRC.test(o.title))
    return (good.length ? good : opts)[0]
  }
  const pad2 = (n) => String(n).padStart(2, '0')

  // null | { item, phase: 'episode'|'searching'|'empty'|'sources', season, episode, opts }
  let streamPick = $state(null)

  function openStream(item, kind) {
    streamPick = kind === 'series'
      ? { item, kind, phase: 'episode', season: 1, episode: 1, opts: [] }
      : { item, kind, phase: 'searching', season: null, episode: null, opts: [] }
    if (kind === 'movie') runStreamSearch()
  }

  async function runStreamSearch() {
    if (!streamPick) return
    const { item, kind, season, episode } = streamPick
    streamPick = { ...streamPick, phase: 'searching' }
    const term = kind === 'series'
      ? `${item.title} S${pad2(season)}E${pad2(episode)}`
      : `${item.title} ${item.year || ''}`.trim()
    const opts = await api.searchStream(term, kind)
    if (!streamPick) return
    if (!opts.length) {
      streamPick = { ...streamPick, phase: 'empty' }
      return
    }
    streamPick = { ...streamPick, phase: 'sources', opts }
    startStream(bestSource(opts))
  }

  async function startStream(source) {
    if (!streamPick) return
    const { item, kind, season, episode } = streamPick
    msg = '▶ conectando torrent...'
    const extra = kind === 'series'
      ? { imdbId: item.imdbId, season, episode }
      : { imdbId: item.imdbId }
    try {
      const res = await api.stream({ link: source.link, cover: item.poster, ...extra })
      streamPick = null
      msg = res?.ok
        ? (res.subtitle ? '▶ tocando com legenda' : '▶ tocando (sem legenda)')
        : `erro ao streamar: ${res?.error || '?'}`
    } catch (_) {
      streamPick = null
      msg = 'erro ao streamar'
    }
  }

  const gb = (n) => (n ? `${(n / 1e9).toFixed(1)} GB` : '?')
</script>

<label class="search">
  <span>Buscar</span>
  <input
    bind:value={query}
    oninput={schedule}
    type="search"
    placeholder="Filme, serie ou artista"
    autocomplete="off"
  />
</label>

{#if msg}<p class="msg">{msg}</p>{/if}

{#if searching}
  <p class="hint">Buscando...</p>
{:else if query.trim() && !groups.length}
  <p class="hint">Nada encontrado.</p>
{:else if !query.trim()}
  <p class="hint">Digite para buscar em Radarr, Sonarr e Lidarr.</p>
{/if}

{#each groups as group (group.kind)}
  <section>
    <h2>{group.title}</h2>
    <div class="grid">
      {#each group.items as item (`${group.kind}-${item.tmdbId ?? item.tvdbId ?? item.mbid ?? item.title}`)}
        <div class="tile">
          <button class="tile-main" onclick={() => request(item, group.kind)}>
            {#if item.poster}
              <img src={item.poster} alt="" loading="lazy" decoding="async" />
            {:else}
              <span class="blank"></span>
            {/if}
            <span class="name">{title(item, group.kind)}</span>
            <span class:have={item.have}>{item.have ? 'Na biblioteca' : '+ baixar'}</span>
          </button>
          {#if !item.have && (group.kind === 'movie' || group.kind === 'series')}
            <button class="stream" onclick={() => openStream(item, group.kind)} title="Assistir agora">▶</button>
          {/if}
        </div>
      {/each}
    </div>
  </section>
{/each}

{#if streamPick}
  <div class="stream-ov">
    <button class="close" onclick={() => (streamPick = null)} aria-label="Fechar">×</button>
    <h2>{streamPick.item.title}</h2>

    {#if streamPick.phase === 'episode'}
      <div class="epform">
        <label>Temp.<input type="number" min="1" bind:value={streamPick.season} /></label>
        <label>Ep.<input type="number" min="1" bind:value={streamPick.episode} /></label>
        <button class="primary" onclick={runStreamSearch}>Buscar</button>
      </div>
    {:else if streamPick.phase === 'searching'}
      <p class="hint">Buscando fontes...</p>
    {:else if streamPick.phase === 'empty'}
      <p class="hint">Nenhuma fonte encontrada.</p>
    {:else if streamPick.phase === 'sources'}
      <p class="hint">Conectando na melhor fonte -- toque outra pra trocar</p>
      <div class="sources">
        {#each streamPick.opts as o}
          <button class="source" onclick={() => startStream(o)}>
            <span class="stitle">{o.title}</span>
            <span class="smeta">{gb(o.size)} · {o.seeders} seeders · {o.indexer || ''}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .search {
    display: grid;
    gap: var(--space-8);
    margin-bottom: var(--space-16);
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
  }

  input {
    min-height: 44px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--tx);
    font: inherit;
    font-size: var(--font-size-sm);
    text-transform: none;
    padding: 0 var(--space-12);
  }

  input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .hint,
  .msg {
    color: var(--tx-3);
    font-size: var(--font-size-sm);
    padding: var(--space-12) var(--space-4);
  }

  section + section {
    margin-top: var(--space-24);
  }

  h2 {
    font-family: var(--font-serif);
    font-size: var(--font-size-lg);
    font-weight: 500;
    color: var(--tx);
    margin: 0 0 var(--space-12);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));
    gap: var(--space-12);
  }

  .tile {
    position: relative;
    aspect-ratio: 2 / 3;
    border-radius: var(--radius-art);
    overflow: hidden;
    background: var(--surface);
    color: var(--tx);
  }

  .tile-main {
    display: block;
    width: 100%;
    height: 100%;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-art);
    overflow: hidden;
    background: none;
    color: var(--tx);
  }

  .tile-main:active {
    border-color: var(--accent);
  }

  .tile .stream {
    position: absolute;
    z-index: 1;
    bottom: var(--space-8);
    left: var(--space-8);
    width: 32px;
    height: 32px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface) 80%, transparent);
    color: var(--tx);
    font-size: 13px;
    line-height: 1;
  }

  .tile .stream:active {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
  }

  img,
  .blank {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .blank {
    background: var(--bg-2);
  }

  .name {
    position: absolute;
    inset: auto 0 0 0;
    padding: var(--space-24) var(--space-8) var(--space-8);
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: var(--font-size-2xs);
    background: linear-gradient(transparent, var(--nm-grad) 60%);
  }

  .tile-main > span:last-child {
    position: absolute;
    top: var(--space-8);
    right: var(--space-8);
    background: var(--accent);
    color: var(--bg);
    font-size: var(--font-size-2xs);
    padding: var(--space-4) var(--space-8);
    border-radius: var(--radius-sm);
  }

  .tile-main > span.have {
    background: var(--bg-3);
    color: var(--tx-2);
    border: 1px solid var(--border);
  }

  .stream-ov {
    position: fixed;
    z-index: 30;
    inset: 0;
    overflow-y: auto;
    background: var(--bg);
    color: var(--tx);
    padding: calc(var(--space-24) + env(safe-area-inset-top)) var(--space-16) var(--space-24);
  }

  .stream-ov .close {
    position: fixed;
    z-index: 2;
    top: 12px;
    right: 12px;
    width: 44px;
    height: 44px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface) 86%, transparent);
    color: var(--tx);
    font-size: 26px;
    line-height: 1;
  }

  .stream-ov h2 {
    font-family: var(--font-serif);
    font-size: var(--font-size-lg);
    font-weight: 500;
    margin: 0 0 var(--space-16);
    padding-right: 44px;
  }

  .epform {
    display: flex;
    align-items: center;
    gap: var(--space-12);
  }

  .epform label {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    color: var(--tx-3);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
  }

  .epform input {
    width: 56px;
    min-height: 40px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--tx);
    font: inherit;
    text-align: center;
  }

  .epform .primary {
    min-height: 40px;
    padding: 0 var(--space-16);
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--accent);
    color: var(--bg);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 700;
  }

  .sources {
    display: grid;
    gap: var(--space-8);
    margin-top: var(--space-12);
  }

  .source {
    display: grid;
    gap: var(--space-4);
    text-align: left;
    padding: var(--space-12);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--tx);
  }

  .source:active {
    border-color: var(--accent);
  }

  .stitle {
    font-size: var(--font-size-sm);
  }

  .smeta {
    color: var(--tx-3);
    font-size: var(--font-size-2xs);
  }
</style>
