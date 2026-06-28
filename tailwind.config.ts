import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    "./libs/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  // The verdict semafor colour classes are declared as string literals in
  // lib/compliance/colors.ts; with `lib` now in `content` they are detected,
  // but we keep an explicit safelist so they can never be purged regardless of
  // where the source of truth moves (the legend promises a traffic light).
  safelist: [
    "bg-green-100", "text-green-800", "border-green-300",
    "bg-orange-100", "text-orange-800", "border-orange-300",
    "bg-red-100", "text-red-800", "border-red-300",
    "bg-gray-100", "text-gray-600", "border-gray-300",
    // gov semafor row tinting (lib/compliance/colors.ts string literals)
    "bg-success-tint", "border-l-success", "text-success",
    "bg-warning-tint", "border-l-warning", "text-warning",
    "bg-danger-tint", "border-l-danger", "text-danger",
    "bg-gray-50", "border-l-gray-300",
  ],
  theme: {
    extend: {
      colors: {
        // --- minedu.sk gov-style palette (see docs/design/minedu-design-manual.md) ---
        gov: {
          blue: "#0055A0",
          blue50: "rgba(0,85,160,0.10)",
          ink: "#212529",
          muted: "#495057",
          canvas: "#F9F9F9",
          surface: "#E9ECEF",
          border: "#DEE2E6",
          red: "#AF0D15", // nav accent + danger
        },
        // semafor (strong = text/icon; tint = row bg; bar = left edge)
        success: { DEFAULT: "#0F663E", tint: "#E7F2EC", bar: "#0F663E" },
        warning: { DEFAULT: "#8A5300", tint: "#FBF1DD", bar: "#C77700" },
        danger: { DEFAULT: "#AF0D15", tint: "#FBE7E8", bar: "#AF0D15" },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        sans: [
          "var(--font-rubik)",
          "Rubik",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Arial",
          "sans-serif",
        ],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        // minedu "soft elevation": big blur, low opacity, 1px border ring.
        gov: "0 2px 8px rgba(33,37,41,0.08), 0 0 0 1px #DEE2E6",
        "gov-md": "0 8px 24px rgba(0,0,0,0.10)",
        "gov-lg": "0 16px 48px rgba(0,0,0,0.176)",
      },
    },
  },
  plugins: [],
};

export default config;
