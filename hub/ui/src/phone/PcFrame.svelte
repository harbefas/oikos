<script>
  let { url = '' } = $props()

  const frameUrl = $derived(
    url.replace(/^http:\/\/localhost(?=[:/]|$)/, `http://${location.hostname}`)
  )
</script>

{#if frameUrl}
  <iframe title="hyprpad" src={frameUrl}></iframe>
{:else}
  <p class="hint">Hyprpad indisponivel.</p>
{/if}

<style>
  iframe {
    width: 100%;
    height: 100%;
    border: 0;
    display: block;
    background: var(--bg);
  }

  .hint {
    color: var(--tx-3);
    font-size: var(--font-size-sm);
    padding: var(--space-16) var(--space-4);
  }
</style>
