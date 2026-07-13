import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: 'var(--surface-bg)',
          50: 'var(--surface-50)',
          100: 'var(--surface-100)',
          200: 'var(--surface-200)',
          300: 'var(--surface-300)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        border: {
          light: 'var(--border-light)',
          medium: 'var(--border-medium)',
        },
        // Acento da marca — terracota. `lime` mantido como ALIAS p/ não quebrar classes
        // existentes (text-lime, bg-lime/20 etc.); o valor agora é o terracota.
        brand: { DEFAULT: '#BA5653', hover: '#A84744', ink: '#FFFFFF' },
        lime: { DEFAULT: '#BA5653', hover: '#A84744', 50: '#FFFFFF', 100: '#F3DEDD', 200: '#BA5653' },
        // Cores semânticas (zonas de FC, ACWR, gráficos) — espectro refinado
        accent: {
          green: '#34D399',
          yellow: '#F5B14C',
          red: '#FB5E7E',
          orange: '#FF8A4C',
          blue: '#38BDF8',
          violet: '#A78BFA',
          cyan: '#22D3EE',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Oswald', 'Inter', 'sans-serif'],   // condensada esportiva (títulos de impacto)
      },
      animation: {
        'slide-in': 'slideIn 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
        'slide-up': 'slideUp 0.32s cubic-bezier(0.22, 1, 0.36, 1)',
        'fade-in': 'fadeIn 0.2s ease-out',
        'pop': 'pop 0.28s cubic-bezier(0.34, 1.56, 0.64, 1)',
        'float': 'float 3.5s ease-in-out infinite',
        'shimmer': 'shimmer 1.4s linear infinite',
        'pulse-ring': 'pulseRing 1.8s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        slideIn: { '0%': { transform: 'translateX(16px)', opacity: '0' }, '100%': { transform: 'translateX(0)', opacity: '1' } },
        slideUp: { '0%': { transform: 'translateY(14px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        pop: { '0%': { transform: 'scale(0.9)', opacity: '0' }, '55%': { transform: 'scale(1.04)' }, '100%': { transform: 'scale(1)', opacity: '1' } },
        float: { '0%, 100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
        shimmer: { '0%': { backgroundPosition: '-400px 0' }, '100%': { backgroundPosition: '400px 0' } },
        pulseRing: { '0%': { transform: 'scale(0.7)', opacity: '0.6' }, '100%': { transform: 'scale(2.2)', opacity: '0' } },
      },
    },
  },
  plugins: [],
} satisfies Config
