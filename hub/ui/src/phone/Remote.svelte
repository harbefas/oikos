<script>
  import * as api from '../lib/api.js'

  let q = $state('')
  let timer = 0

  function press(key) {
    api.remote(key)
  }

  function sendQuery() {
    clearTimeout(timer)
    timer = setTimeout(() => api.setSearchQuery(q), 120)
  }
</script>

<section class="remote">
  <label>
    <span>Busca na TV</span>
    <input
      bind:value={q}
      oninput={sendQuery}
      placeholder="Digite aqui"
      autocomplete="off"
    />
  </label>

  <div class="pad" aria-label="Controle remoto">
    <button class="up" onclick={() => press('up')}>▲</button>
    <button class="left" onclick={() => press('left')}>◀</button>
    <button class="ok" onclick={() => press('ok')}>OK</button>
    <button class="right" onclick={() => press('right')}>▶</button>
    <button class="down" onclick={() => press('down')}>▼</button>
  </div>

  <button class="back" onclick={() => press('back')}>Voltar</button>
</section>

<style>
  .remote {
    height: 100%;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: var(--space-16);
    padding: var(--space-16);
    overflow: hidden;
  }

  label {
    display: grid;
    gap: var(--space-8);
    color: var(--tx-3);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
  }

  input {
    min-height: 44px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--tx);
    font: inherit;
    font-size: var(--font-size-sm);
    text-transform: none;
    padding: 0 var(--space-12);
  }

  input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .pad {
    align-self: center;
    justify-self: center;
    width: min(76vw, 58vh, 340px);
    aspect-ratio: 1;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    grid-template-rows: 1fr 1fr 1fr;
    gap: var(--space-8);
  }

  button {
    min-height: 44px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--tx);
    font-family: var(--font-sans);
    font-size: var(--font-size-lg);
    font-weight: 500;
  }

  button:active {
    border-color: var(--accent);
    background: var(--bg-3);
  }

  .up { grid-column: 2; grid-row: 1; }
  .left { grid-column: 1; grid-row: 2; }
  .ok {
    grid-column: 2;
    grid-row: 2;
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
  }
  .right { grid-column: 3; grid-row: 2; }
  .down { grid-column: 2; grid-row: 3; }

  .back {
    justify-self: center;
    width: min(100%, 220px);
    font-size: var(--font-size-sm);
  }

  @media (max-height: 430px) {
    label {
      gap: 4px;
    }

    input {
      min-height: 40px;
    }

    .pad {
      width: min(54vw, 64vh, 260px);
    }

    button {
      min-height: 38px;
    }
  }
</style>
