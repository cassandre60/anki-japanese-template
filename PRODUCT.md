# PRODUCT.md — Japanese sentence-mining note type

Authoritative source for **what the product is supposed to do**.
Architecture, plans, and agent instructions all defer to this file.

## Problem

Yomitan sentence-mining cards are verbose and ergonomically poor out of the
box: oversized headwords, full multi-dictionary glosses, dead screen space,
clunky audio controls, and a familiar sentence that becomes the retrieval cue
once a card is mature (overlearning). Review on a small phone (Galaxy A50) is
especially wasteful.

## Target users

- Solo learner (the maintainer) mining Japanese sentences via Yomitan /
  jidoujisho into Anki.
- Review contexts: Anki Desktop Qt6 WebEngine (Arch Linux, widescreen) and
  AnkiDroid WebView (Samsung Galaxy A50, small screen).
- Installs via the released `.apkg` (GitHub Release asset), or syncs from
  source with Anki-Connect.

## Core design philosophy

> **Every visible element must justify its existence and its screen space.**

The card is a **minimal Japanese-reading interface**, not a dashboard,
dictionary UI, or mini-SRS. Anki is the SRS: it handles scheduling and
grading. The template's only job is to present the Japanese item clearly,
provide the necessary context for retrieval, and get out of the way.

- The fundamental learning task is: **Japanese word → reading + meaning.**
  No English→Japanese production, no custom grading or confidence buttons,
  no additional learning-mode systems.
- The front is a pure retrieval surface: it contains ONLY the thing being
  tested (sentence with target, mature word, or listening audio button).
- The back establishes hierarchy through typography — target → reading →
  meaning → context — with everything secondary collapsed by default.
- Removal beats addition: when uncertain between adding UI and removing
  it, remove; between always-visible and collapsed/hover, prefer
  collapsed.

## Mining / card-quality invariant

> **The mined sentence shown on the front must be independently
> understandable enough to solve the card.** Additional surrounding
> context (previous/next paragraph, dialogue) is supplementary reference
  material and must never be required for the card to be intelligible.

```
Front sentence = self-contained learning unit
Additional surrounding context = optional reference material
```

This is a mining invariant, not a UI preference: a card whose front needs
off-screen context to be solvable is a bad mine and should be re-mined.

## Core user journeys

1. **Mine → review sentence card.** Yomitan fills Expression / Sentence /
   Definition / audio / Frequency; the front tests sentence recognition, the
   back shows the hierarchy: target+reading, compacted meaning, context.
2. **Review mature card as word card.** Cards with interval ≥
   `LONG_INTERVAL_DAYS` show only the Expression on the front
   (anti-overlearning), with silent fallback to the sentence front. The
   familiar sentence must never become the retrieval cue.
3. **Review listening card.** Cards whose audio is the test (pure audio-only
   fields: no definitions, no frequency) show a single large audio
   button; `#listening` activates the listening front **only when usable
   audio exists** (Sentence Audio, or Word Audio fallback) — without
   usable audio it falls back to the normal sentence front. Normal cards
   are completely unaffected and have zero audio on front.
4. **Expand information on demand.** Secondary info (translation,
   extended definition, additional context, kanji/general notes) sits
   behind one quiet `More ▾` toggle; `T` reveals the translation, `F`
   toggles full-card furigana on the back, picture opens the lightbox.
5. **Install / update.** Import the release `.apkg`, or push local
   templates/CSS to the live profile and re-export via `finish.sh`.

## Functional requirements

- Front modes (in priority order): Definition/Extended-definition →
  sentence; legacy Frequency-only → sentence; pure listening cards (no
  Definition, no Extended-definition, no Frequency, usable audio present)
  → large circular audio button; `#listening` + no usable audio falls
  back to sentence; cloze trio rebuild when Sentence lacks `<b>`; mature
  interval-gated word-only front. Normal cards NEVER render or play audio
  on the front. The sentence front is the universal fallback for every
  failure path.
