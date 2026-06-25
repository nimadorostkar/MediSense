/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#2563EB",
          soft: "rgba(37,99,235,0.10)",
        },
        ink: {
          900: "#1C2128",
          800: "#2B313B",
          700: "#3A4049",
          600: "#565E6B",
          500: "#64748B",
          400: "#7B828C",
          300: "#9AA1AB",
          200: "#A2A8B0",
        },
        line: {
          DEFAULT: "#E8E9EC",
          soft: "#ECECEE",
          input: "#E1E4E8",
        },
        canvas: "#E8E9EB",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "22px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(15,23,42,0.03)",
        input: "0 6px 22px rgba(15,23,42,0.05)",
        focus: "0 8px 26px rgba(37,99,235,0.12)",
        chip: "0 10px 22px rgba(37,99,235,0.12)",
        modal: "0 24px 60px rgba(15,23,42,0.28)",
        iconbtn: "0 2px 8px rgba(15,23,42,0.06)",
      },
      keyframes: {
        "ring-hero": {
          from: { backgroundPositionX: "0" },
          to: { backgroundPositionX: "-7820px" },
        },
        "ring-hdr": {
          from: { backgroundPositionX: "0" },
          to: { backgroundPositionX: "-2024px" },
        },
        blink: {
          "0%, 60%, 100%": { opacity: "0.25" },
          "30%": { opacity: "1" },
        },
        rise: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "none" },
        },
        fade: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
      animation: {
        "ring-hero": "ring-hero 2.3s steps(46) infinite",
        "ring-hdr": "ring-hdr 2.3s steps(46) infinite",
        blink: "blink 1s infinite",
        rise: "rise 0.28s ease both",
        fade: "fade 0.18s ease",
      },
    },
  },
  plugins: [],
};
