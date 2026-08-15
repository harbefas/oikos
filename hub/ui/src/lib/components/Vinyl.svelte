<script>
  import { onMount, onDestroy } from 'svelte'

  let {
    cover = null,
    title = '',
    artist = '',
    album = '',
    /** seconds, from mpv */
    pos = 0,
    duration = 0,
    paused = false,
  } = $props()

  /* --- turntable physics ---------------------------------------------------
     The disc is not driven by `pos`. Tying angle to playback position makes it
     jump whenever mpv seeks, and stop dead on pause. A real platter has mass:
     it takes about a second to reach speed and coasts down slower than it spun
     up. So we integrate our own angle and ease the speed toward the target.

     The rotation is not ornament (DESIGN.md §6a): it carries play/pause state,
     readable across a room where a transport glyph would not be. */
  const RPM = 33 + 1 / 3
  const DEG_PER_MS = (RPM * 360) / 60_000
  const SPIN_UP_MS = 900
  const SPIN_DOWN_MS = 2200

  let angle = $state(0)
  let speed = $state(0) // 0..1 fraction of full RPM
  let raf = 0
  let last = 0
  let reduced = false

  function tick(now) {
    const dt = Math.min(now - last, 100) // a backgrounded tab must not lurch
    last = now

    const target = paused ? 0 : 1
    const tau = target > speed ? SPIN_UP_MS : SPIN_DOWN_MS
    // exponential approach: frame-rate independent, no overshoot
    speed += (target - speed) * (1 - Math.exp(-dt / tau))
    if (Math.abs(target - speed) < 0.0005) speed = target

    angle = (angle + DEG_PER_MS * dt * speed) % 360

    // Park the loop once it is genuinely stopped — nothing left to animate.
    if (speed === 0 && target === 0) {
      raf = 0
      return
    }
    raf = requestAnimationFrame(tick)
  }

  function wake() {
    if (reduced || raf) return
    last = performance.now()
    raf = requestAnimationFrame(tick)
  }

  $effect(() => {
    void paused // re-run when transport state flips
    wake()
  })

  onMount(() => {
    reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    // With motion off nothing spins, so `speed` becomes a plain flag and the
    // state has to be carried by the progress rule instead (see .stopped).
    if (reduced) speed = paused ? 0 : 1
    else wake()
  })

  onDestroy(() => cancelAnimationFrame(raf))

  const frac = $derived(duration > 0 ? Math.min(1, Math.max(0, pos / duration)) : 0)
  const spinning = $derived(speed > 0.02)

  // Tonearm: parked off the record, drops to the outer groove on play, then
  // tracks inward as the track runs down — a second, coarser read of progress.
  const REST = -32
  const START = -7
  const END = 11
  const armAngle = $derived(spinning ? START + (END - START) * frac : REST)

  function clock(s) {
    if (!Number.isFinite(s) || s < 0) return '0:00'
    const m = Math.floor(s / 60)
    return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
  }
</script>

