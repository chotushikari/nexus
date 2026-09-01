/** @type {import('tailwindcss').Config} */
// Tailwind mirrors the CSS custom properties in src/app/globals.css.
// Single source of truth is globals.css; this exposes the same tokens as
// utility classes. No dark mode: NEXUS is a light-only product surface.
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SF Mono", "monospace"],
      },
      colors: {
        // UI chrome
        paper: {
          0: "#fbf8f1",
          1: "#f5f0e4",
          2: "#ebe4d4",
          3: "#ded5c0",
          4: "#c4b89e",
        },
        ink: {
          0: "#2b2620",
          1: "#4a4238",
          2: "#6e6355",
          3: "#928676",
        },
        // Office materials — shared with the canvas tileset palette
        sage: {
          0: "#a8bca5",
          1: "#8fa68e",
          2: "#758c74",
          3: "#5c7159",
        },
        oak: {
          0: "#c69a6d",
          1: "#a97c50",
          2: "#86603c",
          3: "#634528",
        },
        // Runtime state — maps 1:1 to the backend RuntimeStatus enum
        state: {
          neutral: "#6e6355",
          active: "#3f6e63",
          comm: "#4a6f8a",
          success: "#4a7c4e",
          warning: "#b07d2b",
          approval: "#c8860d",
          danger: "#a63d2f",
        },
      },
      boxShadow: {
        1: "0 1px 2px rgba(43,38,32,0.06)",
        2: "0 2px 8px rgba(43,38,32,0.08)",
        3: "0 8px 24px rgba(43,38,32,0.10)",
      },
      borderRadius: {
        DEFAULT: "6px",
        lg: "10px",
      },
      letterSpacing: {
        label: "0.11em",
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-in",
        "slide-up": "slideUp 0.26s ease-out",
      },
      keyframes: {
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
