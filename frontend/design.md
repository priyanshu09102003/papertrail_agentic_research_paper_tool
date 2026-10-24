---
version: alpha
name: Linear Dark
description: A restrained, high-contrast product system with soft depth, precise typography, and a cool violet accent.
colors:
  primary: "#7170ff"
  secondary: "#f7f8f8"
  tertiary: "#8b8f98"
  neutral: "#08090a"
  surface: "#0f1011"
  on-surface: "#f7f8f8"
  muted: "#a1a5ad"
  border: "#ffffff14"
  border-strong: "#e5e5e6"
  overlay: "#00000080"
  success: "#2ecc71"
  warning: "#f5c542"
  error: "#ff5b5b"
typography:
  headline-display:
    fontFamily: "Inter Variable"
    fontSize: "72px"
    fontWeight: 510
    lineHeight: "86px"
    letterSpacing: "-1.408px"
  headline-lg:
    fontFamily: "Inter Variable"
    fontSize: "49px"
    fontWeight: 510
    lineHeight: "72px"
    letterSpacing: "-1.584px"
  headline-md:
    fontFamily: "Inter Variable"
    fontSize: "33px"
    fontWeight: 510
    lineHeight: "40px"
    letterSpacing: "-0.24px"
  headline-sm:
    fontFamily: "Inter Variable"
    fontSize: "22px"
    fontWeight: 510
    lineHeight: "28px"
    letterSpacing: "0px"
  body-lg:
    fontFamily: "Inter Variable"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "24px"
    letterSpacing: "-0.165px"
  body-md:
    fontFamily: "Inter Variable"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: "24px"
    letterSpacing: "-0.165px"
  body-sm:
    fontFamily: "Inter Variable"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
    letterSpacing: "-0.12px"
  label-lg:
    fontFamily: "Inter Variable"
    fontSize: "16px"
    fontWeight: 510
    lineHeight: "24px"
    letterSpacing: "-0.08px"
  label-md:
    fontFamily: "Inter Variable"
    fontSize: "14px"
    fontWeight: 510
    lineHeight: "20px"
    letterSpacing: "-0.08px"
  label-sm:
    fontFamily: "Inter Variable"
    fontSize: "12px"
    fontWeight: 510
    lineHeight: "16px"
    letterSpacing: "0px"
  code-sm:
    fontFamily: "Berkeley Mono"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "20px"
    letterSpacing: "0px"
  caption:
    fontFamily: "Inter Variable"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
    letterSpacing: "0px"
rounded:
  none: "0px"
  sm: "4px"
  md: "8px"
  lg: "9px"
  xl: "14px"
  full: "9999px"
spacing:
  xs: "6px"
  sm: "20px"
  md: "30px"
  lg: "60px"
  xl: "96px"
  gutter: "20px"
  section: "96px"
components:
  button-primary:
    backgroundColor: "{colors.border-strong}"
    textColor: "{colors.neutral}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: "14px 20px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.neutral}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: "14px 20px"
    height: "44px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: "14px 20px"
    height: "44px"
  button-link:
    backgroundColor: "transparent"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-lg}"
    rounded: "{rounded.none}"
    padding: "0px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: "12px 16px 16px"
  panel:
    backgroundColor: "#111213"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: "16px"
  input:
    backgroundColor: "#121314"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
  chip:
    backgroundColor: "#151617"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: "6px 10px"
---

# Linear Dark

## Overview
This system feels disciplined, technical, and quietly premium. It is designed for a sophisticated product audience that values clarity, speed, and low visual noise, with a strong emphasis on readability in dark mode. The tone is modern and confident rather than expressive, with small highlights of violet used to signal interaction and brand personality.

