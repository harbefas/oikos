<script>
  import { onMount, onDestroy } from 'svelte'
  import * as api from '../lib/api.js'

  const player = new URLSearchParams(location.search).get('p') === '2' ? 2 : 1
  const face = ['y', 'x', 'b', 'a']
  const held = new Map()
  let turbo = $state(false)
  let swapped = $state(false)
  let wakeLock = null
  let ws = null
  let wsReady = false
  let statusTimer = 0
  let profile = $state('xbox')
  let guide = $state('XB')
  let rightStick = $state('RS')

  function buzz(ms = 10) {
    try { navigator.vibrate?.(ms) } catch (_) {}
  }

  function send(event) {
    const body = JSON.stringify({ ...event, p: player })
    if (wsReady && ws?.readyState === WebSocket.OPEN) {
      try {
        ws.send(body)
        return
      } catch (_) {
        wsReady = false
      }
    }
    api.pad(JSON.parse(body)).catch(() => {})
  }

  function connectPad() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/pad.ws${location.search}`)
    ws.onopen = () => { wsReady = true }
    ws.onclose = () => { wsReady = false }
    ws.onerror = () => {
      wsReady = false
      try { ws.close() } catch (_) {}
    }
  }

  function applyProfile(current = '') {
    const cur = current.toLowerCase()
    if (cur.includes('retroarch')) {
      profile = 'retro'
      guide = 'RET'
      rightStick = 'C'
    } else if (cur.includes('pcsx2')) {
      profile = 'playstation'
      guide = 'PS'
      rightStick = 'RS'
    } else if (cur.includes('dolphin')) {
      profile = 'nintendo'
      guide = 'GC'
      rightStick = 'C'
    } else {
      profile = 'xbox'
      guide = 'XB'
      rightStick = 'RS'
    }
  }

  async function refreshProfile() {
    const st = await api.status()
    applyProfile(st.current ?? '')
  }

  async function fullscreen() {
    const el = document.documentElement
    const fn = el.requestFullscreen || el.webkitRequestFullscreen
    if (fn && !document.fullscreenElement) {
      try { await fn.call(el) } catch (_) {}
    }
    try { await screen.orientation?.lock?.('landscape') } catch (_) {}
  }

  async function keepAwake() {
    try { wakeLock = await navigator.wakeLock?.request('screen') } catch (_) {}
  }

  function button(name, state) {
    send({ btn: name, state: state ? 1 : 0 })
  }

  function down(name) {
    buzz(face.includes(name) ? 8 : 14)
    if (turbo && face.includes(name)) {
      button(name, 1)
      let on = true
      held.set(name, setInterval(() => {
        on = !on
        button(name, on)
      }, 46))
      return
    }
    button(name, 1)
  }

  function up(name) {
    const t = held.get(name)
    if (t) {
      clearInterval(t)
      held.delete(name)
    }
    button(name, 0)
  }

  function bindButton(node, name) {
    const start = (e) => { e.preventDefault(); node.classList.add('on'); down(name) }
    const end = (e) => { e.preventDefault(); node.classList.remove('on'); up(name) }
    node.addEventListener('touchstart', start, { passive: false })
    node.addEventListener('touchend', end, { passive: false })
    node.addEventListener('touchcancel', end, { passive: false })
    node.addEventListener('mousedown', start)
    node.addEventListener('mouseup', end)
    node.addEventListener('mouseleave', end)
    return {
      destroy() {
        node.removeEventListener('touchstart', start)
        node.removeEventListener('touchend', end)
        node.removeEventListener('touchcancel', end)
        node.removeEventListener('mousedown', start)
        node.removeEventListener('mouseup', end)
        node.removeEventListener('mouseleave', end)
      }
    }
  }

  function stick(node, axis) {
    const knob = node.querySelector('i')
    let active = null
    let last = 0

    function move(point) {
      const r = node.getBoundingClientRect()
      const radius = r.width * 0.42
      let dx = point.clientX - (r.left + r.width / 2)
      let dy = point.clientY - (r.top + r.height / 2)
      const d = Math.hypot(dx, dy)
      if (d > radius) {
        dx *= radius / d
        dy *= radius / d
      }
      knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`
      const now = Date.now()
      if (now - last > 16) {
        last = now
        send({
          axis,
          x: Math.round(dx / radius * 32767),
          y: Math.round(dy / radius * 32767),
        })
      }
    }

    function reset() {
      knob.style.transform = 'translate(-50%, -50%)'
      send({ axis, x: 0, y: 0 })
    }

    const start = (e) => {
      e.preventDefault()
      const point = e.changedTouches?.[0] ?? e
      active = point.identifier ?? 'mouse'
      buzz(10)
      move(point)
    }
    const touchMove = (e) => {
      e.preventDefault()
      for (const point of e.changedTouches) if (point.identifier === active) move(point)
    }
    const touchEnd = (e) => {
      for (const point of e.changedTouches) if (point.identifier === active) {
        active = null
        reset()
      }
    }
    const mouseMove = (e) => { if (active === 'mouse') move(e) }
    const mouseEnd = () => { if (active === 'mouse') { active = null; reset() } }

    node.addEventListener('touchstart', start, { passive: false })
    node.addEventListener('touchmove', touchMove, { passive: false })
    node.addEventListener('touchend', touchEnd, { passive: false })
    node.addEventListener('touchcancel', touchEnd, { passive: false })
    node.addEventListener('mousedown', start)
    window.addEventListener('mousemove', mouseMove)
    window.addEventListener('mouseup', mouseEnd)
    return {
      destroy() {
        reset()
        node.removeEventListener('touchstart', start)
        node.removeEventListener('touchmove', touchMove)
        node.removeEventListener('touchend', touchEnd)
        node.removeEventListener('touchcancel', touchEnd)
        node.removeEventListener('mousedown', start)
        window.removeEventListener('mousemove', mouseMove)
        window.removeEventListener('mouseup', mouseEnd)
      }
    }
  }

  onMount(() => {
    connectPad()
    keepAwake()
    refreshProfile()
    statusTimer = setInterval(refreshProfile, 2000)
    try { screen.orientation?.lock?.('landscape') } catch (_) {}
    window.addEventListener('pointerdown', fullscreen, { once: true })
  })

  onDestroy(() => {
    clearInterval(statusTimer)
    try { ws?.close() } catch (_) {}
    try { wakeLock?.release?.() } catch (_) {}
    try { screen.orientation?.unlock?.() } catch (_) {}
    window.removeEventListener('pointerdown', fullscreen)
  })
