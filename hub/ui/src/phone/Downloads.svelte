<script>
  let { items = [] } = $props()
</script>

{#if !items.length}
  <p class="hint">Nada baixando.</p>
{:else}
  <div class="downloads">
    {#each items as item (`${item.kind}-${item.title}`)}
      <article>
        <div class="head">
          <span class="kind">{item.kind}</span>
          <span class="pct">{item.percent ?? 0}%</span>
        </div>
        <h2>{item.title}</h2>
        <div class="bar"><i style:width="{Math.max(0, Math.min(100, item.percent ?? 0))}%"></i></div>
      </article>
    {/each}
  </div>
{/if}

<style>
  .hint {
    color: var(--tx-3);
    font-size: var(--font-size-sm);
    padding: var(--space-16) var(--space-4);
  }

  .downloads {
    display: grid;
    gap: var(--space-12);
  }

  article {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-12);
    overflow: hidden;
  }

  .head {
    display: flex;
    justify-content: space-between;
    gap: var(--space-12);
    color: var(--tx-4);
    font-family: var(--font-mono);
    font-size: var(--font-size-2xs);
    text-transform: uppercase;
  }

  h2 {
    margin: var(--space-8) 0 var(--space-12);
    font-family: var(--font-sans);
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--tx);
    line-height: var(--leading-ui);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .bar {
    height: 3px;
    background: var(--border);
    overflow: hidden;
  }

  .bar i {
    display: block;
    height: 100%;
    background: var(--accent);
  }
</style>
