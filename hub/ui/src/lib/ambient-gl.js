/* ===========================================================================
   Ambient backdrop renderer.

   One fullscreen WebGL2 pass that holds two images and dissolves between them
   while each drifts (Ken Burns). Doing it on the GPU rather than with two
   stacked <img> elements buys three things CSS cannot: a noise-driven dissolve
   instead of a flat opacity fade, film grain that does not band on large flat
   areas, and a glow tinted by the artwork's own dominant colour.

   The loop is stoppable. The TV kiosk shares its GPU with mpv and emulators,
   so whenever something else takes focus the caller calls stop() and this
   costs nothing until it is needed again.
   =========================================================================== */

const VERT = `#version 300 es
out vec2 vUV;
void main() {
  // fullscreen triangle, no vertex buffer needed
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  vUV = p;
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`

const FRAG = `#version 300 es
precision highp float;

in vec2 vUV;
out vec4 frag;

uniform sampler2D uPrev;
uniform sampler2D uNext;
uniform vec2  uPrevSize;
uniform vec2  uNextSize;
uniform vec2  uRes;
uniform float uProgress;   // 0..1 dissolve, prev -> next
uniform float uPrevT;      // 0..1 ken burns phase, per image
uniform float uNextT;
uniform float uTime;
uniform vec3  uTint;       // dominant colour of the incoming art
uniform float uGrain;
uniform float uBloom;
uniform float uDark;       // how much to sink the whole thing back

// --- value noise, for the dissolve mask and the grain -----------------------
float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x),
             mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

// --- cover-fit the image to the canvas, then zoom and drift it --------------
vec2 kenBurns(vec2 uv, vec2 img, float t) {
  vec2 c = uv - 0.5;
  float ia = img.x / max(img.y, 1.0);
  float ca = uRes.x / max(uRes.y, 1.0);
  // crop the axis that overflows so the art always fills the frame
  if (ca > ia) c.y *= ia / ca; else c.x *= ca / ia;
  c /= mix(1.0, 1.12, t);                 // slow push in
  c += vec2(0.020, -0.015) * (t - 0.5);   // slow pan, centred on the midpoint
  return c + 0.5;
}

vec3 sampleArt(sampler2D tex, vec2 size, float t) {
  vec2 uv = kenBurns(vUV, size, t);
  // clamp rather than wrap: a pan that runs off the edge should smear the
  // edge pixel, not tile the poster
  return texture(tex, clamp(uv, 0.001, 0.999)).rgb;
}

void main() {
  vec3 prev = sampleArt(uPrev, uPrevSize, uPrevT);
  vec3 next = sampleArt(uNext, uNextSize, uNextT);

  // Dissolve with a soft noise threshold. Large-scale noise means the new
  // image seeps in across the frame instead of the whole plane changing
  // opacity at once.
  float n = vnoise(vUV * 3.0);
  float m = smoothstep(0.0, 1.0, clamp(uProgress * 1.6 - n * 0.6, 0.0, 1.0));
  vec3 col = mix(prev, next, m);

  // Glow in the artwork's own colour, strongest at the centre where the
  // subject usually is. Keeps the frame from reading as a flat photo.
  float r = length((vUV - 0.5) * vec2(uRes.x / max(uRes.y, 1.0), 1.0));
  float glow = exp(-r * r * 2.2);
  col += uTint * glow * uBloom;

  // Vignette, then sink the whole thing so foreground text stays on top of it
  col *= 1.0 - smoothstep(0.45, 1.15, r) * 0.55;
  col *= 1.0 - uDark;

  // Grain last, so it sits over everything and hides banding in the gradients
  float g = hash(vUV * uRes + fract(uTime) * 977.0) - 0.5;
  col += g * uGrain;

  frag = vec4(col, 1.0);
}`

function compile(gl, type, src) {
  const s = gl.createShader(type)
  gl.shaderSource(s, src)
  gl.compileShader(s)
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(s)
    gl.deleteShader(s)
    throw new Error(`shader: ${log}`)
  }
  return s
}

function makeTexture(gl) {
  const t = gl.createTexture()
  gl.bindTexture(gl.TEXTURE_2D, t)
  // 1x1 transparent placeholder so the first frame has something bound
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE,
    new Uint8Array([0, 0, 0, 255]))
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
  return t
}

const KEN_BURNS_MS = 26_000 // one full drift, deliberately longer than a dwell
const FADE_MS = 900

