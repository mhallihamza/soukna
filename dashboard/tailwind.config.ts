import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0f1e2e",
        paper: "#f5f0e6",
        white: "#fffdf9",
        greenbrand: "#1f6b52",
        greenbg: "#e4efe8",
        amberbrand: "#9a6414",
        amberbg: "#f8eed8",
        redbrand: "#a9362d",
        redbg: "#f7e7e4",
        terra: "#c2603a",
        muted: "#66717b",
        line: "#dcd6cb",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        body: ["Inter", "Arial", "sans-serif"],
        arabic: ["IBM Plex Sans Arabic", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
