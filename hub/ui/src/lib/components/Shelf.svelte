<script>
  import Card from './Card.svelte'

  let {
    title = '',
    items = [],
    /** index of the focused card, or -1 when this row is not the active one */
    focus = -1,
    ratio = '2 / 3',
    onselect = () => {},
  } = $props()

  let track = $state()

  /* Keep the focused card pinned near the left third rather than scrolling it
     to the edge. Netflix does this so the row always shows what comes next —
     the cards ahead of you are the point. */
  $effect(() => {
    if (focus < 0 || !track) return
    const el = track.children[focus]
    if (!el) return
    const target = el.offsetLeft - track.clientWidth * 0.3
    track.scrollTo({ left: Math.max(0, target), behavior: 'smooth' })
  })
</script>

<section class="shelf" class:active={focus >= 0}>
  <h2>{title}</h2>
  <div class="track" bind:this={track}>
    {#each items as item, i (item.id ?? item.path ?? item.name)}
      <Card
        {item}
        {ratio}
        focused={i === focus}
        offset={focus < 0 ? 0 : i - focus}
        {onselect}
      />
    {/each}
    <!-- trailing spacer so the last card can still reach the pinned position -->
    <div class="tail"></div>
  </div>
</section>

<style>
  .shelf {
    margin-bottom: var(--space-32);
  }

  /* Eyebrow, §3: Inter, 2xs, tracked, uppercase, --tx-3. Deliberately not
     amber — the focused card owns the single accent (§2). The active row is
     marked by contrast alone. */
  h2 {
    font-family: var(--font-sans);
    font-size: var(--label-size);
    font-weight: 500;
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
    color: var(--tx-4);
    margin: 0 0 var(--space-12) var(--space-4);
    transition: color var(--duration-base) var(--ease-standard);
  }

  .shelf.active h2 {
    color: var(--tx-2);
  }

  .track {
    display: flex;
    gap: var(--space-16);
    /* the row scrolls, but never shows a scrollbar on a TV */
    overflow-x: auto;
    scrollbar-width: none;
    /* room for the focused card to grow and lift without clipping */
    padding: var(--space-24) var(--space-4);
    transform-style: preserve-3d;
  }

  .track::-webkit-scrollbar {
    display: none;
  }

  .tail {
    flex: 0 0 40vw;
  }
</style>
