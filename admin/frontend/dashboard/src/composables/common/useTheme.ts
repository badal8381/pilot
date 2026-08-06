import { useTheme as useFrappeTheme } from 'frappe-ui'

type Theme = 'light' | 'dark' | 'system'

export const useTheme = () => {
  const { setTheme: setFrappeTheme, ...rest } = useFrappeTheme()

  const setTheme = (theme: Theme) => {
    document.documentElement.classList.add('no-transition')
    setFrappeTheme(theme)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.documentElement.classList.remove('no-transition')
      })
    })
  }

  return { ...rest, setTheme }
}
