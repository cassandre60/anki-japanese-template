# 🎴 Japanese Anki Note Template (Ergonomic & Responsive)

A modern, ultra-compact Japanese sentence-mining note type for Anki. Built for dense, information-efficient review on **Desktop (Arch Linux, Qt6)** and **Mobile (AnkiDroid, small screens)**.

---

## 🎥 Demo

[Screencast_20260903_034628.webm](https://github.com/user-attachments/assets/c3021cdb-7cfd-4cb1-b1a7-ff52a990e305)

---

## ✨ Features

- **🌙 Dual themes** — Tokyo Night dark (default) and Aki Paper light, following Anki's Night Mode.
- **🔢 Minimal by design** — every visible element must justify its screen space. The front is a pure retrieval surface (just the Japanese); the back is a quiet reading interface: target → reading → meaning → context, with secondary info collapsed behind `More ▾`. Anki is the SRS — no badges, dashboards, or grading UI.
- **📱 Fluid responsive layout** — `clamp()` sizing with no breakpoint jumps; a compact Yūkei scenic band spans the card top on desktop and phones, with full-width sentence context below. Cards size to their content (no forced viewport fill).
- **🔤 Zero-reflow furigana** — hidden by default, revealed on hover (desktop) / tap (mobile); **`F`** pins full-card furigana on the back. Nothing ever shifts.
- **🔊 Native audio** — `文` / `言葉` buttons delegate to Anki's replay link (never HTML5 audio), with re-tap debounce so audio can't overlap on AnkiDroid. The ring is a playback indicator (a decorative play-pulse), not true progress. **`R`** is Anki's own shortcut (native replay) — the template never adds it. Custom template shortcuts: `Z` (furigana), `X` (translation), `C` (expanded-info).
- **👁️ On-demand secondary info** — `T`/`X` reveals the translation; `More ▾` exposes the full Yomitan definition, extra context, kanji and general notes. `C` toggles expanded-info. Quiet by default.
- **🖼️ Lightbox** — tap the scenic photo (or press <kbd>Enter</kbd>) for the full-quality original; closes on backdrop click or <kbd>Escape</kbd>.
- **🏷️ Behavioral tags** — tags drive card behavior (e.g. `#listening` forces the listening front) and are never rendered as decoration.

---

## 🃏 Front Card Modes

The front contains ONLY the thing being tested — the sentence itself is the retrieval prompt.

| Situation | Front shows |
| :--- | :--- |
| Definition present | Sentence (or Expression if no Sentence) |
| No definitions, but `Frequency` set (legacy cards) | Usual sentence — never the audio button |
| No definitions, no Frequency, `Sentence Audio` set | Listening-mode audio button |
| Card tagged `#listening` | Listening-mode audio button — **only when usable audio exists** (Sentence Audio, or Word Audio fallback); without audio, falls back to the sentence front |
| Nothing available | Sentence / Expression fallback |
| Sentence has no bold term + cloze trio complete | Rebuilt `prefix + `<b>`body`</b>` + suffix`, styled identically to a Yomitan sentence |
| Review interval ≥ 365 days (desktop only) | Word only (Mature Word Mode, see below); Android keeps the sentence front |

**Cloze fallback** (jidoushio mobile exports): when `Sentence` lacks its `<b>` target word, JS rebuilds it from `cloze-prefix` / `cloze-body` / `cloze-suffix` — but only if all three are non-empty, otherwise the sentence is kept as-is.

**Mature Word Mode** (anti-overlearning, desktop only): old cards stop testing the word and start testing sentence recognition, so at `interval ≥ LONG_INTERVAL_DAYS` (default `365`, one constant in `Card 1 - Front.template.anki`) the front shows only the `Expression`. The interval is resolved at render time via AnkiConnect **content search** (`findCards` by Expression, then Sentence → cloze-body discriminators — reviewer and Browse previewer share the one identical fallback-only path; the live `guiCurrentCard` exact-card read was removed). On Android/mobile this mode is **intentionally disabled** and the ordinary sentence front is shown: the `post` helper UA-guards every AnkiConnect call before any fetch, because refused localhost requests can surface natively as false "Card Content Error: Failed to load" media warnings in the reviewer. The search **never picks candidate 0** blindly; if ambiguity remains, it fails safely to the sentence front. Any failure degrades to the normal sentence front; listening cards are never touched; an anti-flash gate keeps the card hidden until the decision is made (500 ms fetch timeout, 1200 ms reveal cap). The gate is deterministic and safe — it never depends on a single async path that can be throttled into a blank front.

**Listening semantics (Policy B)**: the audio button markup is gated on `Sentence Audio` and inert until a synchronous resolver confirms the listening condition — the classic audio-only field shape OR the `#listening` tag — **with usable audio**. The tag-listening-view binds to the actual `{{Sentence Audio}}` field (not the hardcoded `play:a:0` which plays the first audio field = Word Audio); Word Audio is the fallback, and the label matches what plays (文 for sentence, 言葉 for word). `#listening` + no usable audio falls back to the normal sentence front. The resolver removes every dead/duplicate view so exactly one listening sound button is ever visible. Every other card (and every failure path, including no-JS) keeps the sentence front.

---

## 📖 Back Card

Typography does the work — no dashboard chrome:

1. **Yūkei scenic band** — the card's `Picture` rendered as a compact CSS-treated photo, or an animated Fuji/cloud-sea fallback when empty. Photo cards open the full-quality original in the lightbox.
2. **Target + reading** — the headword with hover furigana, the hero element; pitch accent as quiet muted text.
3. **Primary meaning** — **Definition Compactor** (CSS §6b) trims the Yomitan glossary to the first dictionary, max 2 senses, no appendices; **Definition Truncator** (§6c) caps it at 3 lines with a fade + `▼`, click expands and stays open.
4. **Context** — the sentence (with hover furigana) spans the full reading width.
5. **Secondary info** — collapsed behind a quiet `More ▾`: translation (`T`), additional context, kanji notes, general notes, source, and the **full extended definition** (the compactor never touches it). Source stays hidden until `More ▾` / `C` reveals it. Content hierarchy communicates the card mode directly without labels.

---

## 🗂️ Fields

Fields are managed **exclusively inside the Anki UI** — the repo keeps no static list. For the live names + descriptions, run:

```bash
python3 fetch_anki_fields.py   # dumps gitignored .anki_fields.json
```

Current set (20): `Expression`, `Definition`, `Kanji Notes`, `Source`, `Sentence`, `Sentence (furigana)`, `Sentence Audio`, `Translation`, `Picture`, `context`, `Notes`, `Word Audio`, `Pitch Accent`, `furigana`, `reading`, `cloze-prefix`, `cloze-body`, `cloze-suffix`, `Frequency`, `Extended definition`. Yomitan-mining compatible.

---

## 🚀 Installation

**Option 1 — Quick install (recommended):** download `anki-japanese-template.apkg` from [Releases](https://github.com/mansourvery-hub/anki-japanese-template/releases), import via **File → Import**, then delete the sample cards (the note type is retained).

**Option 2 — Sync from source** (needs Anki + [Anki-Connect](https://ankiweb.net/shared/info/2055492159), Python 3 stdlib only):
```bash
git clone https://github.com/mansourvery-hub/anki-japanese-template.git
cd anki-japanese-template
python3 sync_to_anki.py    # snapshots live state to backups/, then pushes Front/Back/CSS
python3 release_apkg.py    # exports sample deck to dist/*.apkg
```

**Option 3 — Manual:** paste `Card 1 - Front.template.anki`, `Card 1 - Back.template.anki`, and `Card 1 - Style.css` into the card template editor (**Tools → Manage Note Types → Cards**).

---

## 🛠️ Project Structure

```
├── Card 1 - Front.template.anki   # Front HTML: modes, cloze fallback, Mature Word Mode
├── Card 1 - Back.template.anki    # Back HTML: header, definition, sentence, side column
├── Card 1 - Style.css             # Themes, layout, scenic band (§17), compactor, truncator
├── fetch_anki_fields.py           # Read-only dump of live Anki fields (see above)
├── sync_to_anki.py                # Push templates/CSS to Anki (pre-sync backup)
├── release_apkg.py                # Export sample deck to dist/*.apkg
├── verify                         # Local quality gate (tests only, no side effects)
├── finish.sh                      # One command: verify + sync + export + commit + push + release
├── PRODUCT.md / MVP.md            # Product intent / current scope
├── ARCHITECTURE.md + docs/adr/    # Technical structure / lasting decisions
├── QUALITY.md / TEST_STRATEGY.md  # Invariants / how they are verified
├── IMPLEMENTATION_PLAN.md         # Task graph + status
├── tests/                         # Compactor, templates, front modes, mature search, layout, Yūkei (run by ./verify)
├── chat_history/                  # Archived agent prompts
├── dist/                          # Exported .apkg (gitignored, GitHub Release asset)
├── backups/                       # Pre-sync Anki snapshots (gitignored)
├── AGENTS.md                      # Agent operating rules
└── README.md                      # This file
```

---

## 🔄 Development Workflow

Edit the local `.template.anki` / `.css` files (never inside Anki's UI), then run one command:

```bash
./finish.sh "scope: what changed"
# --local: sync + export + commit only · --minor: bump v1.x.0 · --prompt "text": archive prompt
```

This runs tests, syncs to Anki, exports the apkg, commits, pushes, and publishes a tagged release. `tests/` covers the compactor selectors, template invariants (furigana ban on front, audio/lightbox semantics, balanced conditionals, listening Policy B, R-is-Anki-owned, playback indicator terminology, finish.sh ordering), front-mode resolver behavior, mature content-search fallback (duplicate cards / ambiguity), Yūkei photo/fallback consolidation, and headless layout checks.

---

Built with Opencode and Gemini CLI. MIT License.

---

## Support

Building small, useful software — if this project saves you time, consider [buying me a coffee](https://buymeacoffee.com/cassandre60) to help keep it maintained.

<a href="https://buymeacoffee.com/cassandre60"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" width="150" alt="Buy Me A Coffee"></a>
