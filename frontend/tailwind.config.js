/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#f8fafc',
        card: '#ffffff',
        border: 'rgba(226, 232, 240, 0.8)',
        centinela: {
          dark: '#0f172a',
          muted: '#64748b',
          light: '#f1f5f9',
          mint: {
            bg: '#f0fdf4',
            text: '#15803d',
            border: '#dcfce7'
          },
          amber: {
            bg: '#fffbeb',
            text: '#b45309',
            border: '#fef3c7'
          },
          rose: {
            bg: '#fff1f2',
            text: '#be123c',
            border: '#ffe4e6'
          },
          sky: {
            bg: '#f0f9ff',
            text: '#0369a1',
            border: '#e0f2fe'
          }
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace']
      },
      boxShadow: {
        'subtle': '0 1px 3px 0 rgba(0, 0, 0, 0.03), 0 1px 2px -1px rgba(0, 0, 0, 0.03)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02), 0 0 0 1px rgba(226, 232, 240, 0.6)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.04), 0 4px 6px -4px rgba(0, 0, 0, 0.02), 0 0 0 1px rgba(203, 213, 225, 0.8)',
        'modal': '0 25px 50px -12px rgba(15, 23, 42, 0.15)',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      }
    },
  },
  plugins: [],
}
