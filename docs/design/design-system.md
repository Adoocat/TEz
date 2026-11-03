---
name: Academic Workbench
colors:
  surface: '#fbf9f8'
  surface-dim: '#dbd9d9'
  surface-bright: '#fbf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3f3'
  surface-container: '#efeded'
  surface-container-high: '#eae8e7'
  surface-container-highest: '#e4e2e2'
  on-surface: '#1b1c1c'
  on-surface-variant: '#43474e'
  inverse-surface: '#303030'
  inverse-on-surface: '#f2f0f0'
  outline: '#74777f'
  outline-variant: '#c4c6cf'
  surface-tint: '#455f87'
  primary: '#022448'
  on-primary: '#ffffff'
  primary-container: '#1e3a5f'
  on-primary-container: '#8aa4cf'
  inverse-primary: '#adc8f5'
  secondary: '#712ae2'
  on-secondary: '#ffffff'
  secondary-container: '#8a4cfc'
  on-secondary-container: '#fffbff'
  tertiary: '#002b0f'
  on-tertiary: '#ffffff'
  tertiary-container: '#00431b'
  on-tertiary-container: '#55b66c'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d5e3ff'
  primary-fixed-dim: '#adc8f5'
  on-primary-fixed: '#001c3b'
  on-primary-fixed-variant: '#2d486d'
  secondary-fixed: '#eaddff'
  secondary-fixed-dim: '#d2bbff'
  on-secondary-fixed: '#25005a'
  on-secondary-fixed-variant: '#5a00c6'
  tertiary-fixed: '#95f8a7'
  tertiary-fixed-dim: '#79db8d'
  on-tertiary-fixed: '#00210a'
  on-tertiary-fixed-variant: '#005323'
  background: '#fbf9f8'
  on-background: '#1b1c1c'
  surface-variant: '#e4e2e2'
  bg-canvas: '#fcfbf9'
  bg-surface: '#f5f4f0'
  border-subtle: '#e5e3dc'
  text-primary: '#1c1917'
  text-muted: '#78716c'
  status-included: '#15803d'
  status-excluded: '#b91c1c'
  status-maybe: '#b45309'
  status-unverified: '#ea580c'
  status-retracted: '#991b1b'
  status-ai: '#7c3aed'
  status-reading-blue: '#2563eb'
  status-revisit-purple: '#9333ea'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  headline-sm:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
  body-reading:
    fontFamily: Source Serif 4
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  body-ui:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-ui-medium:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-meta:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-meta-medium:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  code-tech:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  code-kbd:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-compact: 0.5rem
  margin: 1rem
  margin-panel: 0.75rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system embodies the focused calm of an uncluttered, physical scholar's desk translated into high-performance desktop software. Drawing structural inspiration from developer-grade environments (Linear, JetBrains, Obsidian, Zotero 7), it treats scholarly inquiry not as bureaucratic data entry, but as deep analytical work requiring prolonged cognitive endurance.

### Aesthetic Movement
The aesthetic aligns with **Functional Structuralism** and **Minimalist Technical Workbench**:
- Flat, planar layout architectures where spatial boundary is defined by sharp 1px hairline rules rather than ambient blurred shadows or multi-layered skeuomorphism.
- Extreme discipline regarding distraction: zero neon glows, no synthetic gradients, and no glassmorphic backdrop filters.
- Absolute data provenance: machine-generated inferences are strictly demarcated from verified human citations, preventing epistemic contamination.
- High-density information display engineered for keyboard-first navigation (vim/IDE-inspired shortcut ergonomics).

## Colors

The palette establishes an intentional distinction between structural reading surfaces, primary interactions, and strict academic classification tokens.

### Base & Neutrals
- **Canvas & Surface:** Built on warm, muted paper tones (`#fcfbf9` canvas, `#f5f4f0` panels) in light mode to eliminate glare during multi-hour screening sessions. Dark mode reverses these using carbon and graphite greys (`#18181b` canvas, `#27272a` surfaces) without dropping to pure `#000000`.
- **Text:** Carbon black (`#1c1917`) for laser-sharp typographic contrast, paired with warm stone grey (`#78716c`) for metadata and taxonomy labels.

### Interaction & Brand Accent
- **Primary Ink Blue (`#1e3a5f`):** Echoes archival fountain pen ink. Used for active navigation tabs, focused selection states, primary command triggers, and verified page-level citations.

### SLR Protocol & Semantic Screening
- **Included (`#15803d`):** Deep botanical green indicating criteria match.
- **Excluded (`#b91c1c`):** Rose-brick crimson paired strictly with exclusion reason tags.
- **Maybe / Amber (`#b45309`):** Cautious amber for ambiguous papers needing team consensus.
- **AI Suggested (`#7c3aed`):** Distinct violet used uniquely for machine-synthesized extractions. It must always render with dashed structural boundaries or explicit `✦` badging.
- **Unverified Claim (`#ea580c`):** Vibrant warning orange rendered as a wavy baseline underline on ungrounded extracted claims.

## Typography

Typographic roles strictly bifurcate cognitive tasks into interface operation, immersive synthesis reading, and technical identification.

