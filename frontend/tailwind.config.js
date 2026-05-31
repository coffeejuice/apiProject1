import defaultTheme from 'tailwindcss/defaultTheme'
import typography from '@tailwindcss/typography'

const neutralGray = {
  50: '#fafafa',
  100: '#f2f2f2',
  200: '#e3e3e3',
  300: '#d6d6d6',
  400: '#bfbfbf',
  500: '#8c8c8c',
  600: '#666666',
  700: '#4a4a4a',
  800: '#303030',
  900: '#1f1f1f',
}

const compactFontScale = {
  xs: ['0.6875rem', { lineHeight: '0.9375rem' }], // 11/15
  sm: ['0.75rem', { lineHeight: '1rem' }], // 12/16
  base: ['0.8125rem', { lineHeight: '1.125rem' }], // 13/18
  lg: ['0.9375rem', { lineHeight: '1.25rem' }], // 15/20
}

const flatterShadows = {
  sm: '0 1px 2px rgba(0, 0, 0, 0.06)',
  DEFAULT: '0 1px 3px rgba(0, 0, 0, 0.08)',
  md: '0 2px 4px rgba(0, 0, 0, 0.08)',
  lg: '0 4px 10px rgba(0, 0, 0, 0.10)',
  xl: '0 6px 14px rgba(0, 0, 0, 0.12)',
  '2xl': '0 8px 20px rgba(0, 0, 0, 0.14)',
  none: 'none',
}

const multilingualSans = [
  'Noto Sans',
  'Noto Sans CJK SC',
  'Noto Sans SC',
  'Noto Sans CJK TC',
  'Noto Sans TC',
  'Noto Sans CJK JP',
  'Noto Sans JP',
  'Noto Sans CJK KR',
  'Noto Sans KR',
  'Noto Sans Arabic',
  'Noto Naskh Arabic',
  'Noto Sans Hebrew',
  'Noto Sans Devanagari',
  'Noto Sans Thai',
  'Noto Sans Armenian',
  'Noto Sans Georgian',
  'Noto Color Emoji',
  'Segoe UI',
  'Microsoft YaHei',
  'PingFang SC',
  'Hiragino Sans',
  'Meiryo',
  'Yu Gothic',
  'Malgun Gothic',
  'Apple SD Gothic Neo',
  'Arial Unicode MS',
  'Arial',
  'sans-serif',
]

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    fontFamily: {
      ...defaultTheme.fontFamily,
      sans: multilingualSans,
    },
    fontSize: compactFontScale,
    fontWeight: {
      ...defaultTheme.fontWeight,
      medium: '400',
      semibold: '600',
    },
    boxShadow: flatterShadows,
    extend: {
      colors: {
        gray: neutralGray,
      },
    },
  },
  plugins: [typography],
}
