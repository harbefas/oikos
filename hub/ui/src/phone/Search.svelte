<script>
  import * as api from '../lib/api.js'

  let query = $state('')
  let results = $state({ movie: [], series: [], music: [] })
  let searching = $state(false)
  let timer = 0
  let msg = $state('')
  let filter = $state('all') // 'all' | 'movie' | 'series' | 'music'

  const allGroups = $derived([
    { kind: 'movie', title: 'Filmes', items: results.movie },
    { kind: 'series', title: 'Séries', items: results.series },
    { kind: 'music', title: 'Música', items: results.music },
  ])
  const groups = $derived(
    allGroups
      .filter((g) => filter === 'all' || g.kind === filter)
      .filter((g) => g.items.length)
  )

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
    closeDetail()
  }

  // tela de detalhe do resultado -- mesma ideia do item ja na biblioteca, so
  // que "Tocar" vira "Baixar", e filme/serie ganham "Assistir agora" (torrent
  // direto, sem esperar o download terminar)
  let detailPick = $state(null) // { item, kind }
  const openDetail = (item, kind) => (detailPick = { item, kind })
  const closeDetail = () => (detailPick = null)

  // ---------- streaming direto (tipo Stremio): busca magnet no Prowlarr,
  // mostra as fontes (ja ordenadas por seeders) pra escolher qual tocar ----------
  const pad2 = (n) => String(n).padStart(2, '0')

  // null | { item, phase: 'episode'|'searching'|'empty'|'sources'|'connecting', season, episode, opts }
  let streamPick = $state(null)

  function openStream(item, kind) {
    closeDetail()
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
    let opts = await api.searchStream(term, kind)
    // Long-running anime (One Piece, Naruto...) gets released -- and gets
    // subtitled on OpenSubtitles -- by absolute episode number under a flat
    // "season 1", not the real TVDB season. If the standard SxxEyy search
    // comes up dry, retry treating the episode field as that absolute
    // number, and remember it so the subtitle lookup uses season 1 too.
    let absolute = false
    if (!opts.length && kind === 'series') {
      opts = await api.searchStream(`${item.title} ${episode}`, kind)
      absolute = opts.length > 0
    }
    if (!streamPick) return
    streamPick = { ...streamPick, phase: opts.length ? 'sources' : 'empty', opts, absolute }
  }

  async function startStream(source) {
    if (!streamPick) return
    const { item, kind, season, episode, absolute } = streamPick
    streamPick = { ...streamPick, phase: 'connecting', sourceTitle: source.title }
    const extra = kind === 'series'
      ? { imdbId: item.imdbId, season: absolute ? 1 : season, episode, title: item.title }
      : { imdbId: item.imdbId, title: item.title }
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

<div class="filters">
  {#each [['all', 'Tudo'], ['movie', 'Filmes'], ['series', 'Séries'], ['music', 'Música']] as [id, label] (id)}
    <button class:active={filter === id} onclick={() => (filter = id)}>{label}</button>
  {/each}
</div>

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
          <button class="tile-main" onclick={() => openDetail(item, group.kind)}>
            {#if item.poster}
              <img src={item.poster} alt="" loading="lazy" decoding="async" />
            {:else}
              <span class="blank"></span>
            {/if}
            <span class="name">{title(item, group.kind)}</span>
            <span class:have={item.have}>{item.have ? 'Na biblioteca' : '+ baixar'}</span>
          </button>
          {#if group.kind === 'movie' ? !item.have : group.kind === 'series'}
            <button class="stream" onclick={() => openStream(item, group.kind)} title="Assistir agora">▶</button>
          {/if}
        </div>
      {/each}
    </div>
  </section>
{/each}

{#if detailPick}
  {@const { item, kind } = detailPick}
  <div class="detail-ov">
    <button class="close" onclick={closeDetail} aria-label="Fechar">×</button>
    <div class="dt-head">
      {#if item.poster}<img class="dt-poster" src={item.poster} alt="" />{/if}
      <div class="dt-headtext">
        <h2>{title(item, kind)}</h2>
        {#if item.genres?.length || item.rating || item.runtime}
          <p class="meta">
            {[item.rating ? `★ ${item.rating}` : null, item.runtime ? `${item.runtime} min` : null, item.genres?.slice(0, 3).join(' · ')].filter(Boolean).join(' · ')}
          </p>
        {/if}
      </div>
    </div>
    {#if item.overview}<p class="overview">{item.overview}</p>{/if}
    <div class="dt-actions">
      <button class="primary" disabled={item.have} onclick={() => request(item, kind)}>
        {item.have ? '✓ já está na biblioteca' : '⬇ Baixar'}
      </button>
      {#if kind === 'movie' ? !item.have : kind === 'series'}
        <button class="primary" onclick={() => openStream(item, kind)}>▶ Assistir agora</button>
      {/if}
    </div>
  </div>
{/if}

{#if streamPick}
  <div class="stream-ov">
    <button class="close" onclick={() => (streamPick = null)} aria-label="Fechar">×</button>
    <div class="sp-head">
      {#if streamPick.item.poster}<img class="sp-poster" src={streamPick.item.poster} alt="" />{/if}
      <div class="sp-headtext">
        <h2>{streamPick.item.title}</h2>
        {#if streamPick.kind === 'series' && streamPick.phase !== 'episode'}
          <p class="sp-ep">Temporada {streamPick.season} · Episódio {streamPick.episode}</p>
        {/if}
      </div>
    </div>

    {#if streamPick.phase === 'episode'}
      <div class="epform">
        <label>
          <span>Temporada</span>
          <input type="number" min="1" bind:value={streamPick.season} />
        </label>
        <label>
          <span>Episódio</span>
          <input type="number" min="1" bind:value={streamPick.episode} />
        </label>
      </div>
      <p class="sp-hint">Anime longo (One Piece, Naruto...) usa numeração absoluta — se não achar nada, tenta de novo com o nº absoluto do episódio no lugar do episódio da temporada.</p>
      <button class="primary sp-go" onclick={runStreamSearch}>Buscar fontes</button>
    {:else if streamPick.phase === 'searching'}
      <div class="sp-status">
        <span class="spinner"></span>
        <p class="hint">Buscando fontes...</p>
      </div>
    {:else if streamPick.phase === 'empty'}
      <div class="sp-status">
        <p class="hint">Nenhuma fonte encontrada.</p>
        {#if streamPick.kind === 'series'}
          <button class="primary sp-go" onclick={() => (streamPick = { ...streamPick, phase: 'episode' })}>
            Tentar outro episódio
          </button>
        {/if}
      </div>
    {:else if streamPick.phase === 'sources'}
      <p class="hint">Escolha uma fonte</p>
      <div class="sources">
        {#each streamPick.opts as o}
          <button class="source" onclick={() => startStream(o)}>
            <span class="stitle">{o.title}</span>
            <span class="smeta">
              <span class="chip seeders">{o.seeders} ⇅</span>
              <span class="chip">{gb(o.size)}</span>
              {#if o.indexer}<span class="chip">{o.indexer}</span>{/if}
            </span>
          </button>
        {/each}
      </div>
    {:else if streamPick.phase === 'connecting'}
      <div class="sp-status">
        <span class="spinner"></span>
        <p class="hint">Conectando torrent...</p>
        <p class="hint dim">{streamPick.sourceTitle}</p>
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

  .filters {
    display: flex;
    gap: var(--space-8);
    margin-bottom: var(--space-16);
    overflow-x: auto;
    scrollbar-width: none;
  }

  .filters button {
    flex: 0 0 auto;
    min-height: 34px;
    padding: 0 var(--space-12);
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--tx-2);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
  }

  .filters button.active {
    border-color: var(--accent);
    background: var(--accent-muted);
    color: var(--tx);
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

  .detail-ov {
    position: fixed;
    z-index: 30;
    inset: 0;
    overflow: hidden;
    background: var(--bg);
    color: var(--tx);
    display: flex;
    flex-direction: column;
    gap: var(--space-12);
    padding: calc(var(--space-48) + env(safe-area-inset-top)) var(--space-16) calc(var(--space-24) + env(safe-area-inset-bottom));
  }

  .dt-head {
    flex: 0 0 auto;
    display: flex;
    gap: var(--space-12);
    align-items: flex-start;
  }

  .dt-poster {
    width: 84px;
    aspect-ratio: 2 / 3;
    object-fit: cover;
    border-radius: var(--radius-art);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-md);
    flex: 0 0 auto;
  }

  .dt-headtext {
    min-width: 0;
    display: grid;
    gap: var(--space-4);
    align-content: start;
  }

  .dt-headtext h2 {
    font-family: var(--font-serif);
    font-size: var(--font-size-lg);
    font-weight: 500;
    margin: 0;
    line-height: var(--leading-tight);
  }

  .dt-headtext .meta {
    margin: 0;
    color: var(--tx-3);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
  }

  .detail-ov .overview {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    margin: 0;
    color: var(--tx-2);
    font-size: var(--font-size-sm);
    line-height: var(--leading-prose);
  }

  .dt-actions {
    flex: 0 0 auto;
    display: grid;
    gap: var(--space-8);
  }

  .dt-actions .primary {
    min-height: 48px;
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--accent);
    color: var(--bg);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 700;
  }

  .dt-actions .primary:disabled {
    opacity: 0.6;
    background: var(--bg-3);
    border-color: var(--border);
    color: var(--tx-2);
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

  .stream-ov .close,
  .detail-ov .close {
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

  .sp-head {
    display: flex;
    gap: var(--space-12);
    align-items: flex-start;
    margin-bottom: var(--space-20);
    padding-right: 44px;
  }

  .sp-poster {
    width: 64px;
    aspect-ratio: 2 / 3;
    object-fit: cover;
    border-radius: var(--radius-art);
    border: 1px solid var(--border);
    flex: 0 0 auto;
  }

  .sp-headtext {
    min-width: 0;
    display: grid;
    gap: var(--space-4);
  }

  .stream-ov h2 {
    font-family: var(--font-serif);
    font-size: var(--font-size-lg);
    font-weight: 500;
    margin: 0;
    line-height: var(--leading-tight);
  }

  .sp-ep {
    margin: 0;
    color: var(--tx-3);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
    letter-spacing: var(--tracking-eyebrow);
  }

  .hint.dim {
    opacity: 0.6;
    font-size: var(--font-size-2xs);
  }

  .epform {
    display: flex;
    gap: var(--space-12);
  }

  .epform label {
    flex: 1 1 0;
    min-width: 0;
    display: grid;
    gap: var(--space-4);
    color: var(--tx-3);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
    letter-spacing: var(--tracking-eyebrow);
  }

  .epform input {
    width: 100%;
    min-width: 0;
    min-height: 52px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--tx);
    font: inherit;
    font-size: var(--font-size-lg);
    text-align: center;
  }

  .sp-hint {
    margin: var(--space-12) 0 0;
    color: var(--tx-3);
    font-size: var(--font-size-2xs);
    line-height: var(--leading-prose);
  }

  .sp-go {
    width: 100%;
    min-height: 48px;
    margin-top: var(--space-16);
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--accent);
    color: var(--bg);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 700;
  }

  .sp-status {
    display: grid;
    justify-items: start;
    gap: var(--space-16);
    padding: var(--space-24) 0;
  }

  .spinner {
    width: 26px;
    height: 26px;
    border-radius: 999px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
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
    background: var(--bg-3);
  }

  .stitle {
    font-size: var(--font-size-sm);
    line-height: var(--leading-tight);
    /* release names run long -- clamp instead of letting one card blow out the list */
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .smeta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
  }

  .chip {
    padding: 2px var(--space-8);
    border-radius: var(--radius-sm);
    background: var(--bg-3);
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
  }

  .chip.seeders {
    background: var(--accent-muted);
    color: var(--tx);
  }
</style>