</script>

<section class="gamepad" class:swapped class:retro={profile === 'retro'} class:playstation={profile === 'playstation'} class:nintendo={profile === 'nintendo'}>
  <div class="triggers left">
    <button class="trigger" use:bindButton={'z'}>LT</button>
    <button use:bindButton={'l'}>LB</button>
  </div>

  <div class="triggers right">
    <button use:bindButton={'r'}>RB</button>
    <button class="trigger" use:bindButton={'r2'}>RT</button>
  </div>

  <div class="mid">
    <button class="menu" onclick={() => (window.location.href = '?tab=home')}>☰</button>
    <button use:bindButton={'select'}>VIEW</button>
    <span class="player">P{player}</span>
    <button use:bindButton={'start'}>MENU</button>
    <button class:on={turbo} onclick={() => { turbo = !turbo; buzz(turbo ? 24 : 10) }}>TURBO</button>
  </div>

  <div class="dpad">
    <span></span><button use:bindButton={'up'}>▲</button><span></span>
    <button use:bindButton={'left'}>◀</button><span></span><button use:bindButton={'right'}>▶</button>
    <span></span><button use:bindButton={'down'}>▼</button><span></span>
  </div>

  <div class="faces">
    <span></span><button class="y" use:bindButton={'y'}>Y</button><span></span>
    <button class="x" use:bindButton={'x'}>X</button><span class="face-guide">{guide}</span><button class="b" use:bindButton={'b'}>B</button>
    <span></span><button class="a" use:bindButton={'a'}>A</button><span></span>
  </div>

  <div class="stick" use:stick={1}><i></i><button class="stick-label" use:bindButton={'l3'}>LS</button></div>
  <div class="stick small" use:stick={2}><i></i><span>{rightStick}</span></div>
  <button class="stick-label r3" use:bindButton={'r3'}>RS</button>
  <button class="swap" class:on={swapped} onclick={() => (swapped = !swapped)} title="Trocar D-pad e analógico">⇄</button>
</section>

