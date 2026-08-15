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
  <div class="head">
    {#if now.cover}
      <img class="art" src={now.cover} alt="" />
    {/if}
    <div class="text">
      <p class="title">{now.title ?? '—'}</p>
      <p class="time">{clock(now.pos)} / {clock(now.duration)}</p>
    </div>
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
</div>

<style>
  .transport {
    background: var(--bg-2);
    border-top: 1px solid var(--border);
    padding: var(--space-12) var(--space-16);
    display: flex;
    flex-direction: column;
    gap: var(--space-12);
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-12);
    min-width: 0;
  }

  .art {
    width: 44px;
    height: 44px;
    object-fit: cover;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    flex: 0 0 auto;
  }

  .text {
    min-width: 0;
  }

  /* Track title is content, so the reading face (§3). */
  .title {
    font-family: var(--font-serif);
    font-size: var(--font-size-sm);
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
</style>
