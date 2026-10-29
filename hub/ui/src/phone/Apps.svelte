<script>
  import * as api from '../lib/api.js'

  let { items = [], onadded = () => {}, onlaunch = () => {} } = $props()

  let label = $state('')
  let url = $state('')
  let busy = $state(false)
  let msg = $state('')

  // Servicos do homelab (~/.config/oikos/services.json): abrem no navegador do
  // celular, nao na TV, pelo mesmo host usado pra abrir o hub (LAN ou Tailscale).
  let services = $state([])
  const host = `${location.protocol}//${location.hostname}`
  api.services().then((s) => (services = s))

  async function launch(id) {
    await api.launchApp(id)
    onlaunch()
  }

  async function add() {
    msg = ''
    const name = label.trim()
    const href = url.trim()
    if (!name || !href) {
      msg = 'Nome e URL obrigatorios.'
      return
    }
    busy = true
    try {
      await api.addWebApp({ label: name, url: href, icon: '🌐', kiosk: true })
      label = ''
      url = ''
      msg = 'Atalho adicionado.'
      await onadded()
    } catch (_) {
      msg = 'URL invalida.'
    } finally {
      busy = false
    }
  }
</script>

<form class="add" onsubmit={(e) => { e.preventDefault(); add() }}>
  <input bind:value={label} placeholder="Nome" autocomplete="off" />
  <input bind:value={url} placeholder="https://..." inputmode="url" autocomplete="url" />
  <button type="submit" disabled={busy}>{busy ? 'Adicionando' : 'Adicionar'}</button>
  {#if msg}<p>{msg}</p>{/if}
</form>

<div class="apps">
  {#each items as item (item.id)}
    <button class="app-tile" onclick={() => launch(item.id)}>
      <span class="icon">{item.icon}</span>
      <span>{item.label}</span>
    </button>
  {/each}
</div>

{#if services.length}
  <h3>Serviços</h3>
  <div class="apps">
    {#each services as svc (svc.port)}
      <a class="app-tile" href="{host}:{svc.port}/" target="_blank" rel="noopener">
        <span class="dot" class:up={svc.up} title={svc.up ? 'no ar' : 'fora do ar'}></span>
        <span class="icon">{svc.icon}</span>
        <span>{svc.label}</span>
      </a>
    {/each}
  </div>
{/if}

<style>
  .add {
    display: grid;
    gap: var(--space-8);
    margin-bottom: var(--space-16);
  }

  input,
  button {
    min-height: 44px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
  }

  input {
    background: var(--surface);
    color: var(--tx);
    padding: 0 var(--space-12);
  }

  input:focus {
    outline: none;
    border-color: var(--accent);
  }

  button {
    background: none;
    color: var(--tx);
  }

  button:active {
    background: var(--bg-3);
    border-color: var(--border-2);
  }

  button:disabled {
    color: var(--tx-4);
  }

  p {
    color: var(--tx-3);
    font-size: var(--font-size-2xs);
  }

  .apps {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
    gap: var(--space-12);
  }

  .app-tile {
    min-height: 112px;
    padding: var(--space-16);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--tx);
    font-size: var(--font-size-xs);
    text-decoration: none;
    position: relative;
  }

  .dot {
    position: absolute;
    top: var(--space-8);
    right: var(--space-8);
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--red);
  }

  .dot.up {
    background: var(--green);
  }

  h3 {
    margin: var(--space-16) 0 var(--space-8);
    color: var(--tx-3);
    font-size: var(--font-size-xs);
  }

  .icon {
    font-size: 28px;
    line-height: 1;
  }
</style>
