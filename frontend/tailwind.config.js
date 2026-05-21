/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        rx: {
          blue: "#1d4ed8",
          cyan: "#0891b2",
          green: "#059669",
          ink: "#0f172a",
          muted: "#64748b",
          line: "#e2e8f0",
          soft: "#f8fafc"
        }
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15, 23, 42, 0.05), 0 16px 40px rgba(15, 23, 42, 0.06)"
      }
    }
  },
  plugins: []
};
