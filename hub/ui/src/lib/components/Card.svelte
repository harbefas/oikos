<script>
  let {
    item,
    focused = false,
    /** distance in cards from the focused one; drives the 3D falloff */
    offset = 0,
    ratio = '2 / 3',
    onselect = () => {},
  } = $props()

  /* Depth ramp, DESIGN.md §6a: at three metres a 1px border cannot say which
     card has focus, so z-position does. Neighbours rotate away and fall back;
     the focused card is the only thing at z=0 facing the viewer.

     Both are emitted as unitless multipliers of --card-tilt-max /
     --card-depth-step so that the reduced-motion block in tokens.css, which
     zeroes those tokens, actually reaches them. A degree value computed here
     would ignore the media query entirely. */
  const tilt = $derived(Math.max(-1, Math.min(1, -offset / 3)))
  const depth = $derived(-Math.min(Math.abs(offset), 4))
  const dim = $derived(Math.max(0.42, 1 - Math.abs(offset) * 0.13))
  const fallback = $derived(item.icon ?? (item._download ? '📥' : item.system ? '🎮' : item.albums ? '🎵' : ''))
</script>

<button
  class="card"
  class:focused
  style:aspect-ratio={ratio}
  style:--tilt="calc({tilt} * var(--card-tilt-max))"
  style:--depth="calc({depth} * var(--card-depth-step))"
  style:--dim={dim}
  style:view-transition-name={focused ? 'focused-card' : 'none'}
  onclick={() => onselect(item)}
>
  {#if item.cover}
    <img src={item.cover} alt="" loading="lazy" decoding="async" />
  {:else}
    <span class="blank">{fallback}</span>
  {/if}

  {#if item.system}
    <span class="badge">{item.system}</span>
  {/if}

  <span class="name" class:always={!item.cover}>{item.name}</span>
</button>

<style>
  .card {
    position: relative;
    flex: 0 0 var(--card-w);
    width: var(--card-w);
    padding: 0;
    /* artwork container, so --radius-art rather than the 8px chrome cap */
    border-radius: var(--radius-art);
    border: 1px solid var(--border);
    overflow: hidden;
    background: var(--surface);
    font: inherit;
    color: inherit;
    cursor: pointer;
    display: grid;
    place-items: center;

    transform: perspective(var(--shelf-perspective)) rotateY(var(--tilt))
      translateZ(var(--depth));
    filter: brightness(var(--dim));
    transition:
      transform var(--duration-settle) var(--ease-focus),
      filter var(--duration-settle) var(--ease-standard),
      border-color var(--duration-base) var(--ease-standard),
      box-shadow var(--duration-settle) var(--ease-standard);
    will-change: transform, filter;
  }

  /* The one amber on this screen (DESIGN.md §2). Row labels, badges and the
     progress rule all stay neutral so this reads as the single active thing. */
  .card.focused {
    transform: perspective(var(--shelf-perspective)) rotateY(0deg)
      translateZ(0) scale(var(--card-focus-scale))
      translateY(var(--card-focus-lift));
    filter: brightness(1);
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
    z-index: 3;
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
    color: var(--tx-2);
    font-size: clamp(36px, 6vw, 68px);
    display: grid;
    place-items: center;
  }

  /* Dense truncated label — Inter per §3 ("UI labels, dense data"), not the
     reading face. The wash behind it is a scrim over artwork, §6a. */
  .name {
    position: absolute;
    inset: auto 0 0 0;
    padding: var(--space-24) var(--space-12) var(--space-12);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 500;
    line-height: var(--leading-ui);
    color: var(--tx);
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: linear-gradient(transparent, var(--nm-grad) 55%);
    opacity: 0;
    transition: opacity var(--duration-base) var(--ease-standard);
  }

  .card.focused .name {
    opacity: 1;
  }

  .name.always {
    opacity: 1;
  }

  /* Eyebrow treatment per §3 */
  .badge {
    position: absolute;
    top: var(--space-8);
    right: var(--space-8);
    background: var(--bg-3);
    border: 1px solid var(--border-2);
    border-radius: var(--radius-sm);
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 500;
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
    padding: 2px 6px;
  }
</style>
