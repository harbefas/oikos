<script>
  import Grid from './Grid.svelte'

  let { items = [], ratio = '2 / 3', onselect = () => {}, groupBy = 'genre' } = $props()

  // Agrupa pelo genero unico que o backend manda (1o genero do Jellyfin/TMDB
  // -- sem duplicar item em varias secoes). Jogos nao tem genero, so sistema
  // (`label`, ex. "PC"/"SNES") -- por isso o groupBy e configuravel.
  const groups = $derived.by(() => {
    const by = new Map()
    for (const item of items) {
      const g = item[groupBy] || 'Outros'
      if (!by.has(g)) by.set(g, [])
      by.get(g).push(item)
    }
    return [...by.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0], 'pt-BR'))
  })
</script>

<div class="groups">
  {#each groups as [genre, group] (genre)}
    <section>
      <h2>{genre}</h2>
      <Grid items={group} {ratio} {onselect} />
    </section>
  {/each}
</div>

<style>
  .groups {
    display: grid;
    gap: var(--space-24);
  }

  h2 {
    font-family: var(--font-serif);
    font-size: var(--font-size-lg);
    font-weight: 500;
    color: var(--tx);
    margin: 0 0 var(--space-12);
  }
</style>
