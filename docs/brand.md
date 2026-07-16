# Brand note (§7)

The dashboard uses the shared **vibe-shelf design system** — the `:root` block in
`risk_ledger/dashboard.py` is that palette verbatim: five colours (`--bg`,
`--surface`, `--accent`, `--text`, `--text-strong`), every other shade derived
with `color-mix()`, `--danger` the one reserved warning red, Inter + Space Grotesk,
flat surfaces. Raw hex lives **only** in `:root`; all CSS and all baked-SVG marks
reference tokens through `var()` (SPEC v2.4 §1).

This note records the two places the dashboard deliberately departs from, or
extends, the app-oriented rules, so each reads as a decision rather than a drift.

## Sanctioned extension: the RAG status triad

The design system is five colours with no red except `--danger`. A risk dashboard's
entire job is red/amber/green, so — per the GRC build spec §7, which is explicit
that the status triad is **held outside the five-colour palette** — three status
tokens are added:

| Token | Value | Role |
|---|---|---|
| `--status-over` | = `--danger` (`#cf8f83`) | over appetite |
| `--status-at` | `#5fc07e` | at appetite (green) |
| `--status-below` | `#cda23e` | below appetite (amber, unused tolerance) |
| `--status-below-tint` | `#ddb95f` | the same amber, lightened for text < 13px |

They are used **only on risk indicators** (dots, bars, RAG labels, the hero
number), never on chrome, and never colour-alone — every status dot ships beside a
text label. `--status-over` is literally the palette's own `--danger`, so only the
amber and green are genuinely new hues, and both exist because the artifact's core
message is a colour.

## Recorded deviation: the hero number is 40px

The design system says nothing on a normal screen exceeds the 26px wordmark; the
dashboard's hero residual figure is **40px** (with a 30px page `h1`). This is a
deliberate exception: on a dashboard whose entire point is one number read in ten
seconds, a large hero is defensible, and the app-oriented rules were written for
mobile screens and explicitly adapted here (SPEC v2.4 §6). Recorded so it is not
"corrected" back later from memory.

## Contrast — the earned check (§2)

Measured with the WCAG 2.1 relative-luminance formula (sRGB linearisation), fresh
each time from the token values, against `--bg` (`#0f120d`) and `--surface`
(`#1d231c`). AA thresholds: **4.5:1** normal text, **3.0:1** large text / UI.
Derived tokens are composited over the background at their `color-mix` alpha before
measuring.

| Token | on `--bg` | on `--surface` | AA (normal text) |
|---|---|---|---|
| `--text` `#e6e4db` | 14.82 | 12.59 | ✓ |
| `--text-strong` `#ffffff` | 18.87 | 16.04 | ✓ |
| `--accent` `#7d9b83` | 6.19 | 5.26 | ✓ |
| `--status-over` `#cf8f83` | 7.11 | 6.04 | ✓ |
| `--status-at` `#5fc07e` | 8.38 | 7.12 | ✓ |
| `--status-below` `#cda23e` | 7.94 | 6.75 | ✓ |
| `--status-below-tint` `#ddb95f` | 10.05 | 8.54 | ✓ |
| `--text-muted` (≈0.6·text) | 5.87 | 5.44 | ✓ |
| `--text-faint` (≈0.42·text) | 3.46 | 3.37 | large-text only |

**Reading it.** The 10–12px chart labels sit on `--surface` in `--text-muted`
(5.44) or, for the small amber "hidden" annotation, `--status-below-tint` (8.54) —
both clear the 4.5 normal-text bar. The full status trio clears AA on both
surfaces. `--text-faint` is the one token below 4.5; it is a placeholder/tertiary
tone from the design system and is **not used for body text on this dashboard**
(the chrome uses `--text-muted` for secondary and tertiary text), so nothing
essential relies on it.

Reproduce the numbers by re-running the luminance calc over the `:root` values; if a
token changes, update this table.