- Back hierarchy: a compact Yūkei scenic band (the card's `Picture` when
  present, otherwise a decorative Fuji/cloud-sea fallback), then the
  word/furigana target with Japanese seal, 5-star frequency visualizer and
  pitch accent, compacted primary definition (§6b), sentence context, native
  circular audio (`文`/`言葉`),
  secondary information toggleable behind `More ▾` / `Less ▴` (translation,
  context, kanji notes, notes, source, full extended definition), keyboard shortcuts
  hints. Content hierarchy communicates card structure directly.
- Mature Word Mode (desktop only): interval resolved at render time via a
  fallback-only AnkiConnect content search (Expression → Sentence →
  cloze-body discriminators) — reviewer and Browse previewer share the
  one identical path (the live `guiCurrentCard` read was removed), it
  never picks candidate 0 blindly, and any failure → sentence front;
  listening fronts untouched.
  On Android/mobile Mature Word Mode is **intentionally disabled** and the
  ordinary sentence front is shown: the template makes no AnkiDroid JS API
  interval request, because those calls can surface natively as false
  "Card Content Error: Failed to load" media warnings in the reviewer.
- Tags are behavioral metadata, never decoration: hidden probes only;
  `#listening` forces listening behavior (requires usable audio, else
  falls back to sentence); extensible for future behavior-related tags
  without card redesign.
- Tooling: `sync_to_anki.py` pushes Front/Back/CSS with a pre-sync snapshot
  to `backups/<timestamp>/`; `release_apkg.py` exports deck
  `My Life Decks::Japanese::anki-japanese-template` via `exportPackage`;
  `finish.sh` runs tests → sync → export → commit → push → release.

## UX requirements

- Ultra-compact, content-driven height (no viewport fill, no dead space);
  empty space on the front is acceptable — never filled with UI.
- Fluid `clamp()` sizing phone → 4K; a compact scenic band spans the card top
  on desktop and phones, while sentence context remains full-width below it.
- Zero-reflow furigana (hidden, hover/tap reveal, absolute ruby); `F`
  toggles full-card furigana on the back. Hero shows one grouped
  reading annotation (`.hero-reading`) instead of per-kanji segments.
- Native-only audio (delegate to Anki replay link, re-tap debounce,
  playback indicator pulse — never HTML5 `Audio`); `R` is Anki-owned
  (native replay), never a template shortcut. `:has()` is intentional
  architecture for empty-shell collapse.
- Dual themes (Tokyo Night dark / Aki Paper light, follows Anki Night Mode),
  accent color reserved for target highlighting and interactive states,
  `prefers-reduced-motion` support, keyboard focus indicators, aria
  labels/roles.
- Japanese remains the dominant visual language: English typography never
  competes with it.

## Constraints

- Vanilla JS/CSS only, scoped, resilient to Anki WebView DOM re-use.
- Fields live **exclusively in the Anki UI**; repo keeps no static field
  list (`fetch_anki_fields.py` → gitignored `.anki_fields.json` is the only
  source).
- Local `.template.anki` / `.css` files are the single source of truth —
  never edit inside the Anki UI.
- Screen real estate is precious: no debug badges or verbose header labels.
- Stdlib-only Python tooling (no third-party runtime deps; test-only deps
  allowed).

## Non-goals

- New Anki note-type fields, add-ons, or Python-at-review solutions.
- Multi-note-type theming system or generic card framework.
- Enterprise release management (solo `finish.sh` flow is enough).
- Server/cloud sync, collaboration, analytics.
- English→Japanese production mode, custom grading UI, confidence
  buttons, learning-mode systems beyond context/word/listening.

## Important assumptions

- Yomitan markup shape (`.yomitan-glossary`, `data-sc-*` attributes) is
  stable enough for structural CSS scoping; drift is caught by fixtures.
- AnkiConnect on `127.0.0.1:8765` (desktop) remains the interval source; it
  can be absent. The AnkiDroid JS bridge is deliberately **not** used
  (its calls can trigger the reviewer's false media-load error).
- One card type ("Card 1"); model name
  `Japanese Note type (Sentence card by Default)` is stable.

## Open questions

- None blocking. Candidate evolution items live in `MVP.md` (Deferred) and
  `IMPLEMENTATION_PLAN.md` (roadmap).
