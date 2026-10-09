# TEST_STRATEGY.md — how QUALITY.md is mechanically verified

```text
QUALITY.md (WHAT must remain true)
  → TEST_STRATEGY.md (HOW it is verified)
    → tests / linters / headless checks / CI
```

## Layers (narrow → broad)

```text
tiny brick test → targeted suite → ./verify → CI (clean env)
```

While iterating, run the targeted suite; before declaring a task complete,
run `./verify`; CI re-runs `./verify` after every push.

## Enforcement map

| Requirement (QUALITY.md) | Enforcement |
| --- | --- |
| Compactor keeps 1st dictionary, ≤2 senses, no appendices; extended definition untouched; rules scoped to `.primary-definition` | `tests/test_compactor.py` — extracts real `display:none` rules from CSS §6b, applies to `tests/fixtures/*.html` (bs4 + soupsieve) |
| Front furigana ban; raw Sentence/Expression present | `tests/test_templates.py` §1 |
| Audio aria-labels; native-only controller; sibling replay source; debounce; restart-only | `tests/test_templates.py` §§2–3b |
| Cloze probe shape, trio gate, `<b>` rebuild, bold guard | `tests/test_templates.py` §2c |
| Yūkei scenic band: one `Picture` reference; photo/fallback conditionals; accessible photo trigger; no retired inline thumbnail; corrected `saturate()` + `overlay` pipeline; fallback reduced motion | `tests/test_yukei.py` — back-template/CSS structural contracts plus headless Chrome interaction/layout probes; runs during the minimal-front isolation branch |
| Lightbox backdrop-only close, dialog semantics, alt | `tests/test_templates.py` §4 |
| Balanced Anki conditionals | `tests/test_templates.py` §5 |
| Minimal redesign: no tags bar / frequency badges; More collapse; state label; F/T shortcuts; listening resolver wiring | `tests/test_templates.py` §§6b–6c |
| `:focus-visible`, reduced motion, content-driven sizing, context-grid fallback, clamp() authority, no JS font override | `tests/test_templates.py` §§6–7 |
| Mature Word Mode: const, desktop-only retrieval, no executable AnkiDroid JS API / bridge code, mobile degrades to sentence, no `note:` clause, anti-flash gate, word-mode CSS | `tests/test_templates.py` §8b |
| Mature content-search fallback: never picks candidate 0, Sentence + cloze-body discriminators, fails safely on ambiguity, exact-card resolution | `tests/test_mature_content.py` — extracts the content-search block verbatim, runs 6 headless Chrome cases with mocked AnkiConnect (skipped gracefully without Chrome) |
| Listening Policy B + exactly-one-button: `#listening` without audio → sentence front; `#listening` with audio → listening front; both-views markup → exactly one active; dead/duplicate views removed | `tests/test_front_modes.py` — 8 state harnesses in headless Chrome (skipped gracefully without Chrome) |
| Listening audio source: tag-listening-view binds to `{{Sentence Audio}}` (not `play:a:0`), Word Audio fallback, label matches | `tests/test_templates.py` §6d |
| R shortcut is Anki-owned (never in template shortcut UI); playback indicator terminology | `tests/test_templates.py` §§6e–6f |
| Shortcut hints are clickable controls: `<button data-shortcut>` markup, one shared `applyShortcut` action table for keys + clicks, CSS affordance | `tests/test_templates.py` §6e2 (structural) + `tests/test_shortcut_clicks.py` (headless Chrome: click Z/X/C toggles the same state the keys do, inner `<kbd>` click, C never touches the translation, unbound keys inert, missing translation/More degrades without errors) |
| finish.sh deterministic ordering (push main before release, `--target main`), no-op protection | `tests/test_templates.py` §9 |
| Stdlib-only sync, microsecond backups, finish.sh no-op guard | `tests/test_templates.py` §9 |
| Content-driven height, no h-overflow, furigana containment, type hierarchy, 3-line clamp + one-way expand, listening target size, context grid, More collapsed by default, footer containment | `tests/test_layout.py` — headless Chrome on the **real** stylesheet; skipped gracefully when Chrome is absent |
| Shortcut hints stay usable on phones: visible (never `display:none`), ≥44px tall, all three in one row inside the card | `tests/test_layout.py` mobile probes (desktop too) |
| Listening resolver behavior: classic audio-only fields and `#listening` tag activate the audio front; gloss/no-tag, no-audio, and Frequency-legacy shapes keep the sentence front | `tests/test_front_modes.py` — extracts the real resolver from the front template and runs 6 state harnesses in headless Chrome; skipped gracefully when Chrome is absent |
| Clean-environment pass, no forgotten files/deps | CI (`.github/workflows/verify.yml`) runs `./verify` |
| Every UI element collapses when its field is empty | `tests/test_templates.py` §10 — conditional-enclosure parser over Front/Back, `:has()` shell-guard checks, JS self-removal checks |

## The gate

`./verify` = the repository's complete mandatory **local** quality gate.
Side-effect free: it never touches Anki, never writes releases, never
commits. `finish.sh` step 0 delegates to it, so the gate and the release
pipeline can never disagree.

## Regression rule (inside the dev loop, not a separate phase)

```text
bug → diagnose → fix → add regression test → verify → commit
```

Every escaped bug earns a permanent test: compactor regressions → new
fixture/assertion; template/CSS regressions → a new `test_templates.py`
check, or a scoped back/CSS-only suite while the minimal-front branch skips
that file; layout regressions → new `test_layout.py` probe assertion.

## Dependencies

- `test_compactor.py`: `beautifulsoup4` + `soupsieve` (test-only).
- `test_templates.py`: stdlib only (node optional for JS syntax checks).
- `test_front_modes.py`: headless Chrome if present, else skip (pass).
- `test_mature_content.py`: headless Chrome if present, else skip (pass).
- `test_layout.py`: headless Chrome if present, else skip (pass).
- `test_yukei.py`: stdlib only; headless Chrome optional for browser probes.
