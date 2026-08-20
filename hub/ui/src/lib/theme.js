export function currentTheme() {
  return 'dark'
}

export function startTheme() {
  document.documentElement.dataset.theme = currentTheme()
}
