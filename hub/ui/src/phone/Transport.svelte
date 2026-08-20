<script>
  import * as api from '../lib/api.js'

  let { now = {} } = $props()

  const music = $derived(now.mkind === 'music')
  const frac = $derived(now.duration > 0 ? Math.min(1, (now.pos ?? 0) / now.duration) : 0)

  function clock(s) {
    if (!Number.isFinite(s) || s < 0) return '0:00'
    const m = Math.floor(s / 60)
    return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
  }

  function delay(v) {
    const n = Number(v ?? 0)
    return `${n > 0 ? '+' : ''}${n.toFixed(1)}s`
  }

  // prev/next only make sense in a playlist — a single film has neither.
  const actions = $derived(
    music
      ? [
          ['prev', 'Anterior'],
          ['playpause', now.paused ? 'Tocar' : 'Pausar'],
          ['next', 'Próxima'],
        ]
      : [
          ['back60', '−60s'],
          ['back', '−10s'],
          ['playpause', now.paused ? 'Tocar' : 'Pausar'],
          ['fwd', '+10s'],
          ['fwd60', '+60s'],
        ]
  )
</script>

<div class="transport">
  <div class="hero">
    {#if now.cover}
      <img class="art" src={now.cover} alt="" />
    {:else}
      <span class="art blank">{music ? '🎵' : '🎬'}</span>
    {/if}
  </div>

  <div class="text">
    <p class="title">{now.title ?? '—'}</p>
    <p class="time">{clock(now.pos)} / {clock(now.duration)}</p>
  </div>

  <div class="bar"><i style:width="{frac * 100}%"></i></div>

  <div class="row">
    {#each actions as [action, label] (action)}
      <button
        class:primary={action === 'playpause'}
        onclick={() => api.mpv(action)}
      >
        {label}
      </button>
    {/each}
  </div>

  <div class="row secondary">
    <button onclick={() => api.mpv('voldown')}>Vol −</button>
    <button onclick={() => api.mpv('volup')}>Vol +</button>
    {#if !music}
      <button onclick={() => api.mpv('sub')}>Legenda</button>
      <button onclick={() => api.mpv('audio')}>Áudio</button>
    {/if}
  </div>

  {#if !music}
    <div class="sync">
      <span>Legenda</span>
      <button onclick={() => api.mpv('subdelay-')}>−</button>
      <button class="value" onclick={() => api.mpv('subdelay0')}>{delay(now.subdelay)}</button>
      <button onclick={() => api.mpv('subdelay+')}>+</button>

      <span>Áudio</span>
      <button onclick={() => api.mpv('audiodelay-')}>−</button>
      <button class="value" onclick={() => api.mpv('audiodelay0')}>{delay(now.audiodelay)}</button>
      <button onclick={() => api.mpv('audiodelay+')}>+</button>
    </div>
  {/if}
</div>

<style>
  .transport {
    height: 100%;
    background: var(--bg-2);
    border-top: 1px solid var(--border);
    padding: var(--space-12) var(--space-16);
    display: flex;
    flex-direction: column;
    gap: var(--space-12);
  }

  /* ocupa o espaco que sobrava vazio -- capa grande em vez de thumb 44px */
  .hero {
    flex: 1;
    min-height: 0;
    display: grid;
    place-items: center;
    padding: var(--space-8) 0;
  }

  .art {
    width: auto;
    height: 100%;
    max-width: 100%;
    max-height: min(52vh, 420px);
    aspect-ratio: 1;
    object-fit: cover;
    border-radius: var(--radius-art);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-md);
  }

  .art.blank {
    display: grid;
    place-items: center;
    background: var(--surface);
    color: var(--tx-3);
    font-size: 48px;
  }

  .text {
    min-width: 0;
    text-align: center;
  }

  /* Track title is content, so the reading face (§3). */
  .title {
    font-family: var(--font-serif);
    font-size: var(--font-size-md);
    line-height: var(--leading-ui);
    color: var(--tx);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .time {
    font-family: var(--font-mono);
    font-size: var(--font-size-2xs);
    font-variant-numeric: tabular-nums;
    color: var(--tx-4);
  }

  .bar {
    height: 2px;
    background: var(--border);
    overflow: hidden;
  }

  .bar i {
    display: block;
    height: 100%;
    background: var(--border-3);
    transition: width 1s linear;
  }

  .row {
    display: flex;
    gap: var(--space-8);
  }

  /* §4 secondary button: transparent fill, 1px border. Nothing moves on press,
     only the line and ground change. */
  .row button {
    flex: 1;
    min-height: 44px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--tx);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 500;
    transition:
      background var(--duration-base) var(--ease-standard),
      border-color var(--duration-base) var(--ease-standard);
  }

  .row button:active {
    background: var(--bg-3);
    border-color: var(--border-2);
  }

  /* The single amber on this surface (§2): the primary transport action. */
  .row button.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
  }

  .row.secondary button {
    font-size: var(--font-size-2xs);
    min-height: 38px;
    color: var(--tx-2);
  }

  .sync {
    display: grid;
    grid-template-columns: minmax(58px, 0.95fr) repeat(3, minmax(38px, 1fr));
    gap: var(--space-8);
    align-items: center;
  }

  .sync span {
    min-width: 0;
    color: var(--tx-4);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 600;
  }

  .sync button {
    min-height: 34px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--tx-2);
    font-family: var(--font-mono);
    font-size: var(--font-size-2xs);
    font-variant-numeric: tabular-nums;
  }

  .sync button:active {
    border-color: var(--accent);
    background: var(--accent-muted);
  }

  .sync .value {
    color: var(--tx);
  }
</style>
