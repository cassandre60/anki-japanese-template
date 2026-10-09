#!/usr/bin/env python3
"""Clickable shortcut-hint behavioral tests.

The back card's hint bar (`Z 振仮名` / `X 訳` / `C 展開`) is not decoration:
each hint is a control that applies exactly what its key applies. This suite
extracts `applyShortcut` / `initCardShortcuts` / `toggleMore` /
`expandDefinition` verbatim from the real `Card 1 - Back.template.anki` and
runs them in headless Chrome against a back-card-shaped harness:

  1. click Z hint  -> `.furigana-mode` on (and off again)
  2. click X hint  -> translation revealed / hidden again
  3. click C hint  -> More opens + definition expands; click again closes
  4. click on the inner <kbd> still applies (closest-based delegation)
  5. keyboard still works (Z/X/C) — the click path is additive, never a
     replacement for the key path
  6. C click never touches the translation (shortcuts stay isolated)
  7. an unbound key does nothing and never throws

Run directly:  python3 tests/test_shortcut_clicks.py
Wired into ./verify alongside the other suites. Skipped gracefully
without Chrome.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACK = os.path.join(ROOT, "Card 1 - Back.template.anki")
CHROME = shutil.which("google-chrome-stable") or shutil.which("chromium")

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f" ({detail})" if detail and not cond else ""))
    if cond:
        PASS += 1
    else:
        FAIL += 1


def load_functions():
    """Extract the shortcut action functions verbatim from the back template.

    Returns (funcs, missing): a missing function is a FAIL, not a crash —
    the whole point is that a template without the shared action entry point
    must fail this suite loudly and legibly.
    """
    with open(BACK, encoding="utf-8") as f:
        back = f.read()
    funcs = {}
    missing = []
    for name in ("toggleMore", "expandDefinition", "applyShortcut",
                 "initCardShortcuts"):
        m = re.search(r"window\.%s = function.*?^\s{4}\};" % name, back, re.S | re.M)
        if not m:
            missing.append(name)
        else:
            funcs[name] = m.group(0)
    return funcs, missing


# The real hint-bar markup, lifted from the back template so the harness can
# never drift from what ships (a <span> hint would make these cases vacuous).
def load_hint_markup():
    with open(BACK, encoding="utf-8") as f:
        back = f.read()
    m = re.search(r'<div class="shortcut-hints".*?</div>', back, re.S)
    if not m:
        raise RuntimeError("shortcut-hints markup not found in back template")
    return m.group(0)


def build_html(funcs, hints, with_translation=True, with_more=True):
    translation = (
        '<div class="translation-box" role="button" tabindex="0" aria-expanded="false">'
        '<div class="translation-hint">訳 ▾</div>'
        '<div class="translation-text">To clear one\'s mind.</div></div>'
    ) if with_translation else ""
    more = (
        '<div class="more-section" hidden>'
        '<div class="html-content secondary-block">extra context</div>'
        '</div>'
        '<button type="button" class="more-toggle" aria-expanded="false">'
        '<span class="more-text">詳細</span> <span class="more-caret">▾</span></button>'
    ) if with_more else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"></head><body>
<div class="card-wrapper back-card"><div class="card-container">
<div class="sentence-display">心を澄ませて、<ruby>音楽<rt>おんがく</rt></ruby>を聴く。</div>
<div class="definition-box primary-definition">Short definition.</div>
{translation}
{more}
{hints}
</div></div>
<script>
var report = {{}};
function press(key) {{
  document.dispatchEvent(new KeyboardEvent('keydown', {{key: key, bubbles: true}}));
}}
function tap(sel) {{
  var el = document.querySelector(sel);
  if (!el) return false;
  el.click();
  return true;
}}
function hintEl(key) {{
  return document.querySelector('.shortcut-item[data-shortcut="' + key + '"]');
}}
function state() {{
  var wrapper = document.querySelector('.card-wrapper.back-card');
  var box = wrapper.querySelector('.translation-box');
  var btn = wrapper.querySelector('.more-toggle');
  var def = wrapper.querySelector('.primary-definition');
  var sec = wrapper.querySelector('.more-section');
  return {{
    furigana: wrapper.classList.contains('furigana-mode'),
    translation: box ? box.classList.contains('revealed') : null,
    translationAria: box ? box.getAttribute('aria-expanded') : null,
    moreOpen: btn ? btn.getAttribute('aria-expanded') : null,
    moreHidden: sec ? sec.hidden : null,
    defExpanded: def ? def.classList.contains('is-expanded') : null
  }};
}}
try {{
{funcs['toggleMore']}
{funcs['expandDefinition']}
{funcs['applyShortcut']}
{funcs['initCardShortcuts']}
window.initCardShortcuts();

/* 1. Z hint: toggles furigana on, then off. */
report.zClick = tap('.shortcut-item[data-shortcut="z"]');
report.zOn = state().furigana;
tap('.shortcut-item[data-shortcut="z"]');
report.zOff = state().furigana;

/* 4. Click landing on the inner <kbd> applies too (closest delegation). */
var kbd = hintEl('z').querySelector('kbd');
kbd.click();
report.kbdClick = state().furigana;
tap('.shortcut-item[data-shortcut="z"]');

/* 2. X hint: reveals then hides the translation, aria stays in sync. */
tap('.shortcut-item[data-shortcut="x"]');
report.xOn = state();
tap('.shortcut-item[data-shortcut="x"]');
report.xOff = state();

/* 3. C hint: opens More + expands the definition, then closes More. */
tap('.shortcut-item[data-shortcut="c"]');
report.cOn = state();
tap('.shortcut-item[data-shortcut="c"]');
report.cOff = state();

/* 6. C hint must not touch the translation (shortcuts stay isolated). */
tap('.shortcut-item[data-shortcut="c"]');
report.cTranslationUntouched = state().translation;
tap('.shortcut-item[data-shortcut="c"]');

/* 5. Keyboard path still works after the click path was added. */
press('z');
report.keyZ = state().furigana;
press('x');
report.keyX = state().translation;
press('c');
report.keyC = state().moreOpen;

/* 7. Unbound keys are inert and must not throw. */
press('q');
press('Enter');
report.afterUnknown = state();
}} catch(e) {{ report.err = String(e && e.stack || e); }}
document.title = 'X' + JSON.stringify(report) + 'X';
</scr""" + "ipt></body></html>"


