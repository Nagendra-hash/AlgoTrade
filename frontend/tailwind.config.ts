import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border:     "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
      },
      animation: {
        "ticker":       "ticker 40s linear infinite",
        "fade-in":      "fadeIn 0.15s ease",
        "slide-up":     "slideUp 0.2s ease",
        "pulse-ring":   "pulseRing 1.5s ease-out infinite",
      },
      keyframes: {
        ticker:    { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        fadeIn:    { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp:   { from: { transform: "translateY(8px)", opacity: "0" }, to: { transform: "translateY(0)", opacity: "1" } },
        pulseRing: { "0%": { transform: "scale(0.8)", opacity: "1" }, "100%": { transform: "scale(2)", opacity: "0" } },
      },
    },
  },
  plugins: [],
};
export default config;
