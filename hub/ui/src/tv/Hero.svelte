<script>
  import * as api from '../lib/api.js'

  let { item = null } = $props()

  /* Detail is fetched lazily and only for the thing you have settled on, so
     flying down a row does not fire twenty Jellyfin requests. */
  let info = $state(null)
  let dwell = 0
  let token = 0

  $effect(() => {
    const it = item
    clearTimeout(dwell)
    if (!it?.id) { info = null; return }
    dwell = setTimeout(async () => {
      const mine = ++token
      const d = await api.detail(it.id)
      if (mine === token) info = d
    }, 320)
    return () => clearTimeout(dwell)
  })

  const meta = $derived(
    [
      info?.year,
      info?.runtime ? `${info.runtime} min` : null,
      info?.rating ? `★ ${info.rating}` : null,
      info?.genres?.slice(0, 3).join(' · ') || null,
    ]
      .filter(Boolean)
      .join('  ·  ')
  )
</script>

<div class="hero">
  {#key item?.id ?? item?.name}
    <div class="inner">
      <h1>{item?.name ?? ''}</h1>
      {#if meta}<p class="meta">{meta}</p>{/if}
      {#if info?.overview}<p class="overview">{info.overview}</p>{/if}
    </div>
  {/key}
</div>

<style>
  .hero {
    /* Fixed, not min-height: a variable hero would shift every shelf below it
       each time focus moved. The floor is what a two-line title plus a clamped
       synopsis actually measures -- below that the content overflows upward
       (align-items: flex-end) and the header crops it. */
    height: clamp(190px, 24vh, 300px);
    display: flex;
    align-items: flex-end;
    padding: 0 4px 30px;
    max-width: 62ch;
  }

  /* Staggered entrance: title first, then the supporting copy. Reads as one
     considered move instead of three things appearing at once. */
  .inner > * {
    animation: rise var(--duration-settle) var(--ease-standard) both;
  }

  .inner > :nth-child(2) {
    animation-delay: 60ms;
  }

  .inner > :nth-child(3) {
    animation-delay: 110ms;
  }

  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(12px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Weight 500 — §3 forbids 700 on Garamond. */
  /* One line, always. The title is the only part of the hero whose height is
     not already bounded, and a two-line title is what pushed the content past
     the box and up under the header. */
  h1 {
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-family: var(--font-serif);
    font-size: var(--font-size-4xl);
    font-weight: 500;
    line-height: var(--leading-tight);
    letter-spacing: var(--tracking-headline);
    text-wrap: balance;
    color: var(--tx);
  }

  /* Eyebrow: chrome data, so Inter (§3) */
  .meta {
    margin-top: var(--space-12);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 500;
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
    color: var(--tx-3);
  }

  /* Synopsis is prose, so it stays on the reading face — this is the marker
     §1 calls out: Garamond as an actual reading face, not headline veneer. */
  /* A short panel cannot seat a two-line title and three lines of prose in the
     space the shelves can spare, so the synopsis gives up a line there rather
     than the hero growing and eating the next row's peek. */

  .overview {
    margin-top: var(--space-12);
    font-family: var(--font-serif);
    font-size: var(--font-size-sm);
    line-height: var(--leading-prose);
    text-wrap: pretty;
    color: var(--tx-2);
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