export function createAmbient(canvas, opts = {}) {
  const gl = canvas.getContext('webgl2', {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    powerPreference: 'low-power',
    preserveDrawingBuffer: false,
  })
  if (!gl) return null // caller falls back to the CSS crossfade

  const prog = gl.createProgram()
  gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VERT))
  gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FRAG))
  gl.linkProgram(prog)
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    throw new Error(`link: ${gl.getProgramInfoLog(prog)}`)
  }
  gl.useProgram(prog)

  const u = (n) => gl.getUniformLocation(prog, n)
  const U = {
    prev: u('uPrev'), next: u('uNext'),
    prevSize: u('uPrevSize'), nextSize: u('uNextSize'),
    res: u('uRes'), progress: u('uProgress'),
    prevT: u('uPrevT'), nextT: u('uNextT'),
    time: u('uTime'), tint: u('uTint'),
    grain: u('uGrain'), bloom: u('uBloom'), dark: u('uDark'),
  }

  const texPrev = makeTexture(gl)
  const texNext = makeTexture(gl)
  gl.uniform1i(U.prev, 0)
  gl.uniform1i(U.next, 1)

  const vao = gl.createVertexArray() // required in WebGL2 even with no attributes
  gl.bindVertexArray(vao)

  const state = {
    prevSize: [1, 1], nextSize: [1, 1],
    prevStart: 0, nextStart: 0,
    fadeStart: -Infinity,
    tint: [0, 0, 0],
    grain: opts.grain ?? 0.035,
    bloom: opts.bloom ?? 0.18,
    dark: opts.dark ?? 0.25,
    dpr: 1,
  }

  let raf = 0
  let running = false
  let lost = false

  canvas.addEventListener('webglcontextlost', (e) => {
    e.preventDefault()
    lost = true
    stop()
  })

  function resize() {
    // The TV is 1080p and this is a background: capping DPR keeps the
    // fragment count sane on the laptop iGPU without any visible cost.
    const dpr = Math.min(window.devicePixelRatio || 1, opts.maxDpr ?? 1.5)
    const w = Math.max(1, Math.round(canvas.clientWidth * dpr))
    const h = Math.max(1, Math.round(canvas.clientHeight * dpr))
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
      gl.viewport(0, 0, w, h)
    }
    state.dpr = dpr
  }

  function frame(now) {
    if (!running || lost) return
    resize()

    const fade = Math.min(1, (now - state.fadeStart) / FADE_MS)
    const kb = (start) => Math.min(1, ((now - start) % (KEN_BURNS_MS * 2)) / KEN_BURNS_MS)

    gl.uniform2f(U.res, canvas.width, canvas.height)
    gl.uniform2f(U.prevSize, state.prevSize[0], state.prevSize[1])
    gl.uniform2f(U.nextSize, state.nextSize[0], state.nextSize[1])
    gl.uniform1f(U.progress, fade)
    gl.uniform1f(U.prevT, kb(state.prevStart))
    gl.uniform1f(U.nextT, kb(state.nextStart))
    gl.uniform1f(U.time, now / 1000)
    gl.uniform3f(U.tint, state.tint[0], state.tint[1], state.tint[2])
    gl.uniform1f(U.grain, state.grain)
    gl.uniform1f(U.bloom, state.bloom)
    gl.uniform1f(U.dark, state.dark)

    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, texPrev)
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, texNext)
    gl.drawArrays(gl.TRIANGLES, 0, 3)

    raf = requestAnimationFrame(frame)
  }

  function start() {
    if (running || lost) return
    running = true
    raf = requestAnimationFrame(frame)
  }

  function stop() {
    running = false
    cancelAnimationFrame(raf)
  }

  /* Push a decoded image in as the new backdrop. The old "next" becomes
     "prev" so the dissolve always runs from what is currently on screen —
     interrupting a fade mid-way still looks continuous. */
  function show(img, tint) {
    if (lost) return
    const now = performance.now()
    const fade = Math.min(1, (now - state.fadeStart) / FADE_MS)

    // Copy the current next -> prev by re-uploading. Cheap at these sizes and
    // avoids a framebuffer blit path that some drivers get wrong.
    if (fade >= 1 && state.lastImg) {
      gl.bindTexture(gl.TEXTURE_2D, texPrev)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, state.lastImg)
      state.prevSize = [...state.nextSize]
      state.prevStart = state.nextStart
    }

    gl.bindTexture(gl.TEXTURE_2D, texNext)
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img)

    state.lastImg = img
    state.nextSize = [img.naturalWidth || img.width, img.naturalHeight || img.height]
    state.nextStart = now
    state.fadeStart = now
    if (tint) state.tint = tint
  }

  function set(k, v) { state[k] = v }

  function destroy() {
    stop()
    gl.deleteTexture(texPrev)
    gl.deleteTexture(texNext)
    gl.deleteProgram(prog)
    gl.deleteVertexArray(vao)
  }

  resize()
  return { start, stop, show, set, destroy, get running() { return running } }
}

/* Average colour of an image, sampled tiny. Used for the glow tint — a full
   dominant-colour cluster would be more correct but this is a background
   wash, and the mean of a poster is already the colour it reads as. */
const SWATCH = 12
let swatchCanvas = null

export function dominantColor(img) {
  if (!swatchCanvas) {
    swatchCanvas = document.createElement('canvas')
    swatchCanvas.width = swatchCanvas.height = SWATCH
  }
  const ctx = swatchCanvas.getContext('2d', { willReadFrequently: true })
  try {
    ctx.drawImage(img, 0, 0, SWATCH, SWATCH)
    const d = ctx.getImageData(0, 0, SWATCH, SWATCH).data
    let r = 0, g = 0, b = 0
    for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2] }
    const n = (d.length / 4) * 255
    // Push toward saturation: the raw mean is muddy, and the glow wants the
    // hue the poster reads as, not its greyness.
    const c = [r / n, g / n, b / n]
    const mean = (c[0] + c[1] + c[2]) / 3
    return c.map((x) => Math.min(1, mean + (x - mean) * 2.2))
  } catch {
    return [0, 0, 0] // tainted canvas (remote art without CORS) — no tint
  }
}

/* Decode an image off the main thread where possible. Returns null instead of
   throwing so a missing backdrop just means "keep the current one". */
export function loadImage(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null)
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.decoding = 'async'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}
