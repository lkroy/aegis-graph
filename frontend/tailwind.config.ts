import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: "#020617",
          panel: "#0b1220",
          border: "#1e293b",
          cyan: "#22d3ee",
          gold: "#fbbf24",
        },
      },
    },
  },
  plugins: [],
};
export default config;