### Font Hierarchy
1. **Application Shell & UI Controls (Inter):** Clean, neutral neo-grotesque with exhaustive Turkish diacritics support (`ğ`, `ı`, `İ`, `ş`, `ç`, `ö`, `ü`). Used for dense layout grids, navigation trees, inputs, and screening triage actions.
2. **Reading & Synthesis Body (Source Serif 4):** A book-grade editorial serif calibrated at 15px with a generous 1.6 line-height (`24px`). Applied to abstract panes, research notes, and AI-synthesized narrative briefings to prevent optical fatigue.
3. **Technical & Metadata Precision (JetBrains Mono):** Monospaced, highly legible numerals and characters for BibTeX keys, DOI strings, boolean query syntax, and keyboard shortcuts (`⌘K`, `I`, `E`).

## Layout & Spacing

The layout is built on a tight, deterministic **4px micro-grid** tailored for multi-column desktop environments.

### Desktop Shell Dimensions
- **Activity Bar / Navigation Rail:** 56px fixed width on the far left.
- **Context Sidebar (Collections/Queries):** 240px fixed or collapsible width.
- **Inspector Panel (Item Details & Extracted Matrix):** Resizable between 320px and 400px.
- **Main Workspace Canvas:** Fluid flex container containing either the Literature Matrix or a Split-view PDF Screen.

### Table & List Row Densities
- **Compact (28px height):** Standard for triage lists, bibtex tables, and rapid decision mode.
- **Comfortable (36px height):** Used for complex screening cards, note trees, and multi-line item overviews.

Element spacing relies on fixed `0.25rem` (4px) increments: `space-xs` (4px) for inline badge and chip gaps, `space-sm` (8px) for input padding and toolbars, and `space-md` (12px) for panel margins.

## Elevation & Depth

This design system uses a strict **Planar Layering Model** without ambient drop shadows or floating elevations.

### Structural Hairlines
Visual boundaries are established exclusively via 1px neutral borders (`#e5e3dc` in light, `#27272a` in dark). Resizable splitters, headers, footers, and matrix grid lines rely solely on structural line separation.

### Surface Tiers
- **Canvas Tier (0dp):** Main window background and underlying PDF container (`--bg-canvas`).
- **Surface Tier (1dp):** Sidebars, table containers, and inspectors (`--bg-surface`).
- **Active / Hover Tier (2dp):** Subtly shifted surface luminance (+2% brightness or neutral tint) on row hover. No elevation or blur is applied.

### Overlays
Floating popovers (such as the `⌘K` Quick Open palette or Citation Picker) use a crisp 1px border paired with a deep, non-diffuse, minimal scrim: `box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08)`. Blurs and frosted glass techniques are expressly forbidden.

## Shapes

The shape vocabulary communicates precision, software engineering rigor, and structural stability. 

- **4px Radius (`space-xs`):** Assigned to metadata chips, source verified pills (`[Yazar 2024 · s.4]`), mini status dots, and keyboard command badges (`kbd`).
- **6px Radius (Base Controls):** Assigned to buttons, form inputs, table active row selections, and search containers.
- **10px Radius (Dialog Frames):** Reserved exclusively for modals, the command palette overlay container, and detached float windows.
- **Borders & Dividers:** Always 1px solid hairline, except for AI proposals which use a 1px dashed pattern with 4px dash intervals.

## Components

### Buttons & Action Triggers
- **Primary Action:** Solid ink blue (`#1e3a5f`), white text, 6px border radius, 28px height (compact) or 32px (standard), accompanied by a right-aligned monospaced shortcut cue (`↵`).
- **Screening Decision Buttons:**
  - *Include (`Dahil`):* Bordered green badge (`#15803d`), keyboard shortcut `I`.
  - *Exclude (`Hariç`):* Bordered red badge (`#b91c1c`), keyboard shortcut `E`, clicking triggers an exclusion taxonomy dropdown.
  - *Maybe (`Belki`):* Bordered amber badge (`#b45309`), keyboard shortcut `M`.
- **Ghost / Tool Buttons:** 28px × 28px icon hit targets (Lucide 16px icons) with flat styling; hover activates a 1px neutral border.

### Status Indicators & Source Chips
- **Reading Status Circles:** 8px solid or hollow circular indicators:
  - Grey: Unread
  - Blue (`#2563eb`): Currently Reading
  - Green (`#15803d`): Finished / Extracted
  - Violet (`#9333ea`): Marked for Revisit
- **Verified Source Chip:** 4px radius chip in `#1e3a5f` with 10% opacity background, dark ink text, featuring the publication year and page number (`[Gök 2023 · s.12]`). Clicking shifts the PDF viewer directly to the source coordinates.
- **AI Suggested Extraction Cell:** Rendered with a 1px dashed violet border (`#7c3aed`), tinted violet background (5% opacity), accompanied by a leading `✦` glyph and a one-click confirmation tick (`✓`).
- **Ungrounded Claim Indicator:** Orange squiggly underline (`text-decoration: underline wavy #ea580c 1.5px`) highlighting model outputs that lack an anchor citation in the PDF text.

### Tables & Matrix Grid
- Dense data grid with 1px border intersections. Row heights lock to 28px in compact mode and 36px in comfortable mode.
- Leftmost indicator column showcases status dot, screening pill, and star flags without expanding column widths.
- Active cell displays a 1px solid focus border matching primary blue, enabling fluid arrow key traversal.

### Keyboard Badges (`<kbd>`)
- Monospaced 11px font (`JetBrains Mono`), 4px border radius, 1px solid border (`#d6d3d1`), light stone background (`#f5f5f4`), 2px 4px internal padding. Displayed inline next to commands (e.g., `⌘K`, `⇧E`).