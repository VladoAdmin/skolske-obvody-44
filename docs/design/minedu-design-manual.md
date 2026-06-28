# MŠVVaM (minedu.sk) — Gov-Style Design Manual

Extracted from the live Slovak Ministry of Education portal **https://www.minedu.sk/**
(inspected 2026-06-28, computed styles + screenshots, Chrome/Playwright @ 1440px).

Reference screenshots: `./minedu-ref/01-hero-top.png`, `02-fullpage.png`, `03-footer.png`, `04-clean-top.png`.

This manual is a **visual-language extraction** for our own gov-style portal. It captures
colors, type, spacing and component patterns only — no proprietary logos/assets are copied.

---

## 1. Design language summary

minedu.sk is a clean, high-trust Bootstrap-based government portal. The recipe is:

- **One signature blue** (`#0055A0`) used everywhere structural: nav bar, all headings, links, icons.
- **A thin dark-red accent line** (`#AF0D15`) under the primary nav — the only "state red" on the page, giving a subtle Slovak-flag (blue + red + white) feel.
- **White content on a faint grey canvas** (`#F9F9F9`), separated by hairline borders (`#DEE2E6`).
- **Cards = white box + 1px grey border + a soft, large-radius shadow** for gentle elevation. Corners are nearly square (**2px radius**) — sober, institutional, not playful.
- **UPPERCASE blue section titles** (22px / 600) act as the main structural rhythm.
- **List rows** with blue link text + a `›` chevron + hairline separators — the dominant content pattern (used for our obvody result list).

---

## 2. Color tokens

All values are the real computed colors from the live site (RGB → HEX).

### 2.1 Brand & neutrals

| Token | HEX | Source / usage on minedu.sk |
|---|---|---|
| `--blue-700` (primary, signature) | `#0055A0` | Nav bar bg, every heading, links, icons (rgb 0,85,160 — 292 uses) |
| `--blue-700-90` | `rgba(0,85,160,0.9)` | Hover/overlay states on blue |
| `--blue-50` (tint) | `rgba(0,85,160,0.1)` | Faint blue wash (active row / selected) |
| `--ink` (body text) | `#212529` | Body copy, dark UI text (rgb 33,37,41 — most common) |
| `--ink-muted` | `#495057` | Secondary text |
| `--white` | `#FFFFFF` | Cards, header, nav text |
| `--canvas` | `#F9F9F9` | Page background behind cards |
| `--surface-2` | `#E9ECEF` | Footer background, subtle fills |
| `--border` | `#DEE2E6` | Card borders, row dividers, inputs |
| `--border-soft` | `rgba(222,226,230,0.3)` | Very light internal dividers |

### 2.2 Status / semafor colors (traffic-light)

minedu uses a dark institutional green and a dark flag-red. We keep those as the base and
add an accessible amber for the middle state. All chosen to pass **WCAG AA (≥4.5:1)** as
text on white, and to read clearly as row tints.

| State | Text/strong HEX | Contrast on white | Row tint (bg) HEX | Left bar HEX | Meaning in app |
|---|---|---|---|---|---|
| **Success / V súlade** | `#0F663E` | 6.6:1 ✓ | `#E7F2EC` | `#0F663E` | green (z minedu tlačidla) |
| **Warning / Čiastočný** | `#8A5300` | 5.3:1 ✓ | `#FBF1DD` | `#C77700` | amber (added, AA-safe) |
| **Danger / Nesúlad** | `#AF0D15` | 6.9:1 ✓ | `#FBE7E8` | `#AF0D15` | red (z minedu nav-underline / linkov) |

Notes:
- The **strong** hex is for text, icons, and the verdict label so the textual verdict stays
  fully legible — never rely on tint alone (accessibility + colour-blind safety).
- The **row tint** is a ~8% wash of the strong colour over white; safe under `#212529` body text.
- A **3px left bar** in the strong colour gives the row an unmistakable status edge.

---

## 3. Typography

minedu.sk uses **Rubik** (Google Font) with a Bootstrap-style system stack fallback.

```
font-family: Rubik, system-ui, -apple-system, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, "Noto Sans", sans-serif;
```

Load Rubik (weights 400/500/600/700). In Next.js prefer `next/font/google`:

```ts
import { Rubik } from "next/font/google";
export const rubik = Rubik({ subsets: ["latin","latin-ext"], weight: ["400","500","600","700"], display: "swap", variable: "--font-rubik" });
```
(`latin-ext` is required for Slovak diacritics: š, č, ž, ô, ľ …)

### Type scale (measured)

| Role | Size | Weight | Line-height | Color | Extra |
|---|---|---|---|---|---|
| Page title `h1` | 28–32px | 700 | 1.15 | `#0055A0` | (site uses small h1; scale up for our app) |
| Section title `h2` | **22px** | **600** | 1.2 (26.4px) | `#0055A0` | **UPPERCASE** |
| Card title `h3` | 20px | 600 | 1.2 (24px) | `#0055A0` or `#FFF` on blue |
| Sub-heading / list head | 18px | 600 | 1.4 | `#212529` | |
| Body | **16px** | 400 | **24px (1.5)** | `#212529` | |
| Small / meta | 14px | 400 | 1.45 | `#495057` | |
| Link | 16px | 400 | 1.5 | `#0055A0` | underline in prose; no underline in nav/lists |

