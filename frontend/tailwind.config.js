/** @type {import('tailwindcss').Config} */
// Sistema de diseño "Centinela Glass": fondo menta/cielo suave, paneles de vidrio,
// tinta verde-negra y acentos pastel (lima, aqua, rosa) tomados de la referencia.
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Neutros con matiz verde-azulado (reemplazan el slate frío por defecto)
        slate: {
          50: '#f5f9f8',
          100: '#eaf1f0',
          200: '#d9e4e2',
          300: '#bccac8',
          400: '#8ea09d',
          500: '#667875',
          600: '#4c5e5b',
          700: '#374845',
          800: '#1f302d',
          900: '#10211f',
          950: '#091514',
        },
        // Emerald → verde azulado más sereno
        emerald: {
          50: '#ecf8f4',
          100: '#d4f0e7',
          200: '#aee3d2',
          300: '#7fd0b8',
          400: '#4fb99b',
          500: '#2fa081',
          600: '#228168',
          700: '#1d6755',
          800: '#1a5345',
          900: '#17443a',
          950: '#0a2823',
        },
        // Acentos pastel de la referencia
        lime: { DEFAULT: '#dcf3a0', soft: '#eef9cd', ink: '#506a10' },
        aqua: { DEFAULT: '#9fd8d0', soft: '#d3eeea', ink: '#1d6b62' },
        blush: { DEFAULT: '#f4a9a8', soft: '#fad9d8', ink: '#9a3a3a' },
        ink: '#10211f',
        background: '#eef5f4',
        card: '#ffffff',
        border: 'rgba(217, 228, 226, 0.8)',
        centinela: {
          dark: '#10211f',
          muted: '#667875',
          light: '#eaf1f0',
          mint: { bg: '#ecf8f4', text: '#1d6755', border: '#d4f0e7' },
          amber: { bg: '#fffbeb', text: '#b45309', border: '#fef3c7' },
          rose: { bg: '#fff1f2', text: '#be123c', border: '#ffe4e6' },
          sky: { bg: '#f0f9ff', text: '#0369a1', border: '#e0f2fe' },
        },
      },
      fontFamily: {
        sans: ['Outfit', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        subtle: '0 1px 2px 0 rgba(16, 33, 31, 0.04)',
        xs: '0 1px 2px 0 rgba(16, 33, 31, 0.05)',
        card: '0 8px 24px -8px rgba(16, 33, 31, 0.08), inset 0 0 0 1px rgba(255, 255, 255, 0.7)',
        'card-hover':
          '0 16px 36px -10px rgba(16, 33, 31, 0.14), inset 0 0 0 1px rgba(255, 255, 255, 0.9)',
        float: '0 18px 40px -12px rgba(16, 33, 31, 0.22)',
        modal: '0 30px 70px -16px rgba(16, 33, 31, 0.28)',
      },
      borderRadius: {
        '2xl': '1.125rem',
        '3xl': '1.75rem',
        '4xl': '2.25rem',
      },
      spacing: { 18: '4.5rem', 68: '17rem' },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateX(-16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.35s ease-out both',
        'slide-in': 'slide-in 0.25s ease-out both',
      },
    },
  },
  plugins: [],
};
