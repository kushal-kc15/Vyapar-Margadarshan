/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      // ---- Fonts ----
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        display: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'monospace'],
      },

      // ---- Typography ----
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.02em' }],
        micro: ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.14em' }],
        xs: ['0.75rem', { lineHeight: '1.125rem' }],
        sm: ['0.8125rem', { lineHeight: '1.25rem' }],
        base: ['0.875rem', { lineHeight: '1.375rem' }],
        lg: ['1rem', { lineHeight: '1.5rem' }],
        xl: ['1.125rem', { lineHeight: '1.625rem', letterSpacing: '-0.01em' }],
        '2xl': ['1.375rem', { lineHeight: '1.75rem', letterSpacing: '-0.015em' }],
        '3xl': ['1.75rem', { lineHeight: '2.125rem', letterSpacing: '-0.02em' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.025em' }],
        '5xl': ['3rem', { lineHeight: '1.02', letterSpacing: '-0.03em' }],
        '6xl': ['3.75rem', { lineHeight: '1', letterSpacing: '-0.035em' }],
        '7xl': ['4.75rem', { lineHeight: '0.98', letterSpacing: '-0.04em' }],
        '8xl': ['6rem', { lineHeight: '0.95', letterSpacing: '-0.04em' }],
      },

      letterSpacing: {
        eyebrow: '0.14em',
      },

      // ---- Colors ----
      colors: {
        // Paper – the body background. Warm off-white.
        paper: {
          DEFAULT: 'rgb(var(--color-paper) / <alpha-value>)',
          deep: 'rgb(var(--color-paper-deep) / <alpha-value>)',
          edge: 'rgb(var(--color-paper-edge) / <alpha-value>)',
        },

        // Ink – typographic scale.
        ink: {
          DEFAULT: 'rgb(var(--color-ink) / <alpha-value>)',
          soft: 'rgb(var(--color-ink-soft) / <alpha-value>)',
          muted: 'rgb(var(--color-ink-muted) / <alpha-value>)',
          faint: 'rgb(var(--color-ink-faint) / <alpha-value>)',
        },

        // Rules – borders / hairlines.
        rule: {
          DEFAULT: 'rgb(var(--color-rule) / <alpha-value>)',
          strong: 'rgb(var(--color-rule-strong) / <alpha-value>)',
        },

        // Cinnabar – primary accent (red ink).
        cinnabar: {
          50: 'rgb(var(--color-cinnabar-50) / <alpha-value>)',
          200: 'rgb(var(--color-cinnabar-200) / <alpha-value>)',
          300: 'rgb(var(--color-cinnabar-300) / <alpha-value>)',
          500: 'rgb(var(--color-cinnabar-500) / <alpha-value>)',
          600: 'rgb(var(--color-cinnabar-600) / <alpha-value>)',
          700: 'rgb(var(--color-cinnabar-700) / <alpha-value>)',
        },

        // Moss – positive / "in balance" tone.
        moss: {
          50: 'rgb(var(--color-moss-50) / <alpha-value>)',
          200: 'rgb(var(--color-moss-200) / <alpha-value>)',
          500: 'rgb(var(--color-moss-500) / <alpha-value>)',
          600: 'rgb(var(--color-moss-600) / <alpha-value>)',
          700: 'rgb(var(--color-moss-700) / <alpha-value>)',
        },

        // Saffron – caution / "watch" tone.
        saffron: {
          50: 'rgb(var(--color-saffron-50) / <alpha-value>)',
          200: 'rgb(var(--color-saffron-200) / <alpha-value>)',
          500: 'rgb(var(--color-saffron-500) / <alpha-value>)',
          600: 'rgb(var(--color-saffron-600) / <alpha-value>)',
          700: 'rgb(var(--color-saffron-700) / <alpha-value>)',
        },

        // Inkwell – neutral ledger text.
        inkwell: {
          50: '#f0eee9',
          500: '#7a7468',
          700: '#3d3a35',
        },

        // Legacy surface system (kept for compatibility).
        surface: {
          DEFAULT: '#ffffff',
          muted: '#faf8f3',
          sunken: '#f3f1ea',
        },
        line: {
          DEFAULT: '#e3ddd0',
          strong: '#cbc3b1',
        },
        canvas: '#fbfaf7',

        // Landing page palette (additive).
        ivory: {
          DEFAULT: '#F7F1E1',
          soft: '#F2EAD3',
          deep: '#EADFC2',
        },
        charcoal: {
          DEFAULT: '#2A241D',
          soft: '#4A4239',
          muted: '#7C7060',
          faint: '#A89D8B',
        },
        coral: {
          50: '#FCEBE7',
          100: '#F8D2C8',
          200: '#F0AE9C',
          500: '#E26B4D',
          600: '#C95940',
          700: '#A8472F',
        },
        forest: {
          50: 'rgb(var(--color-forest-50) / <alpha-value>)',
          100: 'rgb(var(--color-forest-100) / <alpha-value>)',
          200: 'rgb(var(--color-forest-200) / <alpha-value>)',
          500: 'rgb(var(--color-forest-500) / <alpha-value>)',
          600: 'rgb(var(--color-forest-600) / <alpha-value>)',
          700: 'rgb(var(--color-forest-700) / <alpha-value>)',
        },
        teal: {
          50: '#DBEEEC',
          100: '#B6DAD6',
          200: '#84C2BC',
          500: '#2E8078',
          600: '#266963',
          700: '#1D524D',
        },
        amber: {
          50: '#FAEBD2',
          100: '#F2D3A4',
          200: '#E5B470',
          500: '#D88A41',
          600: '#BA6F2D',
          700: '#8E5520',
        },
        sage: {
          50: '#EBF1E7',
          100: '#D6E2CC',
          200: '#B8CFA9',
        },
        mint: {
          50: '#E2EFE9',
          100: '#C5DDD5',
          200: '#9BC8BB',
        },
        peach: {
          50: '#FAE6D5',
          100: '#F2CFAE',
          200: '#E8B081',
        },
        warmborder: {
          DEFAULT: '#EBE0C5',
          strong: '#D8C9A2',
        },
      },

      // ---- Borders ----
      borderRadius: {
        sm: '0.375rem',
        DEFAULT: '0.5rem',
        md: '0.625rem',
        lg: '0.75rem',
        xl: '1rem',
        pill: '9999px',
      },

      // ---- Shadows ----
      boxShadow: {
        xs: '0 1px 2px 0 rgba(28, 26, 23, 0.05)',
        sm: '0 1px 3px 0 rgba(28, 26, 23, 0.07), 0 1px 2px -1px rgba(28, 26, 23, 0.04)',
        md: '0 4px 12px -2px rgba(28, 26, 23, 0.08)',
        pop: '0 18px 40px -16px rgba(28, 26, 23, 0.18), 0 2px 6px -2px rgba(28, 26, 23, 0.06)',
        page: '0 1px 0 0 rgba(28, 26, 23, 0.04), 0 12px 32px -10px rgba(28, 26, 23, 0.10)',
      },

      // ---- Animations ----
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'fade-in-up': 'fadeInUp 0.28s ease-out forwards',
        'draw': 'draw 1.4s ease-out forwards',
        'shimmer': 'shimmer 1.6s linear infinite',
        'drawer': 'drawer 0.2s ease-out',
      },

      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        draw: {
          '0%': { strokeDashoffset: '200' },
          '100%': { strokeDashoffset: '0' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        drawer: {
          '0%': { opacity: '0', transform: 'scale(0.96) translateY(-4px)' },
          '100%': { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