Letter-spacing: `normal` everywhere (no tracking). Section titles get visual weight from
**uppercase + blue + 600**, not from spacing.

---

## 4. Spacing, radius, elevation

### Spacing scale (Bootstrap-derived, observed paddings 4/6/9/12/16/24/40px)
Use a 4px base: `4, 8, 12, 16, 24, 32, 40, 48, 64`.
- Card inner padding: **24px** (`p-6`).
- List row padding: **12px 16px** (`py-3 px-4`); chevron rows up to `9px 40px` indented.
- Nav item padding: **~16px 24px**.
- Section vertical rhythm: **40–48px** between blocks.

### Border radius
- **`2px`** is the *only* radius on minedu (buttons, cards, inputs). Institutional, near-square.
- Our tokens: `--radius-sm: 2px` (chips/inputs/buttons), `--radius: 4px` (cards — a hair softer is fine), `--radius-lg: 6px` (modals/side panel). Stay small; avoid rounded "app" look.

### Elevation (the subtle 3D depth)
Three real shadows were found; generalize into a 3-step scale:

| Token | Value | Use |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(33,37,41,0.06)` | hairline lift (inputs, hover) |
| `--shadow` (card) | `0 2px 8px rgba(33,37,41,0.08), 0 0 0 1px #DEE2E6` | **default card** — soft large-radius glow + 1px ring (matches the tile look) |
| `--shadow-md` | `0 8px 24px rgba(0,0,0,0.10)` | raised tiles / hover |
| `--shadow-lg` | `0 16px 48px rgba(0,0,0,0.176)` | dropdowns / modals (verbatim from site) |

The signature feel = **big blur radius + low opacity + a 1px border ring**, not a hard drop shadow.

---

## 5. Component patterns (observed)

**App header (topbar):** white bg, full-bleed, generous height (~140px on desktop with
crest + wordmark left, social/lang/search right). No shadow on the header itself.

**Primary nav strip:** solid `#0055A0` bar directly under the header, white 700-ish uppercase
items with `▾` carets, and a **thin `#AF0D15` red line along its bottom edge** (~2–3px). This
red underline is the single most identifiable gov cue — replicate it.

**Section title:** `UPPERCASE`, `#0055A0`, 22px/600, sitting on the `#F9F9F9` canvas.

**Tile card (Užitočné odkazy grid):** white, 1px `#DEE2E6` border, `--shadow` (soft),
2px radius, centered black icon + bold dark label, ~24px padding, equal-height grid.

**List row (Najnovšie dokumenty):** blue link text (`#0055A0`, no underline), a right-aligned
`›` chevron, hairline `#DEE2E6` bottom border, hover → faint blue wash `rgba(0,85,160,0.06)`.

**Buttons:** 2px radius, 6–12px padding, solid fill + 1px same-color border.
- Primary action green `#0F663E` / white text.
- Secondary/outline: transparent bg, `#212529` text, 1px `#212529` border.
- Destructive: `#AF0D15`.

**Footer:** `#E9ECEF` bg, `#212529` text, blue links.

---

## 6. CSS custom properties (paste into `globals.css`)

```css
:root {
  /* brand & neutrals */
  --color-blue-700: #0055A0;   /* signature ministry blue */
  --color-blue-50:  rgba(0,85,160,0.10);
  --color-ink:      #212529;
  --color-ink-muted:#495057;
  --color-white:    #FFFFFF;
  --color-canvas:   #F9F9F9;
  --color-surface-2:#E9ECEF;
  --color-border:   #DEE2E6;
  --color-accent-red:#AF0D15;  /* nav underline accent */

  /* semafor — text/strong (AA on white) */
  --color-success:  #0F663E;
  --color-warning:  #8A5300;
  --color-danger:   #AF0D15;
  /* semafor — row tints */
  --tint-success:   #E7F2EC;
  --tint-warning:   #FBF1DD;
  --tint-danger:    #FBE7E8;
  /* semafor — left bars */
  --bar-success:    #0F663E;
  --bar-warning:    #C77700;
  --bar-danger:     #AF0D15;

  /* typography */
  --font-sans: Rubik, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
  --fs-body: 16px;  --lh-body: 1.5;
  --fs-h2: 22px;    --fw-h2: 600;
  --fs-h3: 20px;    --fw-h3: 600;

  /* radius */
  --radius-sm: 2px; --radius: 4px; --radius-lg: 6px;

  /* elevation */
  --shadow-sm: 0 1px 2px rgba(33,37,41,0.06);
  --shadow:    0 2px 8px rgba(33,37,41,0.08), 0 0 0 1px var(--color-border);
  --shadow-md: 0 8px 24px rgba(0,0,0,0.10);
  --shadow-lg: 0 16px 48px rgba(0,0,0,0.176);
}

body { font-family: var(--font-sans); font-size: var(--fs-body); line-height: var(--lh-body); color: var(--color-ink); background: var(--color-canvas); }
h2 { font-size: var(--fs-h2); font-weight: var(--fw-h2); color: var(--color-blue-700); text-transform: uppercase; }
a  { color: var(--color-blue-700); }
```

