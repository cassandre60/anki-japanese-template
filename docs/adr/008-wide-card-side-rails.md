# ADR 008 — Wide-card side rails replace the top scenic band

Builds on ADR 005 (illustrated Yūkei band) and ADR 006 (photo-derived band).
This ADR changes only the **wide desktop** presentation; phones and narrow
reviewer panes keep ADR 005/006 exactly as shipped.

## Context

The top scenic band is the back card's first visual block on every card. It
paints 56–70px but its net flow cost is ~34–40px on desktop and ~37–50px on
phones. On the maintainer's widescreen desktop reviewer that vertical strip is
the most expensive decoration in the card, while the same card already sits on
a full-window Fuji backdrop (§14). The band therefore reads as a second,
smaller landscape pasted above the content.

Phones are a different constraint: AnkiDroid gives the card only 6px of side
padding at 412px wide, so there is no gutter for a side treatment; the compact
top band is the correct mobile answer. The maintainer explicitly asked for a
desktop-only compromise so the phone layout stays untouched.

Two further constraints shaped the implementation:

1. `QUALITY.md` requires exactly one `{{Picture}}` reference. A naive
   two-rail design would either reference the field twice or duplicate the
   lightbox trigger and its tab stop.
2. Anki's reviewer pane width is not the monitor width. A 27-inch display can
   host a 700px reviewer pane, so the gate must be the card's container width,
   not a viewport media query.

## Options considered

1. Keep the top band everywhere — rejected: it preserves the mobile layout but
   leaves the desktop vertical cost and the duplicated-landscape feel.
2. Remove the scenic treatment on wide cards — rejected: it loses the card's
   visual identity and the lightbox affordance.
3. Two independent rail elements, each with its own `{{Picture}}` — rejected:
   violates the single-reference invariant and creates two focus stops for one
   image.
4. **One full-card band, clipped into two side rails (chosen).** The existing
   single band becomes an absolutely positioned layer, clipped by an SVG
   `clipPath` with two `objectBoundingBox` rectangles. The existing photo
   trigger still fills the layer, so there is one `Picture` reference, one
   tab stop, one lightbox target, and both rails remain clickable.

## Decision

- **Gate:** `@container anki-card (min-width: 1000px)`. The query container is
  the existing `.card-wrapper` (`container-type: inline-size`). Below 1000px
  the §17 top band is untouched; this includes narrow desktop panes.
- **Geometry:** on wide cards `.scenic-band` becomes `position: absolute;
  inset: 0; height: auto; margin: 0; z-index: 0`. It leaves the flow entirely,
  so the content starts at the card's normal top padding.
- **Rails:** one inline `<clipPath id="scenic-side-clip">` per band branch,
  with rects `0 → 0.04` and `0.96 → 1` (`objectBoundingBox`). The 4% token is
  `--scenic-rail-w`; at a 1360px card that is ~54px per side, deliberately
  larger than the earlier 3% prototype. A vertical mask fades both rail ends;
  `::before` / `::after` gradients fade each rail's inner edge into the card
  surface, so only the outer ~60% reads as colour.
- **Colour:** the wide rails always use the cool `--scenic-sky` gradient (the
  ADR 005 fallback look), not the photo-derived warm strip. The maintainer
  preferred that calm blue/purple palette and asked for it going forward. In
  the light theme the token resolves to the theme's warm sky, preserving the
  existing dual-theme system.
- **Photo:** the on-card photo/scene is hidden on wide cards; the photo
  trigger itself stays alive and transparent, keeping the lightbox access and
  the single focus stop. Its keyboard ring is inset (`outline-offset: -4px`)
  so the clipped rails still show focus; focusing the trigger also brightens
  the rails.
- **Content layer:** everything after the band is wrapped in
  `.card-content` (`position: relative; z-index: 1`) so the card content paints
  above the absolute band. The wrapper has no other styles; narrow layouts are
  byte-for-byte unchanged.
- **No JS, no new fields, no new assets.** `openLightbox` is untouched. The
  clip-path definition box is zero-sized so it cannot consume band height.

## Consequences

- Wide desktop cards reclaim the band's ~34–40px flow cost; the rails occupy
  the existing side padding and the faded inner edge does not cross the
  content area.
- Mobile and narrow reviewer panes keep the ADR 005/006 top band, photo
  pipeline, and full-width lightbox target. Existing mobile contracts remain
  valid.
- The card-derived photo is no longer visible on wide cards, but it is still
  one click/Enter away in the lightbox; the rails are the quiet decorative
  surface instead.
- `tests/test_yukei.py` gains wide-card contracts (absolute zero-flow band,
  clip/mask, cool gradient, rail hit-testing, hidden scene, inset focus CSS,
  content layer) and a narrow-pane regression (900px keeps the top band).
  The mobile contracts continue to run unchanged.
- The breakpoint is a judgement call: 1000px is wide enough for two rails plus
  a readable centre column, and low enough for common maximized desktop
  reviewer panes. Revisit only with a layout-probe proof.