def render(html):
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "back.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        try:
            out = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu",
                 "--no-sandbox", "--hide-scrollbars",
                 "--window-size=1440,900",
                 "--virtual-time-budget=1500",
                 "--dump-dom", f"file://{path}"],
                capture_output=True, text=True, timeout=60,
            ).stdout
        except subprocess.TimeoutExpired:
            return None
    m = re.search(r"<title>X(.*?)X</title>", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def main():
    if not CHROME:
        print("[SKIP] no headless Chrome found — shortcut-click checks skipped")
        return 0
    funcs, missing = load_functions()
    if missing:
        check("back template exposes a shared applyShortcut action table",
              False, f"missing: {', '.join(missing)}")
        print()
        print(f"{PASS} passed, {FAIL} failed")
        return 1
    hints = load_hint_markup()

    # The shipped hint bar must be clickable markup, not inert text.
    check("hint bar: items are buttons carrying data-shortcut",
          len(re.findall(r'<button[^>]*class="shortcut-item"', hints)) == 3
          and all(k in hints for k in ('data-shortcut="z"', 'data-shortcut="x"',
                                       'data-shortcut="c"')),
          hints[:200])
    check("hint bar: no R hint (Anki-owned)",
          "data-shortcut=\"r\"" not in hints.lower())

    r = render(build_html(funcs, hints))
    check("shortcut clicks: probe returned", r is not None)
    if r:
        check("shortcut clicks: ran without errors", "err" not in r, r.get("err", ""))
        check("Z hint: click applies furigana mode (on then off)",
              r.get("zOn") is True and r.get("zOff") is False, json.dumps(r))
        check("Z hint: click on the inner <kbd> applies too",
              r.get("kbdClick") is True, json.dumps(r))
        check("X hint: click reveals then hides the translation",
              r.get("xOn", {}).get("translation") is True
              and r.get("xOn", {}).get("translationAria") == "true"
              and r.get("xOff", {}).get("translation") is False
              and r.get("xOff", {}).get("translationAria") == "false",
              json.dumps(r))
        check("C hint: click opens More + expands the definition",
              r.get("cOn", {}).get("moreOpen") == "true"
              and r.get("cOn", {}).get("moreHidden") is False
              and r.get("cOn", {}).get("defExpanded") is True,
              json.dumps(r))
        check("C hint: second click closes More again",
              r.get("cOff", {}).get("moreOpen") == "false"
              and r.get("cOff", {}).get("moreHidden") is True,
              json.dumps(r))
        check("C hint: never touches the translation (isolated)",
              r.get("cTranslationUntouched") is False, json.dumps(r))
        check("keyboard shortcuts still work alongside the click hints",
              r.get("keyZ") is True and r.get("keyX") is True
              and r.get("keyC") == "true", json.dumps(r))
        check("unbound keys are inert (no throw, no state change)",
              r.get("afterUnknown", {}).get("furigana") is True
              and r.get("afterUnknown", {}).get("moreOpen") == "true",
              json.dumps(r))

    # Hint clicks must degrade safely when the card has no translation/More:
    # no exception, no half-applied state.
    r = render(build_html(funcs, hints, with_translation=False, with_more=False))
    check("bare card: probe returned", r is not None)
    if r:
        check("bare card: X/C hint clicks degrade without errors",
              "err" not in r, r.get("err", ""))
        check("bare card: Z hint still toggles furigana",
              r.get("zOn") is True, json.dumps(r))
        check("bare card: X click leaves no translation state behind",
              r.get("xOn", {}).get("translation") is None, json.dumps(r))
        check("bare card: C click leaves More untouched",
              r.get("cOn", {}).get("moreOpen") is None, json.dumps(r))

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
