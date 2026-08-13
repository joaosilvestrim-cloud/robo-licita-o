/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta Drive Data — azul-ciano principal (extraída do logo)
        proc: {
          50:  "#ecfbff",
          100: "#d6f4fd",
          200: "#ade9fa",
          300: "#6bd6f2",
          400: "#35bce6",
          500: "#16a0d4",
          600: "#1177b0",
          700: "#155d8a",
          800: "#123f5e",
          900: "#0b2d45",
        },
        // Acento verde Drive Data
        dgreen: {
          300: "#7be8a6",
          400: "#4cdd84",
          500: "#2fcb6c",
          600: "#22a95a",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.07), 0 1px 2px -1px rgb(0 0 0 / 0.07)",
        "card-hover": "0 4px 12px 0 rgb(0 0 0 / 0.10), 0 2px 4px -2px rgb(0 0 0 / 0.10)",
      },
    },
  },
  plugins: [],
};
