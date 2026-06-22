/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      colors: {
        surface: {
          DEFAULT: "#ffffff",
          muted: "#fafafa",
          subtle: "#f5f5f5",
        },
        ink: {
          DEFAULT: "#171717",
          muted: "#737373",
          faint: "#a3a3a3",
        },
        line: "#e5e5e5",
      },
      boxShadow: {
        panel: "0 24px 80px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.04)",
        card: "0 1px 2px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04)",
      },
      borderRadius: {
        xl: "12px",
        "2xl": "16px",
      },
    },
  },
  plugins: [],
};
