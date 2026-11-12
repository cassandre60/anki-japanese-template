# IMPLEMENTATION_PLAN.md — task graph + status

The graph is part of the plan (not a substitute): the graph says *what
depends on what*, the task entries say *what each node means*. This is a
task/slice graph, not a todo list (`Build frontend` would not qualify).

## Dependency graph

```text
                    ┌───────────────────┐
                    │ T1 fields bootstrap│
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    ↓                   ↓
            ┌───────────────┐   ┌───────────────┐
            │ T2 front modes │   │ T3 back grid  │
            └───────┬───────┘   └───────┬───────┘
                    │                   │
                    ↓                   ↓
            ┌───────────────┐   ┌───────────────┐
            │ T4 mature mode │   │ T5 compactor  │
            └───────┬───────┘   └───────┬───────┘
                    │                   │
                    └─────────┬─────────┘
                              ↓
                    ┌───────────────────┐
                    │ T6 audio/lightbox │
                    └─────────┬─────────┘
                              │
                              ↓
                    ┌───────────────────┐
                    │ T7 responsive/    │
                    │ themes/density    │
                    └─────────┬─────────┘
                              │
                              ↓
                    ┌───────────────────┐
                    │ T8 verify gate +  │
                    │ regression tests  │
                    └─────────┬─────────┘
                              │
                              ↓
                    ┌───────────────────┐
                    │ T9 release loop   │
                    │ (sync/export/tag) │
                    └─────────┬─────────┘
                              │
                              ↓
                    ┌───────────────────┐
                    │ T10 methodology   │
                    │ refactor (this)   │
                    └─────────┬─────────┘
                              │
                              ↓
                    ┌───────────────────┐
                    │ T11 empty-field   │
                    │ collapse          │
                    └─────────┬─────────┘
                              │
                              ↓
                    ┌───────────────────┐
                    │ T12 minimal-       │
                    │ interface redesign │
                    └─────────┬─────────┘
                              │
                              ↓
                    ┌───────────────────┐
                    │ T13 editorial     │
                    │ redesign & polish │
                    └───────────────────┘
```

Dependencies: `T1 → {T2, T3} → {T4, T5} → T6 → T7 → T8 → T9 → T10 → T11 → T12 → T13`.
T2/T3 are parallelizable; T4 needs T2; T5 needs T3.

## Tasks

- **T1 — Field bootstrap.** `fetch_anki_fields.py` + gitignored
  `.anki_fields.json`; agents read exact names per session. Status: COMPLETE.
- **T2 — Front modes.** Sentence/Expression, listening button,
  Frequency-legacy path, fallback, cloze-trio rebuild. Status: COMPLETE.
- **T3 — Back grid.** Tags, word header, sentence/translation/context, side
  column, footer; DOM-reuse-safe controllers. Status: COMPLETE.
- **T4 — Mature Word Mode.** `LONG_INTERVAL_DAYS` gate, desktop-only
  AnkiConnect interval retrieval (mobile intentionally degrades to the
  sentence front), fallbacks, anti-flash reveal. Status: COMPLETE.
- **T5 — Definition Compactor + truncator.** CSS §6b structural scoping +
  §6c 3-line one-way expand. Status: COMPLETE.
- **T6 — Audio + lightbox.** Native delegation, debounce, sibling source;
  backdrop/`Escape` close. Status: COMPLETE.
- **T7 — Responsive/themes/density.** Clamps, container queries + fallback,
  zero-reflow ruby, Tokyo Night / Aki Paper, backdrop, reduced motion.
  Status: COMPLETE.
- **T8 — Verify gate + regression tests.** `verify`, `test_compactor.py`,
  `test_templates.py`, `test_layout.py`, CI. Status: COMPLETE (this refactor
  introduces `verify` + CI; suites pre-exist).
- **T9 — Release loop.** `sync_to_anki.py` (pre-sync snapshots),
  `release_apkg.py` (`exportPackage`), `finish.sh` one-command flow, apkg as
  Release asset only. Status: COMPLETE.
- **T10 — Methodology refactor.** Adopt PRODUCT/MVP/ARCHITECTURE/QUALITY/
  TEST_STRATEGY/PLAN + slim AGENTS.md + `verify`/CI without changing card
  behavior. Status: COMPLETE (`./verify` 129/129 green; released with this
  commit).
- **T11 — Empty-field collapse.** QUALITY rule + `:has()` shell guards +
  degenerate-content self-removal + enclosure parser test (§10). Turns the
  standing conditional coverage into a total, mechanically enforced
  guarantee. Status: COMPLETE (`./verify` 135/135 green; released with this
  commit).
- **T12 — Minimal-interface redesign.** Front = pure retrieval surface
  (hidden behavioral probes; listening as a hidden-by-default resolver:
  classic audio-only fields OR `#listening` tag; sentence front as the
  universal fallback). Back = typography hierarchy (word → pitch quiet →
  compacted meaning → context grid sentence+picture → secondary collapsed
  behind `More ▾`), discreet Context/Word/Listening state label,
  `F` full-card furigana + `T` translation shortcuts, tags/frequency
  badges removed (tags are behavioral metadata). Bug fixes: `{{Type}}`/
  `note:` search clause removed (wrong value), mobile `.word-meta-row`
  specificity, JS syntax gate added after an unbalanced-brace regression
  was caught by visual QA. Status: COMPLETE (`./verify` 168/168 green).
