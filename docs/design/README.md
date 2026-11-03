# Design exports

- `screens/<section>-<screen>-<theme>.{png,html}` — screen mockups. Section numbers follow `docs/design-prompt.md`. The `.html` file is the generated mockup source (Tailwind CDN); use it to read exact spacing and colors, never copy it into the app.
- `tokens.json` — design tokens (light/dark colors, type scale, spacing, radii, shadows, z-index). Each key becomes a CSS variable (`color.bg.canvas` → `--color-bg-canvas`).
- `design-system.md` — the design system rationale ("Academic Workbench") that the tokens come from.

The frontend takes colors, sizes and spacing from the tokens, never from hard-coded values.

## Known gaps and conflicts (see `docs/progress.md` → Open questions)

- Only the matrix screen exists in dark theme; dark tokens are a draft derived from it.
- Missing: 4.1 welcome screen and new-review form, all of 4.6 (inbox banner, import preview, `.bib`/`.ris` wizard), component sheet, collapsed shell, empty/loading/offline states, English variants.
- Mockups contain later-phase features (AI, highlights, card/timeline views, Zotero, sync). Phase 1 implements only what `docs/plan.md` lists; where a mockup contradicts the plan (AGPL license label, CLI daemon socket, multi-worker pool, cloud sync), the plan wins.
