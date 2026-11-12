# ADR 007 — Runner-built releases (headless apkg builder)

## Context

The release artifact (sample-deck apkg) was exported from the maintainer's
live Anki collection via Anki-Connect (`release_apkg.py`), which makes the
desktop the only machine able to produce a release. Two problems surfaced:

- Releases stall when the desktop's upstream network misbehaves
  (2026-11-12: a 5.8 MB release-asset upload repeatedly died on
  `uploads.githubusercontent.com` while all API calls and downloads were
  healthy).
- Every other repo the maintainer owns publishes releases from CI runners;
  this one cannot, because the sample deck content (10 cards, 5.8 MB of
  media) lives only in the live collection.

## Decision

1. **Sample content becomes repo content.** `fetch_sample_deck.py` derives
   `samples/notes.json` + `samples/fields.json` + `samples/media/` from the
   live collection via Anki-Connect — machine-derived, never hand-written
   (rule-0 spirit: derive, don't guess). `samples/fields.json` is the one
   committed field-list snapshot; tests validate it against the field
   references in the templates so it can never silently drift.
2. **Headless stdlib builder.** `build_sample_apkg.py` builds
   `dist/anki-japanese-template.apkg` with stdlib only (`sqlite3` +
   `zipfile`): legacy `collection.anki2` (schema 18), note type composed
   from the repo's `Card 1 - Front/Back.template.anki` +
   `Card 1 - Style.css` + the committed field list, notes/cards/media from
   `samples/`. The `anki` pip package is rejected: PRODUCT.md mandates
   stdlib-only tooling.
3. **CI publishes.** A release workflow (`release.yml`, tag push `v*`)
   runs `./verify`, builds the apkg, and publishes the GitHub release
   with the asset.
4. **finish.sh keeps the inherently-local parts.** verify → version stamp →
   `sync_to_anki.py` (with snapshots) → commit → push main → tag push.
   The maintainer import-validates a locally built apkg in a scratch
   profile before tagging.

This amends ADR 004: the publisher moves to CI and the artifact source
moves from the live collection to repo files. ADR 004's invariants are
unchanged: verify-first ordering, pre-sync snapshots, tag == pushed
commit, apkg ships as a Release asset never in the repo.

## Consequences

Releases no longer depend on the desktop's network; runners build and
publish them like any other app in the maintainer's portfolio. The repo
gains ~6 MB of committed sample media (already public via past release
assets). The builder's legacy-format output must be import-validated
against current Anki in a scratch profile; documented fallback if legacy
import is refused: also emit an uncompressed `collection.anki21` twin
(schema 21). `release_apkg.py`'s Anki-Connect export path is retired once
the builder + workflow are validated end-to-end.