- **T13 — Editorial redesign & aesthetic polish.** Visual transformation from
  sterile dashboard to refined Japanese editorial reading interface. Removal of
  retrieval-state UI (`.retrieval-state`, "Context"/"Word"/"Listening") in favor
  of pure content hierarchy. Refined typography scale: restrained hero headword
  `clamp()`, editorial definition with no harsh dividing lines or boxes,
  quiet audio affordances (34px/30px buttons with subtle borders), and an
  asymmetric context grid balancing the Japanese sentence against intentional
  media proportions. Fixed empty-shell collapse bug for `.context-grid` and
  `.context-main`. Verified across 10 visual regression scenarios.
  Status: COMPLETE.
- **T14 — Listening Policy B + audio source fix + mature exact-card.**
  Listening Policy B: `#listening` activates the listening front only when
  usable audio exists (`hasUsableAudio` on `.raw-audio-source`); `#listening`
  + no audio falls back to the normal sentence front. Dead/duplicate views
  removed so exactly one listening button is ever visible. Listening audio
  source fix: the tag-listening-view binds to the actual `{{Sentence Audio}}`
  field (label 文), falling back to `{{Word Audio}}` (label 言葉) — never the
  hardcoded `play:a:0` (which plays the first audio field = Word Audio on
  listening cards). Mature exact-card: content-search fallback uses Sentence
  then cloze-body discriminators, never picks candidate 0, fails safely on
  ambiguity. R shortcut is Anki-owned (removed from the back's shortcut UI).
  Audio terminology: "progress ring" → "playback indicator". finish.sh
  ordering: push main before `gh release create --target main`. Tests:
  `test_front_modes.py` (8 cases), `test_mature_content.py` (6 cases),
  structural invariants in `test_templates.py` (§§6d–6f, 8c, 9). Docs audit
  across all methodology files. Status: COMPLETE.

- **T15 — Hero single-row density (R2).** Back `hero-header`: word + freq/
  pitch/audio share one flex row on wide screens (container + media fallback),
  tight stacked column on phones; vertical rhythm tightened (`--gap-section`,
  definition/separator/context gaps, quieter shortcut hints); picture fills the
  parallel row (44vh / 46vw-640px desktop, compact mobile cap unchanged).
  Empty-collapse + hierarchy + touch targets preserved; layout-probe proof in
  `test_layout.py` (shared-row desktop, stacked mobile), structural guards in
  `test_templates.py`. Status: COMPLETE.

- **T16 — Yūkei photo band + Picture consolidation (ADR 005/006).** Back-only
  compact scenic band keeps the ADR 005 illustrated fallback when `Picture` is
  empty; populated cards render one CSS-treated photo and reuse the existing
  lightbox. The old inline context thumbnail is removed while its CSS remains
  as a deliberate compatibility pass. Added `tests/test_yukei.py` so the
  back/CSS contract remains enforced during the minimal-front isolation branch.
  Status: COMPLETE (`./verify` green; desktop/mobile headless visual review on
  real Anki media covered both themes, click/Enter, both close paths, and
  reduced motion).

- **T17 — Front restoration (v1.8.52).** Main carried the 15-line minimal-front
  isolation stub from v1.8.35 while the spec corpus described mature/listening
  behavior living only in git history. Restored the fixed full front
  (`79743b7`: no jsapi, fallback-only content search, Policy B) and re-enabled
  `test_templates` / `test_front_modes` / `test_mature_content` in `verify`
  (291/291 green, zero fallout). Field-verified by maintainer on desktop +
  AnkiDroid (2026-09-26).

- **T18 — Runner-built releases (ADR 007).** Sample deck (11 notes + media)
  as repo files (`fetch_sample_deck.py` → `samples/`, derived from the live
  collection — never hand-written), committed field snapshot with per-field
  font/size/description validated against template references, stdlib
  headless builder (`build_sample_apkg.py`: schema-11 legacy package,
  sha-derived ids, content-hash guids, version-encoded mtimes, byte-identical
  rebuilds; 36-check suite + `--check` wired into `./verify`),
  `release.yml` (tag push → verify → build → publish), `finish.sh`
  re-scoped to verify → stamp → sync → commit → push main → tag
  (publishing is CI-owned; no local artifact build — `./verify` already
  builds and validates the apkg, and the scratch-profile import check is a
  one-time gate for the first CI release; §9 contract tests updated).
  Status: IN PROGRESS
  — remaining: maintainer import-validates a built apkg in a scratch
  profile, then the first tag fires the CI release end-to-end;
  `release_apkg.py` retired after that.

## Roadmap (evolution loop input, not committed scope)

- R1: extra compactor fixtures if Yomitan markup drifts.
- R2: further density tuning only with layout-probe proof.
- R3: new ADRs only for decisions with alternatives + consequences.

## State updates

Mark a task COMPLETE only after targeted checks + `./verify` + (for
template/CSS changes) the `finish.sh` release run. Update technical docs
only when something actually changed — no churn.
