import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeName = 'tech' | 'minimal'

export const useThemeStore = defineStore('theme', () => {
  const STORAGE_KEY = 'app_theme'

  const theme = ref<ThemeName>(
    (localStorage.getItem(STORAGE_KEY) as ThemeName) ?? 'minimal',
  )

  function applyTheme(t: ThemeName) {
    document.documentElement.classList.remove('theme-tech', 'theme-minimal')
    document.documentElement.classList.add(`theme-${t}`)
  }

  function setTheme(t: ThemeName) {
    theme.value = t
    localStorage.setItem(STORAGE_KEY, t)
    applyTheme(t)
  }

  function toggle() {
    setTheme(theme.value === 'tech' ? 'minimal' : 'tech')
  }

  /** 应用入口调用一次，确保主题类挂载到 <html> */
  function init() {
    applyTheme(theme.value)
  }

  return { theme, setTheme, toggle, init }
})
