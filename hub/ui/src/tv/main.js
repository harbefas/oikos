import '../lib/tokens.css'
import { mount } from 'svelte'
import { startTheme } from '../lib/theme.js'
import App from './App.svelte'

startTheme()

export default mount(App, { target: document.getElementById('app') })
