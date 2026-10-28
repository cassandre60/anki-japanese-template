# VISUAL_SYSTEM.md — card design system (skill adaptation)

This repo vendors the `landing-page-design` skill from
[elayadesign/ai-design-skills](https://github.com/elayadesign/ai-design-skills)
at `.opencode/skills/landing-page-design/`. The skill is a **landing-page**
system; a flashcard is not a landing page. This file is the authority
boundary between them: it records which rules the product applies, how they
were adapted, and which are deliberately excluded.

Precedence: `PRODUCT.md`, `QUALITY.md`, and `AGENTS.md` always win over the
skill. The skill never overrides measured typography, Anki constraints, or
the single-source-of-truth workflow.

## Applied

| Rule | Adaptation | Enforced by |
| --- | --- | --- |
| B7 Motion: one decelerating curve, no browser-default easing, animate `transform`/`opacity` only | `--ease-settle: cubic-bezier(0.22, 1, 0.36, 1)`, `--motion-hover: 200ms`, `--motion-settle: 300ms`. Every `transition` resolves through the tokens. The frequency bar animates `transform: scaleX()`, not `width`. | `tests/test_design_system.py` |
| B9 States: hover, active, focus, no dead affordances | Press states (`translateY(1px)` / `scale(0.98)`) on audio, More, translation, hint chips, and both image triggers. Visible focus ring on the clickable definition box, which is `tabindex="0" role="button"` even before truncation. Empty-state collapse was already stronger than the skill requires. | same |
| B4 Borders: no single-sided card borders | Removed the `border-left` pull-quote rule from `.secondary-block`; the warm tint carries the block. Section dividers (`.extended-def-wrapper`) are rules, not cards. | same |
| B3 Radius: Tailwind steps and the nested formula | `--border-radius-md` snapped 10px to 8px, hint chips 5px to 6px, brushstroke highlight 3px to 2px. Nested shapes already sit outside the 32px gap or are clipped by the rounded container, so the formula needs no further change. | same |
| B1 Type scale (chrome only) | Fixed-size UI labels share `--text-label: 0.75rem` (12px): More, frequency badge and stars, translation hint, source, section header, hint chips, keycaps, audio labels. Japanese content keeps its fluid `clamp()` scale, which is product-owned and measured in `QUALITY.md`. | same |
| B1 Copy: no orphaned last line | `text-wrap: balance` on the hero expression; `text-wrap: pretty` on sentence, definition, and secondary copy. Older WebViews ignore the property; layout is unaffected. | same |
| B9 Accessibility: readable secondary text | `--text-muted` raised to WCAG AA 4.5:1 on both card surfaces (`#77869d` dark, `#6b7280` light). The extra opacity multipliers on hint and footer text were removed so token contrast survives. | same |

## Excluded (and why)

| Rule | Why not |
| --- | --- |
| Part A: offer, CTA, page structure, SEO/AEO, FAQ, tagline reveal (B11) | A card is a single retrieval surface, not a marketing page. |
| B1 font list (Geist/Manrope/Poppins, "never Inter") | The interface stack is product-owned and ships no webfonts; Japanese needs its own serif stack. |
| B1 Tailwind type scale for content | The Japanese sizes are measured `clamp()` tokens (`QUALITY.md`, v1.8.75/76). Snapping them to fixed steps would break responsive hierarchy and the furigana contracts. |
| B2 fixed spacing table | The card uses fluid viewport spacing (`--gap-*`, `--container-pad-*`) to fill Anki's reviewer pane at any size. |
| B4 dark palette (`#181818` family) and "no gradients" | Tokyo Night and Aki Paper are the product themes. Gradients are the illustrated scenic band (ADR 005/006), the ink underline, and a functional truncation scrim, not decorative page backgrounds. |
| B5 hero text gradient | Would fight the accent-reserved Japanese typography and the zero-reflow reveal. |
| B6 icon sets | The UI uses Japanese glyphs and inline SVG; no icon font ships in an apkg. |
| B8 marketing copy realism | No marketing copy exists in the product. |
| B10 ship checklist (favicon, 404, meta, legal, cookie consent, skip link) | Belongs to a website, not to an Anki note type. Alt text and focus rings are already enforced. |
| B7 scroll reveals, navigation motion, 500ms layout transitions | The card has no scroll narrative or navigation, and it must settle in about 150ms because it is reviewed hundreds of times per session. |

## Re-syncing upstream

Replace `SKILL.md` with the upstream file, update
`.opencode/skills/landing-page-design/UPSTREAM.md` (commit hash and checksum),
then re-run `./verify`. If upstream adds a rule, decide its row in the tables
above before writing code.
