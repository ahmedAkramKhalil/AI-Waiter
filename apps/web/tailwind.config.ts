import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Tajawal"', '"Cairo"', "system-ui", "sans-serif"],
        display: ['"Tajawal"', '"Cairo"', "system-ui", "sans-serif"],
      },
      colors: {
        wine: {
          50:  "#fbf4f5",
          100: "#f3dfe2",
          200: "#e4b3bb",
          300: "#cc7d8a",
          400: "#a84c5d",
          500: "#8b2d40",
          600: "#6e1f30",
          700: "#561825",
          800: "#3c0f18",
          900: "#25080f",
        },
        gold: {
          100: "#fff6dc",
          200: "#fbe8a3",
          300: "#f2ce60",
          400: "#d9a83a",
          500: "#b7851a",
          600: "#8a6210",
        },
        cream: "#fdf6ec",
      },
      backgroundImage: {
        "restaurant": "radial-gradient(ellipse at top, #6e1f30 0%, #3c0f18 45%, #1a0308 100%)",
        "gold-glow": "radial-gradient(circle at 30% 20%, rgba(242,206,96,0.35), transparent 60%)",
        "glass": "linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.02) 60%)",
        "glass-gold": "linear-gradient(135deg, rgba(242,206,96,0.28) 0%, rgba(183,133,26,0.08) 70%)",
      },
      boxShadow: {
        "glossy": "0 20px 40px -20px rgba(0,0,0,0.6), inset 0 1px 0 0 rgba(255,255,255,0.18), inset 0 -1px 0 0 rgba(0,0,0,0.2)",
        "gold":   "0 10px 30px -10px rgba(217,168,58,0.6), inset 0 1px 0 0 rgba(255,255,255,0.4)",
        "bubble": "0 8px 24px -10px rgba(0,0,0,0.5), inset 0 1px 0 0 rgba(255,255,255,0.15)",
      },
      keyframes: {
        shimmer: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%":      { backgroundPosition: "100% 50%" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%":      { transform: "translateY(-8px)" },
        },
        pulseDot: {
          "0%, 80%, 100%": { opacity: "0.3", transform: "scale(0.8)" },
          "40%":           { opacity: "1",   transform: "scale(1.1)" },
        },
      },
      animation: {
        shimmer: "shimmer 6s ease-in-out infinite",
        float:   "float 4s ease-in-out infinite",
        dot:     "pulseDot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
