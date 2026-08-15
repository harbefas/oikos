// Terere (06h-18h) / Cimarrao (18h-06h). Shared by TV and phone so the two
// never disagree. Hour comes from Intl in America/Sao_Paulo rather than the
// local clock: the kiosk box has drifted to UTC before and the theme flipped
// mid-evening.
const HOUR = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Sao_Paulo',
  hour: 'numeric',
  hour12: false,
})

export function currentTheme() {
  const h = parseInt(HOUR.format(new Date()), 10)
  return h >= 6 && h < 18 ? 'light' : 'dark'
}

export function startTheme() {
  const apply = () => {
    document.documentElement.dataset.theme = currentTheme()
  }
  apply()
  setInterval(apply, 600_000)
}
