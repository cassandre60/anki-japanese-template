#!/usr/bin/env python3
"""Template & CSS structural invariant tests.

Verifies the source files BEFORE they are pushed to Anki:
  - Front card never renders a furigana-bearing field (back-card-only rule)
  - Front is a pure retrieval surface (no tags/badges/metadata UI)
  - Listening is a hidden-by-default resolver: #listening tag or classic
    audio-only fields activate it; the sentence front is the fallback
  - Secondary back information is collapsed behind "More ▾"
  - Audio buttons carry aria-labels; controller is restart-only
  - Lightbox closes only on backdrop clicks (not on the enlarged image)
  - Anki template conditionals are balanced
  - CSS contains the accessibility/portability rules

Run directly:  python3 tests/test_templates.py
Wired into finish.sh step 0 alongside test_compactor.py.

Pure standard library — no dependencies.
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FRONT = os.path.join(ROOT, "Card 1 - Front.template.anki")
BACK = os.path.join(ROOT, "Card 1 - Back.template.anki")
CSS = os.path.join(ROOT, "Card 1 - Style.css")

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}")
    if cond:
        PASS += 1
    else:
        FAIL += 1


def main():
    front = open(FRONT, encoding="utf-8").read()
    back = open(BACK, encoding="utf-8").read()
    css = open(CSS, encoding="utf-8").read()

    # --- 1. Front card: furigana is back-card only ---
    furigana_fields = re.findall(r"\{\{[^}]*furigana[^\d}][^}]*\}\}", front)
    # allowed: none. Front uses plain Sentence/Expression only.
    check("Front renders no furigana: filter or furigana-bearing field",
          not furigana_fields and "Sentence (furigana)" not in front)
    check("Front renders the raw Sentence/Expression fields",
          "{{edit:Sentence}}" in front and "{{edit:Expression}}" in front)

    # --- 1b. Template scripts must be syntactically valid JavaScript ---
    # A SyntaxError in a card script kills the WHOLE script block: no
    # reveal, no mature mode, no listening resolver — the card hangs
    # hidden. Structural string checks cannot catch an unbalanced brace,
    # so parse every <script> body with node (skipped if node absent).
    node = shutil.which("node")
    if node:
        import tempfile as _tempfile
        for name, src in (("Front", front), ("Back", back)):
            bodies = re.findall(r"<script>(.*?)</script>", src, re.S)
            all_ok = True
            for body in bodies:
                with _tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tf:
                    tf.write(body)
                    tmp_path = tf.name
                try:
                    rc = subprocess.run([node, "--check", tmp_path],
                                        capture_output=True, timeout=30).returncode
                    if rc != 0:
                        all_ok = False
                finally:
                    os.unlink(tmp_path)
            check(f"{name}: all {len(bodies)} script block(s) parse as valid JavaScript", all_ok)
    else:
        print("[SKIP] node not found — template script syntax check skipped")

    # --- 2. Audio buttons: aria-labels present ---
    # Front is sentence-audio-only (1) + Back has word + sentence (2) = 3 total.
    # (Word-audio fallback was removed from the front listening mode.)
    buttons = re.findall(r"<button[^>]*circular-audio-btn[^>]*>", front + back)
    check(f"all {len(buttons)} audio buttons have aria-label",
          len(buttons) >= 3 and all("aria-label" in b for b in buttons))

    # --- 3. Audio controller: native-only (no HTML5 Audio path) ---
    for name, src in (("Front", front), ("Back", back)):
        check(f"{name}: no is-paused state remnants",
              "is-paused" not in src)
        check(f"{name}: resetAudioState defined",
              "window.resetAudioState = function" in src)
        check(f"{name}: native-only playback (no new Audio garbage-loads on AnkiDroid)",
              "new Audio(" not in src)
        check(f"{name}: delegates to Anki replay link",
              "nativeReplay.click()" in src)
        check(f"{name}: replay link resolved via wrapper scope (not nested in button)",
              "closest('.audio-btn-wrapper')" in src)
        check(f"{name}: re-tap debounce (native audio can't be stopped)",
              "window.currentActiveBtn === btn" in src)
        # restart-only: every click path goes through resetAudioState first
        check(f"{name}: playCircularAudio starts with resetAudioState",
              re.search(r"window\.playCircularAudio = function\(btn\) \{\s*(/\*.*?\*/\s*)*if \(window\.currentActiveBtn === btn\) return;\s*window\.resetAudioState\(\);", src, re.S) is not None)

    # --- 3b. Audio markup: valid + clickable on AnkiDroid ---
    for name, src in (("Front", front), ("Back", back)):
        check(f"{name}: replay source lives OUTSIDE the button (sibling span)",
              re.search(r"</button>\s*<span class=\"raw-audio-source\"", src) is not None)
        check(f"{name}: no display:none audio source (breaks .click() playback)",
              "raw-audio-source\" style=\"display:none" not in src)
        check(f"{name}: no div-inside-button (invalid HTML, breaks AnkiDroid taps)",
              '<div class="audio-btn-content">' not in src)
    check("CSS: raw-audio-source visually hidden but present (no display:none)",
          re.search(r"\.raw-audio-source\s*\{[^}]*position:\s*absolute", css) is not None
          and ".raw-audio-source" in css)

    # --- 2c. Cloze fallback: bold-less Sentence rebuilt from cloze trio ---
    check("Front: hidden cloze probe with plain prefix/body/suffix fields",
          'class="cloze-probe"' in front
          and "{{cloze-prefix}}" in front and "{{cloze-body}}" in front
          and "{{cloze-suffix}}" in front)
    check("Front: probe uses plain fields (no edit: filter, stays furigana-free)",
          "edit:cloze" not in front)
    check("Front: reconstruction only fires when sentence lacks bold",
          "querySelector('b, strong')" in front)
    check("Front: reconstruction requires the complete trio (no partial rebuild)",
          "clozePre && clozeMid && clozeSuf" in front)
    check("Front: rebuilt term uses <b> (inherits sentence-display styling)",
          "createElement('b')" in front)

    # --- 4. Lightbox: backdrop-only close ---
    check("lightbox closes only on backdrop click (e.target === overlay)",
          "if (e.target === overlay) closeOverlay()" in back)
    check("lightbox overlay has dialog semantics",
          "setAttribute('role', 'dialog')" in back and "setAttribute('aria-modal', 'true')" in back)
    check("lightbox clone preserves alt text", "img.alt" in back)

    # --- 5. Anki conditionals balanced ({{#field}} and {{^field}} both open) ---
    for name, src in (("Front", front), ("Back", back)):
        opens = len(re.findall(r"\{\{[#^][A-Za-z]", src))
        closes = len(re.findall(r"\{\{/[A-Za-z]", src))
        check(f"{name}: balanced field conditionals ({opens} open / {closes} close)",
              opens == closes)

    # --- 6. CSS invariants ---
    check("CSS: :focus-visible keyboard indicator present",
          ":focus-visible" in css)
    check("CSS: prefers-reduced-motion present",
          "prefers-reduced-motion: reduce" in css)
    check("CSS: content-driven card sizing (no forced viewport fill)",
          "min-height: 100vh" not in css and "min-height: 100dvh" not in css
          and "container-type: inline-size" in css)
    check("CSS: container-query media fallback for the context grid",
          re.search(r"@media \(min-width: 768px\)[\s\S]{0,200}\.context-grid", css) is not None)

    # --- 6b. Redesign: hierarchy with frequency visualizer ---
    check("Back: no sticky tags bar (tags are behavioral metadata)",
          "tags-container" not in back and "tags-list" not in back
          and "tag-pill" not in back)
    check("Back: frequency visualizer present",
          "frequency-badge" in back and "renderFrequencyIndicator" in back)
    check("CSS: frequency badge styling present",
          "frequency-badge" in css and "--freq-" in css)
    check("Back: secondary info is collapsed behind More by default",
          'class="more-section" hidden' in back
          and "more-toggle" in back)
    check("Back: More toggle has aria state + toggle behavior",
          'aria-expanded="false"' in back
          and "toggleMore" in back)
    check("Back: no retrieval-state label UI (content hierarchy replaces captions)",
          "retrieval-state" not in back and "__ajtFrontState" not in back)
    check("Front: no front-state store written",
          "__ajtFrontState" not in front)
    check("CSS: no retrieval-state styling remains",
          "retrieval-state" not in css)
    check("Back: keyboard F toggles full-card furigana (back only)",
          "furigana-mode" in back and "'f'" in back)
    check("Back: keyboard T reveals the translation",
          "'t'" in back and "translation-box" in back)
    check("CSS: full-card furigana mode rule exists",
          ".card-wrapper.furigana-mode ruby rt" in css)
    # --- 6c. Listening mode invariants ---
    check("Front: listening markup gated behind Definition/Extended/Frequency absence",
          re.search(r"\{\{\^Frequency\}\}[\s\S]*?\{\{#Sentence Audio\}\}\s*<div class=\"listening-view", front) is not None)
    check("Front: listening resolver checks for rendered listening view",
          "LISTENING RESOLVER" in front and ("querySelector('.listening-view')" in front or "querySelector('.classic-listening-view')" in front))
    check("Front: sentence front is the universal fallback",
          re.search(r"\{\{#Definition\}\}\s*<div class=\"sentence-display\">", front) is not None)
    check("CSS: listening-view flex styled",
          ".listening-view" in css and re.search(r"\.listening-view\s*\{[^}]*display:\s*flex", css) is not None)
    check("CSS: listening mode hides the sentence/word fronts",
          ".card-wrapper.listening-mode .sentence-display" in css)

    # --- 6d. Listening audio source + Policy B (Features 2, 3) ---
    # The tag-listening-view delegates to Anki's answer-side audio (play:a:N /
    # playsound:a:N) to avoid Anki's C++/Python reviewer auto-playing audio on
    # every tagged normal card on load (which happens whenever [sound:...] is
    # in the front HTML regardless of CSS display:none).
    # On the back card, Word Audio is first (a:0) and Sentence Audio is second (a:1):
    # - Both exist: Sentence Audio is a:1 (label 文)
    # - Only Sentence Audio exists: Sentence Audio is a:0 (label 文)
    # - Only Word Audio exists: Word Audio is a:0 (label 言葉)
    tag_block = re.search(r'<!-- Behavioral tag probe.*?\{\{/Tags\}\}', front, re.S)
    check("Front: tag-listening-view block present",
          tag_block is not None)
    if tag_block:
        tag_src = tag_block.group(0)
        # Binds to Sentence Audio: plays a:1 when Word Audio is also present,
        # and a:0 when Word Audio is absent. Never plays Word Audio (a:0) when
        # Sentence Audio is present and labelled 文.
        check("Front: tag-listening-view plays Sentence Audio (a:1 when Word Audio also present)",
              "pycmd('play:a:1')" in tag_src
              and "playsound:a:1" in tag_src
              and "文" in tag_src)
        check("Front: tag-listening-view plays Sentence Audio (a:0 when Word Audio absent)",
              re.search(r'\{\{\^Word Audio\}\}[\s\S]*?文[\s\S]*?pycmd\(\'play:a:0\'\)', tag_src) is not None)
        check("Front: tag-listening-view falls back to Word Audio (a:0) with 言葉 label",
              re.search(r'\{\{\^Sentence Audio\}\}[\s\S]*?\{\{#Word Audio\}\}[\s\S]*?言葉[\s\S]*?pycmd\(\'play:a:0\'\)', tag_src) is not None)
        # CRITICAL: raw {{Sentence Audio}} must NOT appear inside {{#Tags}} on
        # front — otherwise Anki auto-plays audio on every tagged normal card.
        check("Front: no raw audio fields inside {{#Tags}} (prevents auto-play on normal cards)",
              re.search(r'\{\{#Tags\}\}[\s\S]*?\{\{Sentence Audio\}\}[\s\S]*?\{\{/Tags\}\}', front) is None
              and re.search(r'\{\{#Tags\}\}[\s\S]*?\{\{Word Audio\}\}[\s\S]*?\{\{/Tags\}\}', front) is None)
    check("Front: Policy B — #listening without usable audio falls back to sentence front",
          "hasUsableAudio" in front and "Policy B" in front)
    check("Front: exactly-one-listening-button cleanup removes dead/duplicate views",
          "Dead/duplicate view cleanup" in front
          and "container.querySelectorAll('.listening-view').forEach" in front)
    check("Front: last-resort pycmd fallback is documented (not the primary path)",
          "Last-resort fallback" in front)

    # --- 6e. R shortcut is Anki-owned, never template-owned (Feature 1) ---
    check("Back: R shortcut hint removed from shortcut UI (Anki-owned)",
          '<kbd>R</kbd>' not in back)
    check("Back: custom template shortcuts are Z, X, C only",
          all(k in back for k in ['<kbd>Z</kbd>', '<kbd>X</kbd>', '<kbd>C</kbd>']))

    # --- 6e2. Shortcut hints are clickable controls, not inert text ---
    hints = re.search(r'<div class="shortcut-hints".*?</div>\s*\n', back, re.S)
    check("Back: shortcut hint bar present", hints is not None)
    if hints:
        hints_src = hints.group(0)
        check("Back: every shortcut hint is a button carrying data-shortcut",
              len(re.findall(r'<button[^>]*class="shortcut-item"[^>]*data-shortcut="[a-z]"',
                             hints_src)) == 3
              and all(f'data-shortcut="{k}"' in hints_src for k in "zxc"))
        check("Back: hint bar exposes group semantics", 'role="group"' in hints_src)
    check("Back: one shared action table serves keys AND hint clicks",
          "window.applyShortcut = function" in back
          and re.search(r"keydown[\s\S]{0,400}?applyShortcut\(e\.key\)", back) is not None
          and re.search(r"closest\('\.shortcut-item'\)[\s\S]{0,300}?applyShortcut\(", back) is not None)
    check("Back: hint clicks never bind R (Anki-owned)",
          re.search(r"data-shortcut=\"r\"", back, re.I) is None)
    check("CSS: clickable shortcut hints keep button chrome reset + affordance",
          re.search(r"\.shortcut-item\s*\{[^}]*cursor:\s*pointer", css) is not None
          and re.search(r"\.shortcut-item:hover", css) is not None
          and re.search(r"\.shortcut-item:focus-visible", css) is not None)

    # --- 6f. Audio terminology: playback indicator, not progress ring (Feature 4) ---
    check("Front: ring described as playback indicator (not true progress)",
          "playback indicator" in front.lower())
    check("CSS: ring described as playback indicator",
          "playback indicator" in css.lower())

    # --- 7. Font sizing source-of-truth ---
    check("Back: no JS font-scaler overriding CSS (inline fontSize ban)",
          "el.style.fontSize" not in back and "autoScaleBackSentence" not in back)
    check("CSS: .sentence-japanese clamp() is the sizing authority",
          re.search(r"\.sentence-japanese\s*\{[^}]*font-size:\s*clamp\(", css) is not None)

    # --- 8. (removed) Frequency visualizer retired with the minimal redesign ---

    # --- 8b. Mature Word Mode invariants (interval-gated front) ---
    check("Front: LONG_INTERVAL_DAYS threshold constant defined",
          re.search(r"const\s+LONG_INTERVAL_DAYS\s*=\s*365", front) is not None
          and "interval >= LONG_INTERVAL_DAYS" in front)
    check("Front: threshold not hard-coded elsewhere (single const definition)",
          len(re.findall(r"LONG_INTERVAL_DAYS\s*=\s*365", front)) == 1
          and len(re.findall(r">=\s*365", front)) == 0)
    check("Front: word probe div present with Expression",
          re.search(r'class="front-word-display">\s*\{\{edit:Expression\}\}', front) is not None)
    check("Front: no guiCurrentCard call anywhere (fallback-only word mode)",
          "'guiCurrentCard'" not in front
          and re.search(r"cardsInfo.*?interval", front, re.S) is not None)
    check("Front: word-mode interval via content search (findCards)",
          "findCards" in front and "content search" in front
          and "BROWSE-PREVIEWER CONTENT SEARCH" in front)
    check("Front: no nonexistent Anki-Connect actions",
          "getCardsInfo" not in front)
    check("Front: no card-id-from-URL guess (no URLSearchParams)",
          "URLSearchParams" not in front)
    check("Front: no executable AnkiDroid JS API code remains",
          "AnkiDroidJS" not in front and "ankiGetCardInterval" not in front)
    check("Front: no bridge helpers / polling remain",
          "safeApiCall" not in front and "withBridgeTimeout" not in front
          and "parseDroidInterval" not in front
          and "bridgeAvailable" not in front and "waitForBridge" not in front
          and "apiKind" not in front
          and "signal:jsapi" not in front)
    check("Front: post helper UA-guards every AnkiConnect call (mobile rejects before fetch)",
          re.search(r"const post = \(action, params\) => \{[\s\S]*?/Android\|iPhone\|iPad\|iPod/i\.test\(ua\)", front) is not None
          and "AnkiConnect is desktop-only" in front)
    check("Front: QtWebEngine allowlist — fetch only from desktop Anki's engine",
          re.search(r"const post = \(action, params\) => \{[\s\S]*?/QtWebEngine/i\.test\(ua\)", front) is not None
          and "requires desktop QtWebEngine" in front)
    check("Front: mobile never reaches a fetch (guard inside post, before fetch)",
          re.search(r"const post = \(action, params\) => \{[\s\S]*?fetch\('http://127\.0\.0\.1:8765'", front, re.S) is not None)
    check("Front: retrieval remains platform-exclusive (DESKTOP-ONLY marker)",
          "DESKTOP-ONLY" in front)
    check("Front: retrieval latency is measured and logged",
          "performance.now" in front and "elapsedMs" in front
          and "[Mature Word Mode] source=" in front)
    check("Front: safety reveal cap bounds worst-case hidden time",
          "setTimeout(reveal, 1200)" in front)
    check("Front: AnkiConnect calls fail fast when Anki is wedged (safe sentence fallback)",
          "AnkiConnect timeout" in front and ", 500)" in front)
    check("Front: temporary toast diagnostic removed (no TEMP-DIAG remnants)",
          "TEMP-DIAG" not in front and "ankiShowToast" not in front)
    check("Front: on-card debug diagnostic present (mwm-debug)",
          "DEBUG_MATURE_MODE" in front and "mwm-debug" in front
          and "Mature mode: " in front)
    check("Front: skips ALL retrieval on listening cards (no needless JS-API calls)",
          "isListening" in front)
    check("Front: anti-flash visibility gate present",
          'style="visibility: hidden;"' in front
          and "container.style.visibility = 'visible'" in front)
    check("Front: word-mode class applied to card wrapper",
          "wrapper.classList.toggle('word-mode'" in front)
    check("Front: retrieval failure falls back to sentence (try/catch + typed interval check)",
          "catch" in front and "typeof interval === 'number'" in front)
    check("CSS: word-mode display rules present",
          ".card-wrapper.word-mode .sentence-display" in css
          and ".card-wrapper.word-mode .front-word-display" in css)
    check("CSS: word mode leaves listening view untouched",
          ".listening-view" not in css.split("5b. MATURE-CARD WORD MODE")[1].split("6. BACK CARD")[0]
          if "5b. MATURE-CARD WORD MODE" in css else False)
    check("Front: no \"note:\" search clause ({{Type}} is scheduling type, not model)",
          "NOTE_TYPE" not in front
          and re.search(r"findCards[^\n]*note:", front) is None
          and 'escQuery(NOTE_TYPE)' not in front)

    # --- 8c. Mature content-search invariants (fallback-only word mode) ---
    # Content search is the ONLY retrieval path (guiCurrentCard removed).
    # It must:
    # - NEVER pick candidate 0 blindly (matches[0] is banned)
    # - Use Sentence then cloze-body as discriminators
    # - Fail safely to sentence mode when ambiguity remains
    check("Front: content search never picks candidate 0 (matches[0] banned)",
          "matches[0]" not in front
          and re.search(r"candidates\[0\]", front) is not None)  # only after discriminators narrow to 1
    check("Front: content search uses Sentence discriminator",
          "Discriminator 1: Sentence" in front)
    check("Front: content search uses cloze-body discriminator",
          "Discriminator 2: cloze-body" in front)
    check("Front: content search fails safely on ambiguity (sentence fallback)",
          "content-search-ambiguous" in front
          and "sentence fallback" in front)
    check("Front: content search uses exact-card resolution (length === 1)",
          "candidates.length === 1" in front)

    # --- 10. Empty-field collapse (QUALITY.md: no UI survives an empty field) ---
    # 10a. Static proof over the raw templates (comments/scripts stripped):
    # every rendered field lives inside an Anki conditional, except the
    # documented allowlist (attribute / hidden probe / gated probe).
    TOKEN = re.compile(r"\{\{\s*([#^/]?)\s*([^}]*?)\s*\}\}")
    ALLOW_BARE = {
        ("Front", "cloze-prefix"), ("Front", "cloze-body"), ("Front", "cloze-suffix"),  # hidden probe
        ("Front", "Expression"),  # front-word-display: display:none default, word-mode gate only (§8b)
    }
    bare = []
    for name, src in (("Front", front), ("Back", back)):
        clean = re.sub(r"<!--.*?-->", "", src, flags=re.S)
        clean = re.sub(r"<script.*?</script>", "", clean, flags=re.S)
        stack = []
        for m in TOKEN.finditer(clean):
            sig, body = m.group(1), m.group(2).strip()
            if sig in ("#", "^"):
                stack.append(body)
            elif sig == "/":
                if stack:
                    stack.pop()
            elif body:
                field = body.split(":")[-1].strip()
                if not stack and (name, field) not in ALLOW_BARE:
                    bare.append(f"{name}:{{{{{body}}}}}")
    check("every rendered field is conditional (or allowlisted)" + (f" — bare: {bare}" if bare else ""),
          not bare)

    # 10b. Unconditional shells collapse when all conditional children absent.
    check("CSS: empty .audio-row collapses (no button => gone)",
          re.search(r"\.audio-row:not\(:has\(\.circular-audio-btn\)\)\s*\{\s*display:\s*none", css) is not None)
    check("CSS: empty .context-grid collapses (no sentence/context/picture => gone)",
          re.search(r"\.context-grid:not\(:has\([^)]+\)\)\s*\{\s*display:\s*none", css) is not None)
    check("CSS: empty .context-main collapses (no sentence/context => gone)",
          re.search(r"\.context-main:not\(:has\([^)]+\)\)\s*\{\s*display:\s*none", css) is not None)
    check("CSS: empty .hero-header collapses (no word/meta => gone)",
          re.search(r"\.hero-header:not\(:has\([^)]+\)\)\s*\{\s*display:\s*none", css) is not None)
    check("Back: hero-header splits meta left/right around a centered word",
          'class="hero-header"' in back
          and 'class="hero-side hero-side-left"' in back
          and 'class="hero-side hero-side-right"' in back
          and back.index('hero-side-left') < back.index('hero-word-wrap') < back.index('hero-side-right')
          and back.index('{{#Frequency}}') < back.index('hero-word-wrap')
          and back.index('{{#Word Audio}}') < back.index('hero-word-wrap')
          and back.index('hero-word-wrap') < back.index('{{#Pitch Accent}}')
          and back.index('hero-word-wrap') < back.index('{{#Sentence Audio}}'))
    check("CSS: hero-header is a 3-column grid (left | word | right)",
          re.search(r"\.hero-header\s*\{[^}]*display:\s*grid", css) is not None
          and '"left word right"' in css)
    check("CSS: hero sides hug the word (end/start), narrow stacks word on top",
          re.search(r"\.hero-side-left\s*\{[^}]*justify-content:\s*flex-end", css) is not None
          and re.search(r"\.hero-side-right\s*\{[^}]*justify-content:\s*flex-start", css) is not None
          and '"word word"' in css)
    check("CSS: hero word never forces horizontal overflow (min-width + anywhere wrap)",
          re.search(r"\.hero-word-wrap\s*\{[^}]*min-width:\s*0", css) is not None
          and re.search(r"\.word-display\s*\{[^}]*overflow-wrap:\s*anywhere", css) is not None)
    check("CSS: picture fills the parallel row (generous desktop cap, compact mobile cap)",
          "max-height: 44vh" in css
          and "max-height: clamp(24vh, 22vmin, 32vh)" in css
          and "min(46vw, 640px)" in css)
    check("Back: stylized separators before AND after the definition",
          back.count('class="card-separator"') == 2
          and back.index('class="card-separator"') < back.index('primary-definition'))
    check("CSS: context-grid row is top-anchored in both container + fallback rules",
          len(re.findall(r"\.context-grid:has\(\.context-picture\)\s*\{[^}]*align-items:\s*flex-start", css)) == 2
          and len(re.findall(r"\.context-grid:has\(\.context-picture\)\s*\{[^}]*align-items:\s*center", css)) == 0)
    check("Back: More section + toggle self-remove when secondary content is absent",
          "btn.remove()" in back and "section.remove()" in back)

    # 10c. Degenerate content removes itself instead of leaving chrome behind.
    check("Back: blank definition box is removed (no bordered void)",
          "box.remove()" in back)
    check("Front: blank sentence block is removed after cloze fixup",
          "sd.remove()" in front)

    # --- 9. Sync tooling invariants ---
    sync = open(os.path.join(ROOT, "sync_to_anki.py"), encoding="utf-8").read()
    check("sync_to_anki.py: zero third-party imports (standard lib only)",
          "import requests" not in sync and "import urllib.request" in sync)
    check("sync_to_anki.py: microsecond backup timestamps",
          "%H%M%S-%f" in sync)
    finish = open(os.path.join(ROOT, "finish.sh"), encoding="utf-8").read()
    check("finish.sh: no-op run cannot publish a release",
          "Nothing to push or release" in finish)
    # Deterministic release ordering: push main BEFORE gh release create so
    # the tag points at the exact pushed commit (--target main).
    # Strip comments to check actual command order.
    finish_code = re.sub(r"^\s*#[^\n]*\n", "", finish, flags=re.M)
    finish_code = re.sub(r"^\s*#[^\n]*$", "", finish_code, flags=re.M)
    check("finish.sh: push main before gh release create (--target main)",
          "git push origin main" in finish_code
          and "gh release create" in finish_code
          and finish_code.index("git push origin main") < finish_code.index("gh release create")
          and "--target main" in finish_code)
    check("finish.sh: fetches the remote tag after release creation",
          finish_code.index("gh release create") < finish_code.rindex("git fetch origin \"refs/tags/*:refs/tags/*\""))
    check("finish.sh: verify runs before version stamp (step 0 before step 1)",
          finish.index("./verify") < finish.index("NEW_TAG="))

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