<div class="vinyl-screen">
  <div class="stage">
    <!-- The record sits behind the sleeve and slides out to the right, which is
         the shape everyone recognises as "a record is playing". -->
    <div class="disc-wrap" class:out={spinning}>
      <div class="disc" style:transform="rotate({angle}deg)">
        <div class="grooves"></div>
        <div
          class="label"
          class:blank={!cover}
          style:background-image={cover ? `url(${cover})` : 'none'}
        ></div>
        <div class="spindle"></div>
      </div>

      <div class="arm" style:transform="rotate({armAngle}deg)">
        <div class="arm-pivot"></div>
        <div class="arm-tube"></div>
        <div class="arm-head"></div>
      </div>
    </div>

    <div class="sleeve" class:tilted={spinning}>
      {#if cover}
        <img src={cover} alt="" />
      {:else}
        <div class="sleeve-blank"></div>
      {/if}
    </div>
  </div>

  <div class="meta">
    <h1>{title || 'Sem faixa'}</h1>
    {#if artist || album}
      <p class="sub">
        {artist}{#if artist && album}<span class="sep">·</span>{/if}{album}
      </p>
    {/if}

    <!-- Information, not a control. No buttons here on purpose: the transport
         lives on the phone. -->
    <div class="progress" class:stopped={!spinning}>
      <div class="bar"><i style:width="{frac * 100}%"></i></div>
      <div class="times">
        <span>{clock(pos)}</span>
        <span class="state">{spinning ? '' : 'pausado'}</span>
        <span>{clock(duration)}</span>
      </div>
    </div>
  </div>
</div>

<style>
  .vinyl-screen {
    position: relative;
    z-index: 1;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-48);
    padding: var(--space-48) var(--space-64);
  }

  /* --- record + sleeve ---------------------------------------------------- */
  .stage {
    position: relative;
    display: grid;
    place-items: center;
    width: min(48vh, 42vw);
    aspect-ratio: 1;
  }

  .sleeve {
    grid-area: 1 / 1;
    width: 100%;
    aspect-ratio: 1;
    border-radius: var(--radius-art);
    overflow: hidden;
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-sm);
    transform: perspective(1200px) rotateY(0deg);
    transition: transform var(--duration-settle) var(--ease-standard);
    z-index: 2;
  }

  /* A few degrees of turn once the music starts: enough to read as depth from
     the sofa, not enough to look like a gimmick. */
  .sleeve.tilted {
    transform: perspective(1200px) rotateY(-9deg) translateX(-4%);
  }

  .sleeve img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .sleeve-blank {
    height: 100%;
    background: var(--bg-2);
  }

  .disc-wrap {
    grid-area: 1 / 1;
    width: 94%;
    aspect-ratio: 1;
    position: relative;
    transform: translateX(12%);
    transition: transform var(--duration-settle) var(--ease-standard);
    z-index: 1;
  }

  .disc-wrap.out {
    transform: translateX(32%);
  }

  /* Flat, per §6 — no glossy fill. The record reads as an object through its
     shape, its concentric 1px rules and its rotation. --radius-round is
     allowed here because the object is physically round (§6a). */
  .disc {
    position: absolute;
    inset: 0;
    border-radius: var(--radius-round);
    background: var(--bg-3);
    border: 1px solid var(--border-2);
    will-change: transform;
  }

  /* Grooves as repeating 1px rules — the structural device §6 asks for, drawn
     as a pattern because 80 separate elements would not stay crisp. */
  .grooves {
    position: absolute;
    inset: 3%;
    border-radius: var(--radius-round);
    background: repeating-radial-gradient(
      circle at 50% 50%,
      color-mix(in srgb, var(--border-3) 55%, transparent) 0px,
      color-mix(in srgb, var(--border-3) 55%, transparent) 1px,
      transparent 1px,
      transparent 4px
    );
    mask-image: radial-gradient(circle at 50% 50%, transparent 27%, #000 28%);
  }

  .label {
    position: absolute;
    inset: 33%;
    border-radius: var(--radius-round);
    background-size: cover;
    background-position: center;
    border: 1px solid var(--border-2);
  }

  .label.blank {
    background-color: var(--bg-2);
  }

  .spindle {
    position: absolute;
    inset: 48.6%;
    border-radius: var(--radius-round);
    background: var(--bg);
    border: 1px solid var(--border-2);
  }

  /* --- tonearm ------------------------------------------------------------ */
  .arm {
    position: absolute;
    top: -6%;
    right: -8%;
    width: 46%;
    height: 46%;
    transform-origin: 88% 12%;
    /* Slower than a focus move: this is an arm settling, and it doubles as the
       coarse progress read. */
    transition: transform 1.4s var(--ease-standard);
    z-index: 3;
  }

  .arm-pivot {
    position: absolute;
    top: 4%;
    right: 4%;
    width: 17%;
    aspect-ratio: 1;
    border-radius: var(--radius-round);
    background: var(--bg-3);
    border: 1px solid var(--border-2);
  }

  .arm-tube {
    position: absolute;
    top: 11%;
    right: 12%;
    width: 78%;
    height: 3.5%;
    border-radius: var(--radius-sm);
    background: var(--border-2);
    transform-origin: right center;
    transform: rotate(38deg);
  }

  .arm-head {
    position: absolute;
    top: 55%;
    left: 2%;
    width: 15%;
    height: 8%;
    border-radius: var(--radius-sm);
    background: var(--border-3);
    transform: rotate(38deg);
  }

  /* --- copy --------------------------------------------------------------- */
  .meta {
    text-align: center;
    max-width: 46ch;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-8);
  }

  /* Reading face, weight 500 — never 700 on Garamond (§3). */
  h1 {
    font-family: var(--font-serif);
    font-size: var(--font-size-2xl);
    font-weight: 500;
    line-height: var(--leading-tight);
    letter-spacing: var(--tracking-headline);
    text-wrap: balance;
    color: var(--tx);
  }

  /* Chrome label, so Inter (§3) */
  .sub {
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 500;
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
    color: var(--tx-3);
  }

  .sep {
    margin: 0 0.5em;
    opacity: 0.5;
  }

  .progress {
    margin-top: var(--space-16);
    width: min(420px, 60vw);
  }

  .bar {
    height: 2px;
    background: var(--border);
    overflow: hidden;
  }

  /* The single amber on this screen (§2) — nothing else here is accented. */
  .bar i {
    display: block;
    height: 100%;
    background: var(--accent);
    transition: width 1s linear;
  }

  /* Paused drops the accent, so the state survives with motion disabled. */
  .progress.stopped .bar i {
    background: var(--border-3);
  }

  .times {
    display: flex;
    justify-content: space-between;
    margin-top: var(--space-8);
    font-family: var(--font-mono);
    font-size: var(--font-size-2xs);
    font-variant-numeric: tabular-nums;
    color: var(--tx-4);
  }

  .state {
    letter-spacing: var(--tracking-eyebrow);
    text-transform: uppercase;
  }
</style>