<style>
  .gamepad {
    position: fixed;
    inset: 0;
    background: var(--bg);
    touch-action: none;
    overflow: hidden;
  }

  .triggers,
  .mid {
    position: absolute;
    z-index: 3;
    top: 2.2vh;
    display: grid;
    gap: 1.1vh;
  }

  .triggers { width: min(33vw, 260px); grid-template-columns: 1fr 1fr; }
  .triggers.left { left: 3vw; }
  .triggers.right { right: 3vw; }

  .mid {
    left: 50%;
    transform: translateX(-50%);
    grid-template-columns: auto auto auto auto auto;
    align-items: center;
    padding: .8vh 1vh;
    border: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
    border-radius: 999px;
    background: color-mix(in srgb, var(--bg) 78%, transparent);
    backdrop-filter: blur(10px);
  }

  button {
    min-height: clamp(46px, 9vh, 74px);
    border: 1px solid var(--border);
    border-radius: 2.2vh;
    background: var(--surface);
    color: var(--tx);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 600;
  }

  button.on,
  button:active {
    border-color: var(--accent);
    background: var(--accent-muted);
  }

  .triggers button { height: clamp(46px, 9vh, 74px); }
  .triggers .trigger { height: clamp(54px, 11vh, 88px); border-radius: 2.8vh; background: var(--bg-2); }
  .mid button { width: 12vh; height: 5.6vh; min-height: 0; border-radius: 3vh; font-size: var(--font-size-2xs); }
  .mid .menu { width: 5.8vh; height: 5.8vh; border-radius: 50%; font-size: 2.8vh; opacity: .78; }
  .player { padding: 0 1vh; color: var(--tx-3); font-family: var(--font-mono); font-size: var(--font-size-2xs); font-weight: 800; }

  .stick {
    position: absolute;
    left: 3vw;
    bottom: 5vh;
    width: 44vh;
    height: 44vh;
    max-width: 320px;
    max-height: 320px;
    border-radius: 999px;
    border: 2px solid var(--border-2);
    background: radial-gradient(circle, var(--surface), var(--bg-2));
  }

  .gamepad.swapped .stick:not(.small) {
    left: 20vw;
    bottom: 48vh;
    width: 27vh;
    height: 27vh;
    max-width: 195px;
    max-height: 195px;
  }

  .stick.small {
    left: auto;
    right: 28vw;
    bottom: 48vh;
    width: 27vh;
    height: 27vh;
    max-width: 195px;
    max-height: 195px;
  }

  .stick i {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 34%;
    aspect-ratio: 1;
    border-radius: 999px;
    background: var(--accent);
    border: 1px solid var(--border-2);
    transform: translate(-50%, -50%);
  }

  .stick span {
    position: absolute;
    left: 50%;
    bottom: 14%;
    transform: translateX(-50%);
    color: var(--tx-4);
    font-family: var(--font-mono);
    font-size: clamp(10px, 2.2vh, 14px);
    font-weight: 800;
    pointer-events: none;
  }

  .stick-label {
    position: absolute;
    z-index: 4;
    left: 50%;
    bottom: .8vh;
    transform: translateX(-50%);
    min-height: 0;
    padding: .6vh 1vh;
    background: transparent;
    color: var(--tx-3);
    font-family: var(--font-mono);
    font-size: 1.3vh;
    letter-spacing: .04em;
  }

  .stick-label.r3 {
    left: auto;
    right: calc(28vw + min(29vh, 210px));
    bottom: 57vh;
    transform: none;
    width: 7vh;
    height: 5vh;
  }

  .dpad, .faces {
    position: absolute;
    display: grid;
    gap: 0.8vh;
  }

  .dpad {
    left: 20vw;
    bottom: 48vh;
    grid-template-columns: repeat(3, 8.5vh);
    grid-template-rows: repeat(3, 8.5vh);
  }

  .dpad span, .faces span { min-width: 0; min-height: 0; }

  .gamepad.swapped .dpad {
    left: 3vw;
    bottom: 5vh;
    grid-template-columns: repeat(3, 14.5vh);
    grid-template-rows: repeat(3, 14.5vh);
  }

  .faces {
    right: 3vw;
    bottom: 5vh;
    grid-template-columns: repeat(3, 14.5vh);
    grid-template-rows: repeat(3, 14.5vh);
  }

  .face-guide {
    grid-column: 2;
    grid-row: 2;
    align-self: center;
    justify-self: center;
    width: 9.4vh;
    height: 9.4vh;
    min-width: 58px;
    min-height: 58px;
    border: 1px solid var(--border-2);
    border-radius: 999px;
    background: var(--surface);
    color: var(--tx-2);
    display: grid;
    place-items: center;
    font-family: var(--font-mono);
    font-size: clamp(12px, 3vh, 20px);
    font-weight: 900;
    box-shadow: inset 0 0 0 1px #fff1;
  }

  .dpad button,
  .faces button {
    min-height: 0;
  }

  .swap {
    position: absolute;
    z-index: 5;
    left: 50%;
    bottom: 3vh;
    width: 9vh;
    height: 9vh;
    min-width: 54px;
    min-height: 54px;
    border-radius: 999px;
    transform: translateX(-50%);
    font-size: 4vh;
  }

  .faces button {
    border-radius: 999px;
    font-size: 4.6vh;
  }

  .faces button.y {
    background: #d7a72f;
    color: #1f1600;
  }

  .faces button.x {
    background: #3478d4;
    color: #fff;
  }

  .faces button.b {
    background: #c94747;
    color: #fff;
  }

  .faces button.a {
    background: #2f8f54;
    color: #fff;
  }

  .gamepad.playstation .faces button.y { background: #2f8f54; color: #fff; }
  .gamepad.playstation .faces button.x { background: #3f67d4; color: #fff; }
  .gamepad.playstation .faces button.b { background: #d64949; color: #fff; }
  .gamepad.playstation .faces button.a { background: #d98a2b; color: #1b1000; }

  .gamepad.nintendo .faces button.y,
  .gamepad.retro .faces button.y { background: #6d6f77; color: #fff; }
  .gamepad.nintendo .faces button.x,
  .gamepad.retro .faces button.x { background: #3b76d7; color: #fff; }
  .gamepad.nintendo .faces button.b,
  .gamepad.retro .faces button.b { background: #d04444; color: #fff; }
  .gamepad.nintendo .faces button.a,
  .gamepad.retro .faces button.a { background: #2f8f54; color: #fff; }

  @media (max-height: 430px) {
    .faces {
      grid-template-columns: repeat(3, 13vh);
      grid-template-rows: repeat(3, 13vh);
    }

    .dpad,
    .stick.small {
      bottom: 45vh;
    }

    .stick-label.r3 {
      bottom: 54vh;
    }
  }
</style>
