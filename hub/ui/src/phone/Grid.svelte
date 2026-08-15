<script>
  let { items = [], ratio = '2 / 3', onselect = () => {} } = $props()
</script>

<div class="grid">
  {#each items as item (item.id ?? item.path ?? item.name)}
    <button class="tile" style:aspect-ratio={ratio} onclick={() => onselect(item)}>
      {#if item.cover}
        <img src={item.cover} alt="" loading="lazy" decoding="async" />
      {:else}
        <span class="blank"></span>
      {/if}
      <span class="name">{item.name ?? item.label}</span>
    </button>
  {/each}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));
    gap: var(--space-12);
  }

  /* Touch surface, so chrome rules: nothing scales, nothing lifts. Pressed
     state is a border change (§4). */
  .tile {
    position: relative;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-art);
    overflow: hidden;
    background: var(--surface);
    display: grid;
    place-items: center;
    transition: border-color var(--duration-base) var(--ease-standard);
  }

  .tile:active {
    border-color: var(--accent);
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
  }

  /* Scrim over artwork — permitted under §6a, and required: a title over a
     bright poster is otherwise unreadable. */
  .name {
    position: absolute;
    inset: auto 0 0 0;
    padding: var(--space-24) var(--space-8) var(--space-8);
    font-family: var(--font-sans);
    font-size: var(--font-size-2xs);
    font-weight: 500;
    line-height: var(--leading-ui);
    color: var(--tx);
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: linear-gradient(transparent, var(--nm-grad) 60%);
  }
</style>
