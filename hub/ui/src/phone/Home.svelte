<script>
  import { onMount } from 'svelte'
  import * as api from '../lib/api.js'

  let { onselect = () => {}, onlaunch = () => {} } = $props()

  let resume = $state([])
  let recent = $state([])
  let downloads = $state([])
  let apps = $state([])
  let loading = $state(true)

  const featured = $derived(resume[0] ?? recent[0] ?? null)

  onMount(async () => {
    const [r1, r2, d, a] = await Promise.all([
      api.resume(),
      api.recent(),
      api.downloads(),
      api.apps(),
    ])
    resume = r1
    recent = r2
    downloads = d
    apps = a
    loading = false
  })

  async function launch(id) {
    await api.launchApp(id)
    onlaunch()
  }
</script>

<div class="home">
  {#if loading}
    <p class="hint">Carregando...</p>
  {/if}

  {#if featured}
    <button class="hero" onclick={() => onselect(featured)}>
      {#if featured.backdrop || featured.cover}
        <img src={featured.backdrop ?? featured.cover} alt="" loading="lazy" decoding="async" />
      {:else}
        <span class="blank">{featured.system ? '🎮' : '▶'}</span>
      {/if}
      <span class="shade"></span>
      <span class="label">{featured.system ? featured.label ?? 'Jogo' : featured.type === 'movie' ? 'Filme' : 'Continuar'}</span>
      <strong>{featured.name}</strong>
    </button>
  {/if}

  {#if resume.length}
    <section>
      <h2>Continuar</h2>
      <div class="rail">
        {#each resume as item (item.id ?? item.path ?? item.name)}
          <button class="wide" onclick={() => onselect(item)}>
            {#if item.backdrop || item.cover}
              <img src={item.backdrop ?? item.cover} alt="" loading="lazy" decoding="async" />
            {:else}
              <span class="blank">{item.system ? '🎮' : '▶'}</span>
            {/if}
            <span>{item.name}</span>
          </button>
        {/each}
      </div>
    </section>
  {/if}

  {#if recent.length}
    <section>
      <h2>Recentes</h2>
      <div class="rail posters">
        {#each recent as item (item.id ?? item.path ?? item.name)}
          <button class="poster" onclick={() => onselect(item)}>
            {#if item.cover}
              <img src={item.cover} alt="" loading="lazy" decoding="async" />
            {:else}
              <span class="blank">{item.system ? '🎮' : '🎬'}</span>
            {/if}
            <span>{item.name}</span>
          </button>
        {/each}
      </div>
    </section>
  {/if}

  {#if downloads.length}
    <section>
      <h2>Downloads</h2>
      <div class="downloads">
        {#each downloads.slice(0, 4) as item (item.title)}
          <div class="download">
            <span>{item.kind}</span>
            <b>{item.title}</b>
            <i><em style:width="{item.percent}%"></em></i>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if apps.length}
    <section>
      <h2>Atalhos</h2>
      <div class="apps">
        {#each apps.slice(0, 8) as app (app.id)}
          <button onclick={() => launch(app.id)}>
            <span>{app.icon}</span>
            {app.label}
          </button>
        {/each}
      </div>
    </section>
  {/if}

  {#if !loading && !resume.length && !recent.length && !downloads.length && !apps.length}
    <p class="hint">Nada aqui.</p>
  {/if}
</div>

<style>
  .home {
    display: grid;
    gap: var(--space-22);
    padding-bottom: 92px;
    max-width: 100%;
    overflow-x: hidden;
  }

  h2 {
    margin: 0 0 var(--space-12);
    font-family: var(--font-serif);
    font-size: var(--font-size-lg);
    font-weight: 500;
    color: var(--tx);
  }

  section {
    min-width: 0;
    overflow: hidden;
  }

  .hint {
    color: var(--tx-3);
    font-size: var(--font-size-sm);
  }

  .rail {
    display: flex;
    gap: var(--space-12);
    overflow-x: auto;
    max-width: 100%;
    padding-bottom: var(--space-4);
    scrollbar-width: none;
  }

  .rail::-webkit-scrollbar {
    display: none;
  }

  button {
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--tx);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    text-align: left;
  }

  button:active {
    border-color: var(--accent);
    background: var(--bg-3);
  }

  .hero {
    position: relative;
    width: 100%;
    min-height: 214px;
    overflow: hidden;
    padding: 0;
    border-radius: var(--radius-md);
    display: block;
  }

  .hero img,
  .hero .blank {
    position: absolute;
    inset: 0;
  }

  .hero .shade {
    position: absolute;
    inset: 0;
    background:
      linear-gradient(180deg, rgb(0 0 0 / 0.05), rgb(0 0 0 / 0.7)),
      linear-gradient(90deg, rgb(0 0 0 / 0.45), transparent 65%);
  }

  .hero .label {
    position: absolute;
    left: var(--space-12);
    bottom: 58px;
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
  }

  .hero strong {
    position: absolute;
    left: var(--space-12);
    right: var(--space-12);
    bottom: var(--space-12);
    display: -webkit-box;
    max-width: calc(100% - var(--space-24));
    overflow: hidden;
    overflow-wrap: anywhere;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    color: #fff;
    font-family: var(--font-serif);
    font-size: var(--font-size-xl);
    font-weight: 600;
    line-height: 1.05;
    text-shadow: 0 2px 16px rgb(0 0 0 / 0.8);
  }

  .wide,
  .poster {
    position: relative;
    flex: 0 0 74vw;
    aspect-ratio: 16 / 9;
    padding: 0;
    overflow: hidden;
  }

  .poster {
    flex-basis: 118px;
    aspect-ratio: 2 / 3;
  }

  img,
  .blank {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: grid;
    place-items: center;
    background: var(--bg-2);
    color: var(--tx-3);
    font-size: 30px;
  }

  .wide > span:last-child,
  .poster > span:last-child {
    position: absolute;
    inset: auto 0 0 0;
    padding: var(--space-24) var(--space-8) var(--space-8);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: linear-gradient(transparent, var(--nm-grad) 60%);
  }

  .downloads {
    display: grid;
    gap: var(--space-8);
  }

  .download {
    min-height: 62px;
    display: grid;
    gap: 2px;
    padding: var(--space-8) var(--space-12);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    min-width: 0;
    overflow: hidden;
  }

  .download span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
  }

  .download b {
    min-width: 0;
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 600;
  }

  .download i {
    height: 3px;
    overflow: hidden;
    background: var(--border);
  }

  .download em {
    display: block;
    height: 100%;
    background: var(--accent);
  }

  .apps {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-8);
  }

  .apps button {
    min-height: 74px;
    display: grid;
    place-items: center;
    gap: 2px;
    text-align: center;
    padding: var(--space-8);
  }

  .apps span {
    font-size: 24px;
    line-height: 1;
  }
</style>
