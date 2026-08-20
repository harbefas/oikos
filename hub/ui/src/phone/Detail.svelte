<script>
  let {
    item = null,
    info = {},
    loading = false,
    actionLabel = 'Tocar',
    episodes = [],
    onclose = () => {},
    onaction = () => {},
    onepisode = () => {},
  } = $props()

  let coverFailed = $state(false)

  const title = $derived(info.name ?? item?.name ?? item?.label ?? 'Detalhe')
  const cover = $derived(coverFailed ? null : (info.cover ?? item?.cover))
  const art = $derived(info.backdrop ?? item?.backdrop ?? cover)
  const hasArt = $derived(Boolean(art))
  const meta = $derived(
    [
      info.year,
      info.runtime ? `${info.runtime} min` : null,
      info.rating ? `★ ${info.rating}` : null,
      info.genres?.slice?.(0, 3).join(' · '),
    ].filter(Boolean).join(' · ')
  )

  $effect(() => {
    item
    coverFailed = false
  })
</script>

<div class="detail" class:plain={!hasArt}>
  <button class="close" onclick={onclose} aria-label="Fechar">×</button>
  <div class="backdrop" style:background-image={art ? `url(${art})` : 'none'}></div>

  <section>
    <div class="poster">
      {#if cover}
        <img src={cover} alt="" onerror={() => (coverFailed = true)} />
      {:else}
        <span>{item?.system ? '🎮' : item?.albums ? '🎵' : '🎬'}</span>
      {/if}
    </div>

    <div class="text">
      <h1>{title}</h1>
      {#if meta}<p class="meta">{meta}</p>{/if}
      {#if loading}
        <p class="overview">Carregando...</p>
      {:else if info.overview}
        <p class="overview">{info.overview}</p>
      {/if}

      {#if info.shots?.length}
        <div class="shots">
          {#each info.shots.slice(0, 5) as shot}
            <img src={shot} alt="" loading="lazy" decoding="async" />
          {/each}
        </div>
      {/if}

      <button class="primary" onclick={onaction} disabled={loading}>{actionLabel}</button>

      {#if episodes.length}
        <div class="episodes">
          <p class="eyebrow">Episódios</p>
          {#each episodes as ep, i (ep.path ?? ep.name)}
            <button class="ep" onclick={() => onepisode(i)}>{ep.name}</button>
          {/each}
        </div>
      {/if}
    </div>
  </section>
</div>

<style>
  .detail {
    position: fixed;
    z-index: 30;
    inset: 0;
    overflow-y: auto;
    background: var(--bg);
    color: var(--tx);
  }

  .backdrop {
    position: fixed;
    inset: 0 0 auto;
    height: 45dvh;
    background: center / cover no-repeat;
    opacity: 0.72;
  }

  .backdrop::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      linear-gradient(180deg, transparent 0%, var(--bg) 88%),
      linear-gradient(90deg, var(--bg) 0%, transparent 65%);
  }

  .detail.plain .backdrop {
    display: none;
  }

  .close {
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

  section {
    position: relative;
    z-index: 1;
    min-height: 100dvh;
    padding: 28dvh var(--space-16) calc(var(--space-24) + env(safe-area-inset-bottom));
    display: grid;
    grid-template-columns: minmax(116px, 34vw) 1fr;
    align-items: end;
    gap: var(--space-16);
  }

  .detail.plain section {
    align-content: center;
    align-items: center;
    padding-top: var(--space-16);
  }

  .poster {
    aspect-ratio: 2 / 3;
    border-radius: var(--radius-art);
    border: 1px solid var(--border);
    overflow: hidden;
    background: var(--surface);
    display: grid;
    place-items: center;
    color: var(--tx-3);
    font-size: 34px;
    box-shadow: var(--shadow-md);
  }

  .poster img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .text {
    min-width: 0;
    display: grid;
    gap: var(--space-10);
  }

  h1 {
    margin: 0;
    font-family: var(--font-serif);
    font-size: var(--font-size-xl);
    font-weight: 500;
    line-height: var(--leading-tight);
  }

  .meta {
    margin: 0;
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
  }

  .overview {
    grid-column: 1 / -1;
    margin: var(--space-4) 0 0;
    color: var(--tx-2);
    font-size: var(--font-size-sm);
    line-height: var(--leading-prose);
  }

  .shots {
    grid-column: 1 / -1;
    display: flex;
    gap: var(--space-8);
    overflow-x: auto;
    padding-bottom: var(--space-4);
    scrollbar-width: none;
  }

  .shots::-webkit-scrollbar {
    display: none;
  }

  .shots img {
    flex: 0 0 52vw;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
  }

  .primary {
    grid-column: 1 / -1;
    min-height: 48px;
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    background: var(--accent);
    color: var(--bg);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 700;
  }

  .primary:disabled {
    opacity: 0.6;
  }

  .episodes {
    grid-column: 1 / -1;
    display: grid;
    gap: var(--space-8);
    margin-top: var(--space-8);
  }

  .eyebrow {
    margin: 0;
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
  }

  .ep {
    min-height: 44px;
    padding: 0 var(--space-12);
    text-align: left;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--tx);
    font-family: var(--font-sans);
    font-size: var(--font-size-sm);
  }

  .ep:active {
    border-color: var(--accent);
    background: var(--bg-3);
  }

  @media (min-width: 700px) {
    section {
      max-width: 820px;
      margin: 0 auto;
      grid-template-columns: 220px 1fr;
      padding-top: 24dvh;
    }

    .shots img {
      flex-basis: 220px;
    }
  }
</style>