---

## 7. Tailwind theme config (paste into `tailwind.config.ts`)

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  theme: {
    extend: {
      colors: {
        gov: {
          blue:    "#0055A0",
          blue50:  "rgba(0,85,160,0.10)",
          ink:     "#212529",
          muted:   "#495057",
          canvas:  "#F9F9F9",
          surface: "#E9ECEF",
          border:  "#DEE2E6",
          red:     "#AF0D15", // nav accent + danger
        },
        // semafor (strong = text/icon; tint = row bg; bar = left edge)
        success: { DEFAULT: "#0F663E", tint: "#E7F2EC", bar: "#0F663E" },
        warning: { DEFAULT: "#8A5300", tint: "#FBF1DD", bar: "#C77700" },
        danger:  { DEFAULT: "#AF0D15", tint: "#FBE7E8", bar: "#AF0D15" },
      },
      fontFamily: {
        sans: ["var(--font-rubik)", "Rubik", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Arial", "sans-serif"],
      },
      fontSize: {
        // [size, lineHeight]
        body:    ["16px", "1.5"],
        section: ["22px", "1.2"],   // uppercase blue h2
        card:    ["20px", "1.2"],
      },
      borderRadius: { sm: "2px", DEFAULT: "4px", lg: "6px" },
      boxShadow: {
        sm:  "0 1px 2px rgba(33,37,41,0.06)",
        gov: "0 2px 8px rgba(33,37,41,0.08), 0 0 0 1px #DEE2E6", // default card
        md:  "0 8px 24px rgba(0,0,0,0.10)",
        lg:  "0 16px 48px rgba(0,0,0,0.176)",
      },
    },
  },
};
export default config;
```

> shadcn/ui note: shadcn maps colors via CSS vars (`--primary`, `--background`, …). Set
> `--primary: 209 100% 31%` (HSL of `#0055A0`), `--background: 0 0% 100%`,
> `--muted: 210 17% 95%` (`#F9F9F9`), `--border: 210 14% 89%` (`#DEE2E6`),
> `--destructive: 358 86% 37%` (`#AF0D15`), `--radius: 0.25rem`.

---

## 8. How to apply to our app

**App shell / header**
- White full-bleed header (crest + portal name left; lang/search right).
- Directly below: a `bg-gov-blue` nav strip, white uppercase items (`font-semibold`),
  and a **2px `bg-gov-red` line on its bottom edge** (`border-b-2 border-gov-red`) — this single
  detail sells the "official SK ministry" look.
- Page body on `bg-gov-canvas` (`#F9F9F9`); content blocks are white cards.

**Obvody result list (semafor rows — keep the textual verdict)**
- Each row: white card-row with `border-b border-gov-border`, `py-3 px-4`.
- Status edge: `border-l-4` in `bar-*`; subtle fill `bg-{success|warning|danger}-tint`.
- Verdict label stays **textual and strong-coloured**: e.g.
  `<span class="font-semibold text-success">V súlade</span>` /
  `text-warning "Čiastočný súlad"` / `text-danger "Nesúlad"`, optionally with a small
  badge/icon. Never colour-only — tint + text + (optional) icon together.
- Row title link in `text-gov-blue`, right-aligned `›` chevron, hover `hover:bg-gov-blue50`.

```tsx
// row example
<li class="flex items-center gap-3 border-b border-gov-border border-l-4 border-l-success
           bg-success-tint px-4 py-3 hover:bg-success-tint/70">
  <span class="font-semibold text-success">V súlade</span>
  <a class="text-gov-blue hover:underline">Obvod — ZŠ Mukačevská</a>
  <span class="ml-auto text-gov-muted">›</span>
</li>
```

**Buttons**
- Primary: `bg-success text-white rounded-sm px-3 py-1.5` (the minedu green) **or**
  `bg-gov-blue` for neutral primary actions; secondary: `border border-gov-ink text-gov-ink
  bg-transparent rounded-sm`. Keep `rounded-sm` (2px) — institutional.

**Cards / panels**
- `bg-white rounded shadow-gov p-6`. Title `text-gov-blue text-card font-semibold`.
- Grids of equal-height tiles (icon + bold label) mirror the "Užitočné odkazy" pattern.

**Map side panel / legend**
- Panel: `bg-white shadow-lg rounded-lg` floating over the map.
- Section title: uppercase `text-gov-blue text-section`.
- Legend swatches use the **strong** semafor colours (`#0F663E` / `#C77700` / `#AF0D15`)
  with the SK label next to each (`V súlade` / `Čiastočný` / `Nesúlad`) so the legend matches
  both the map fills and the list rows. Use the same hues for the choropleth district fills
  (lighten ~40% for area fills so labels stay readable).

---

## 9. Source data

Computed-style + colour-frequency dumps used to build this manual:
`/tmp/pw-verify/minedu-data.json`, `minedu-data2.json` (transient).
Durable visual references: `./minedu-ref/*.png`.
