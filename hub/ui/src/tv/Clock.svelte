<script>
  import { onMount, onDestroy } from 'svelte'

  // Same reason as the theme: the box's own clock has drifted before, and a
  // wrong time on a wall-mounted TV is the one bug everyone notices.
  const FMT = new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'America/Sao_Paulo',
    hour: '2-digit',
    minute: '2-digit',
  })

  let now = $state(FMT.format(new Date()))
  let timer = 0

  onMount(() => {
    timer = setInterval(() => (now = FMT.format(new Date())), 10_000)
  })
  onDestroy(() => clearInterval(timer))
</script>

<time>{now}</time>

<style>
  /* Reading face at headline size. Weight 500 — §3 forbids 700 on Garamond,
     it muddies the face. */
  time {
    font-family: var(--font-serif);
    font-size: var(--font-size-3xl);
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    letter-spacing: var(--tracking-headline);
    line-height: var(--leading-tight);
    color: var(--tx-2);
  }
</style>
