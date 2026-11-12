# MVP.md — current scope

`PRODUCT.md` answers *what is this product?* This file answers *what are we
actually building right now?* Agents must not independently widen this scope
while coding.

## MVP goal

A shippable, review-ready Japanese sentence-mining note type: dense on
desktop, usable on a small phone, with sentence/word/listening fronts, a
compact informative back, and a one-command sync → export → release loop.

## Core user journey(s)

1. Import the release `.apkg` → review mined cards daily on desktop and phone.
2. Mature cards automatically test the word, not the memorized sentence.
3. Edit templates/CSS locally → `./finish.sh` → cards updated in Anki and a
   new tagged release published.

## Included capabilities

- Front: pure retrieval surface — sentence / Expression fallback,
  Frequency-legacy sentence path, cloze-trio rebuild (never when the trio
  is already contained in the sentence), pure audio-only listening
  cards (usable audio required; `#listening` without audio falls back to
  sentence), Mature Word Mode (interval-gated, desktop-only AnkiConnect
  content search — one fallback-only path for reviewer and Browse
  previewer (live `guiCurrentCard` read removed), mobile intentionally
  degrades
  to the sentence front, never picks candidate 0, sentence fallback).
- Back: typography-driven hierarchy — compact Yūkei scenic band (photo
  when `Picture` exists, illustrated fallback otherwise), word+furigana
  target, quiet pitch text, Definition Compactor (CSS §6b), 3-line truncator
  with one-way expand (§6c), full-width sentence context, native circular
  audio (playback indicator, not true
  progress), secondary information collapsed behind `More ▾` (translation,
  context, kanji notes, notes, full extended definition), source footer.
  Custom shortcuts: `Z` furigana, `X`/`T` translation, `C` expanded-info;
  `R` is Anki-owned (never in the template's shortcut UI). Content
  hierarchy communicates card mode directly.
- Styling: Tokyo Night + Aki Paper themes, fluid clamps, compact scenic
  band with CSS-only photo treatment, zero-reflow furigana + `F`
  full-card furigana mode (back only), Fuji backdrop, reduced-motion
  support.
- Empty-field collapse everywhere: no padding, border, or margin survives an
  empty field; the More section and its toggle self-remove when empty.
- Tooling: field bootstrap (`fetch_anki_fields.py`), snapshotted sync
  (`sync_to_anki.py`), runner-built releases (ADR 007: `build_sample_apkg.py`
  + `release.yml`), `verify` gate, `finish.sh` release loop, regression
  tests (compactor + templates + front-modes + layout + Yūkei scenic-band
  contracts).

## Excluded capabilities

- New fields, add-ons, or review-time Python.
- Additional card types or note types.
- Cloud sync / collaboration / analytics.
- Mandatory per-project doc/diagram checklists beyond `ARCHITECTURE.md`.

## Acceptance criteria

- `./verify` passes (compactor + template invariants; layout checks when
  Chrome is present).
- A real user can complete: import → review sentence card → review mature
  word card → review listening card → expand definition/translation/image →
  edit locally → `./finish.sh` → updated cards + tagged release.
- No horizontal overflow, no viewport-fill dead space, furigana never shifts
  layout, audio never overlaps, failures always degrade to the sentence front.

## Known limitations

- Mature interval needs AnkiConnect (desktop); Browse/template previews without
  it correctly fall back to the sentence front.
- Mature Word Mode is **intentionally unavailable on Android/mobile** (safe
  sentence fallback). The template makes no AnkiDroid JS API interval request,
  because those calls can surface natively as false "Card Content Error:
  Failed to load" media warnings in the reviewer.
- Headless layout checks skip gracefully when Chrome is absent.

## Deferred features

- Further density passes beyond the current clamp/container-query system.
- A reliable mobile interval source that does not trigger AnkiDroid's false
  media-load error (revisit if AnkiDroid stabilises its JS API).
- Extra dictionaries/markup variants beyond current compactor fixtures.
- Any `docs/adr/` entries beyond decided items (added only when a decision
  has alternatives + consequences + long-term relevance).
