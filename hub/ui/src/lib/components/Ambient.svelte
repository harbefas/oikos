<script>
  import { onMount, onDestroy } from 'svelte'
  import { createAmbient, loadImage, dominantColor } from '../ambient-gl.js'

  let {
    /** URL of the art to show behind everything. Changing it crossfades. */
    src = null,
    /** Stop rendering entirely — used when mpv or a game takes the screen. */
    paused = false,
    grain = 0.035,
    bloom = 0.18,
    dark = 0.25,
  } = $props()

  let canvas
  // $state, not a plain let: the effects below start/stop the renderer and
  // must re-run once onMount assigns it. Without this the loop never starts.
  let ambient = $state(null)
  let fallbackSrc = $state(null) // CSS path when there is no WebGL2
  let fallbackPrev = $state(null)

  // Debounce: holding a direction on the d-pad flies through a dozen cards and
  // we only want the one it lands on to load.
  const DWELL_MS = 260
  let dwell = 0
  let token = 0

  async function apply(url) {
    const mine = ++token
    const img = await loadImage(url)
    if (mine !== token || !img) return // superseded, or art missing: keep current

    if (ambient) {
      ambient.show(img, dominantColor(img))
    } else {
      fallbackPrev = fallbackSrc
      fallbackSrc = url
    }
  }

  $effect(() => {
    const url = src
    clearTimeout(dwell)
    dwell = setTimeout(() => apply(url), DWELL_MS)
  })

  $effect(() => {
    if (!ambient) return
    if (paused || document.hidden) ambient.stop()
    else ambient.start()
  })

  $effect(() => {
    ambient?.set('grain', grain)
    ambient?.set('bloom', bloom)
    ambient?.set('dark', dark)
  })

  function onVisibility() {
    if (!ambient) return
    if (document.hidden) ambient.stop()
    else if (!paused) ambient.start()
  }

  onMount(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!reduce) {
      try {
        ambient = createAmbient(canvas, { grain, bloom, dark })
      } catch (e) {
        console.warn('ambient: falling back to CSS', e)
        ambient = null
      }
    }
    ambient?.start()
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('resize', () => ambient?.set('dpr', 0))
  })

  onDestroy(() => {
    clearTimeout(dwell)
    document.removeEventListener('visibilitychange', onVisibility)
    ambient?.destroy()
  })
</script>

<div class="ambient" aria-hidden="true">
  <canvas bind:this={canvas} class:hidden={!ambient}></canvas>

  {#if !ambient}
    <!-- No WebGL2 (or reduced motion): two stacked layers, plain crossfade.
         Same composition, none of the theatre. -->
    {#if fallbackPrev}
      <div class="layer" style:background-image="url({fallbackPrev})"></div>
    {/if}
    {#if fallbackSrc}
      {#key fallbackSrc}
        <div class="layer fade-in" style:background-image="url({fallbackSrc})"></div>
      {/key}
    {/if}
  {/if}

  <!-- Scrim lives in CSS, not the shader, so it follows the theme tokens.
       Without it, light-theme text over a bright backdrop is unreadable. -->
  <div class="scrim"></div>
</div>

<style>
  .ambient {
    position: fixed;
    inset: 0;
    z-index: 0;
    overflow: hidden;
    background: var(--bg);
  }

  canvas,
  .layer {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  canvas.hidden {
    display: none;
  }

  .layer {
    background-size: cover;
    background-position: center;
    filter: brightness(0.7) saturate(1.1);
  }

  .fade-in {
    animation: fade var(--duration-ambient) var(--ease-standard) both;
  }

  @keyframes fade {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  /* Bottom-heavy so rows and titles sit on solid ground, with a side wash so
     the left rail and hero copy keep contrast over a busy frame. */
  .scrim {
    position: absolute;
    inset: 0;
    background:
      linear-gradient(0deg, var(--scrim) 0%, var(--scrim) 18%, transparent 68%),
      linear-gradient(90deg, var(--scrim-soft) 0%, transparent 55%);
  }
</style>
