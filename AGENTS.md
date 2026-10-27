# AGENTS.md — agent entry point

Modern, ultra-compact Japanese sentence-mining note type for Anki.
Desktop: Arch Linux Qt6 WebEngine (widescreen, dense). Mobile: Galaxy A50
AnkiDroid WebKit (ultra-compact). This file is the entry point — the
methodology lives in the repository structure, not in this file.

## Authority hierarchy

```text
PRODUCT.md             → what the product must do
MVP.md                 → current scope (agents never widen it unasked)
ARCHITECTURE.md        → technical structure (+ docs/adr/ for lasting decisions)
QUALITY.md             → properties that must remain true
TEST_STRATEGY.md       → how those properties are verified
IMPLEMENTATION_PLAN.md → task graph + status (work the next READY task)
AGENTS.md (this file)  → how to navigate and operate within all of the above
```

`CODE ≠ specification.` Code implements the specs; tests enforce them.

## Read order

1. `PRODUCT.md` + `MVP.md` — what and what-now.
2. `ARCHITECTURE.md` (+ relevant `docs/adr/`) — how it is structured.
3. `QUALITY.md` + `TEST_STRATEGY.md` — invariants + enforcement.
4. `IMPLEMENTATION_PLAN.md` — current work and dependencies.
5. Session bootstrap below, then the existing code.

## Development loop (the repeating unit)

```text
SELECT READY TASK → UNDERSTAND → SMALL CONTRACT → TEST/CHECK → IMPLEMENT
  → TARGETED CHECKS → ./verify → UPDATE STATE/DOCS (only if changed)
  → COMMIT → CI → NEXT READY TASK
```

- Work the next task whose dependencies are COMPLETE; never `Build the MVP`.
- Split the task into the smallest meaningful contracts (validated bricks);
  write the test/check before or alongside each brick, then implement only
  enough to satisfy it.
- Targeted suites while iterating, `./verify` before declaring done.
- Bugs branch inside the loop: diagnose → fix → **add regression test** →
  verify → continue. After ~3 blind retries, stop and diagnose root cause
  (stronger model, then human); fix the cause class (spec, invariant, test,
  architecture, tooling) so the system gets stronger.
- MVP completion adds an end-to-end validation (real user journey in
  `MVP.md`) before release; post-MVP changes go product decision →
  architecture reassessment → tasks → loop → release.

## Operating rules

### 0. Field-Name Bootstrap (fields live in Anki, never in the repo)

Note-type fields are managed **exclusively inside the Anki UI**. At session
start, **before** any template work, run `python3 fetch_anki_fields.py` and
read the gitignored `.anki_fields.json` for exact names/descriptions. If
Anki/Anki-Connect is unreachable, **stop and ask the user to start Anki** —
never guess, invent, or reuse field names from memory or chat history.

### 1. Local files are the single source of truth

All edits happen in the local `.template.anki` / `.css` files. Never instruct
edits inside the Anki UI. Tooling is stdlib-only Python.

### 2. Release workflow (one command, not five)

After **every** template/CSS modification, finish with exactly one command:

```bash
./finish.sh "<semantic commit message>"
# --local: sync + export + commit only · --minor: bump v1.x.0
# --prompt "text": archive prompt (rule 3) before anything runs
```

Chain (stops on first failure): `0.` `./verify` (side-effect-free gate) →
`1.` version stamp → `2.` `sync_to_anki.py` (pre-sync snapshot to gitignored
`backups/<timestamp>/`) → `3.` `release_apkg.py` (deck
`My Life Decks::Japanese::anki-japanese-template` via `exportPackage` to
gitignored `dist/*.apkg`) → `4.` commit → `5.` push main → `6.`
`gh release create --target main` (tag points at the pushed commit) →
fetch the remote tag. The apkg ships as a Release asset, never in the repo.
Do not skip, reorder, or substitute steps.

### 3. Prompt archiving

Archive every new user prompt to `chat_history/opencode_prompts.txt`
(prompt text + `---` separator) before/with its commit — preferably via
`./finish.sh --prompt "<user prompt>" "<message>"`.

### 4. Technical constraints (summaries; full rules in QUALITY.md)

Zero-reflow reveal (hidden rt, hover/tap, `F`; hero absolute ruby;
sentence older-template native `50%` rt (`rt text-align: start`,
sentence type scale unchanged for now) per-kanji distribution) ·
native-only
circular audio (`文`/`言葉`, sibling replay link, debounce, playback
indicator — not true progress) · `R` is Anki-owned (never a template
shortcut) · Mature Word Mode (`LONG_INTERVAL_DAYS = 365`,
desktop-only AnkiConnect content search — one fallback-only path for
reviewer and Browse previewer (live `guiCurrentCard` read removed),
never picks
candidate 0, sentence fallback, mobile intentionally degrades to the
sentence front and makes no network request (`post` UA-guard), listening
untouched,
anti-flash gate) · `#listening` requires usable audio (Policy B: falls back
to sentence without it) · `:has()` is intentional architecture · no debug
badges or verbose labels · vanilla scoped JS resilient to WebView DOM re-use.

## File map

`Card 1 - Front.template.anki` (front modes + Mature Word Mode) ·
`Card 1 - Back.template.anki` (grid, audio, lightbox) ·
`Card 1 - Style.css` (themes, layout, compactor §6b, truncator §6c) ·
`fetch_anki_fields.py` · `sync_to_anki.py` · `release_apkg.py` · `verify` ·
`finish.sh` · `tests/` (compactor + templates + front_modes +
mature_content + layout) · `docs/adr/` · `chat_history/` · `dist/` +
`backups/` (gitignored).
