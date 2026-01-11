/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        archon: {
          bg: '#0a0b0d',
          card: '#111215',
          border: '#1e2025',
          accent: '#153e75',
          accentLight: '#1e4a8a',
          accentAlt: '#00d4aa',
          text: '#e0e0e0',
          textMuted: '#888888',
          success: '#22c55e',
          danger: '#ef4444',
          warning: '#f59e0b',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      }
    },
  },
  plugins: [],
}