## Colors
- **Primary (#7170ff):** A cool violet accent used sparingly for active states, product signals, and brand moments. It adds energy without breaking the restrained dark palette.
- **Secondary (#f7f8f8):** The main text and high-emphasis foreground color. It reads as near-white, providing strong contrast on dark surfaces.
- **Tertiary (#8b8f98):** A subdued cool gray for secondary text, metadata, and navigational items that should remain visible but quiet.
- **Neutral (#08090a):** The page background, an almost-black tone that makes the interface feel immersive and reduces glare.
- **Surface (#0f1011):** The primary panel and card surface color. It separates content from the background with a subtle tonal shift instead of a bright container.
- **On-surface (#f7f8f8):** The default content color on elevated surfaces, matching the system’s crisp, high-contrast reading style.
- **Muted (#a1a5ad):** A softer gray for supporting text, labels, and less critical details.
- **Border (#ffffff14):** A faint translucent border used to outline cards and panels without heavy framing.
- **Border-strong (#e5e5e6):** A brighter neutral used for key interactive elements such as the primary button.
- **Overlay (#00000080):** A translucent scrim for menus, dialogs, or focus states when the interface needs to recede.
- **Success (#2ecc71):** A restrained green for positive states and status indicators.
- **Warning (#f5c542):** A warm yellow used for attention states, badges, and priority markers.
- **Error (#ff5b5b):** A vivid red for destructive actions and validation errors.

## Typography
Inter Variable is the core UI font, and it carries nearly all headings, body copy, and labels. Headlines use a slightly unconventional weight of 510, which gives them a precise, engineered feel without becoming too bold; the large display sizes are tight, compact, and highly legible in dark mode. Body text stays calm and readable at 15px–16px with generous 24px line height, while smaller labels and metadata use medium weight to maintain clarity in dense interfaces.

The system favors subtle negative letter spacing in larger type, which helps the wide headlines feel polished and editorial. Uppercase treatment is minimal; the visual language relies more on spacing, scale, and contrast than on all-caps labeling. Berkeley Mono is reserved for code-like snippets and technical tokens, reinforcing the product’s software-first identity.

## Layout
The layout is spacious at the page level, with large vertical gaps between the navigation, hero copy, and product preview. Content appears centered within a broad max-width container, with generous side margins that allow the hero headline and screenshot panel to breathe. The rhythm is based on a compact spacing ladder: 6px for micro adjustments, then 20px, 30px, 60px, and 96px for larger structural separation.

Cards and panels use consistent internal padding rather than heavy outer margins, which keeps the interface feeling dense but controlled. Section spacing should remain generous, especially in marketing contexts, while internal UI density can tighten for product views and data-heavy screens.

## Elevation & Depth
The system is intentionally low-elevation and mostly flat. Instead of pronounced drop shadows, it uses tonal layering: background, surface, and slightly lighter panels stack to create hierarchy. Thin borders and subtle inset effects do most of the work, especially around cards, buttons, and framed regions.

Depth should feel precise rather than dramatic. When shadows appear, they are soft and minimal, supporting the impression of a polished, matte interface rather than a glossy one.

## Shapes
The shape language is rounded but restrained. Most interactive controls use pill radii, while cards and panels settle into a modest 9px corner radius for a more structural feel. This creates a balance between friendly touch targets and a disciplined product surface.

Avoid overly soft or playful curves. The system should feel engineered, with rounded corners used as a refinement rather than a decorative theme.

## Components
Buttons should follow a clear hierarchy. `button-primary` is a filled pill with dark text on a light neutral background, sized at 44px tall with 14px 20px padding. It is the most prominent action and should feel calm, not flashy. `button-secondary` keeps a transparent fill with light text and subtle treatment for less dominant actions. `button-link` is minimal, unboxed, and used for inline navigation or tertiary actions.

Cards use the `card` token: dark surface, 1px translucent border, 9px radius, and modest internal padding. They should feel like contained modules rather than floating elevation layers. `panel` can be used for larger application regions that need a slightly stronger container presence.

Inputs should visually match the rest of the dark surfaces: muted background, light text, restrained borders, and rounded corners. Field states should depend more on border and text contrast than on large color shifts. Chips should be compact pills with small padding and a dark neutral fill, using accent color only for status dots or selected indicators.

Icons and utility controls should be small, subtle, and aligned tightly to text. Lists and metadata rows should use muted text by default, with brighter foreground only for active or selected items. The overall component system should preserve density without sacrificing legibility.

## Do's and Don'ts
- Do keep the interface dark, tonal, and low contrast between container layers.
- Do use the violet accent sparingly for active states, key signals, and brand emphasis.
- Do rely on Inter Variable for almost all UI text, reserving Berkeley Mono for technical snippets.
- Do use thin borders and subtle inset styling instead of heavy shadows.
- Do keep large headings tight and confident with slightly negative letter spacing.
- Don't introduce bright or saturated colors that compete with the primary accent.
- Don't use oversized radii or soft, bubbly shapes that weaken the product feel.
- Don't overuse shadow depth; the system should feel precise and mostly flat.