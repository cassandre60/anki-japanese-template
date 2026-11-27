#!/usr/bin/env python3
"""Back More-section lazy extended definition + prune behavior tests.

Extracts toggleMore / initSecondarySection / prepareDefinitionBoxes /
initDefinitionTruncation / pruneCompactedGlossary verbatim from the real
`Card 1 - Back.template.anki` and runs them in headless Chrome:

  1. lazy: template content stays out of the DOM until first More open,
     then stamps into its host exactly once.
  2. cleanup keeps More alive when the template is the only content.
  3. cleanup removes More + toggle when the section is truly empty.
  4. prune: fixture glossary compacts to the same visible text as CSS §6b
     (①② kept, ③+ hidden) while shrinking the live DOM.
  5. image-only definition survives empty-collapse and is marked
     media-only (regression: 餃子 folding-guide image was deleted).
  6. text definition keeps the normal truncation path.
  7. image-only secondary content keeps More alive.

Run directly:  python3 tests/test_back_more.py
Wired into ./verify alongside the other suites. Skipped gracefully
without Chrome.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACK = os.path.join(ROOT, "Card 1 - Back.template.anki")
CSS = os.path.join(ROOT, "Card 1 - Style.css")
FIXTURE = os.path.join(HERE, "fixtures", "yomitan_daijirin_daijisen.html")
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
    """Extract the window.* functions verbatim from the back template."""
    with open(BACK, encoding="utf-8") as f:
        back = f.read()
    funcs = {}
    for name in ("toggleMore", "showTagsBar", "hideTagsBar", "initSecondarySection", "pruneCompactedGlossary",
                 "hasVisualContent", "prepareDefinitionBoxes",
                 "initDefinitionTruncation"):
        m = re.search(r"window\.%s = function.*?^\s{4}\};" % name, back, re.S | re.M)
        if not m:
            raise RuntimeError(f"{name} not found in back template")
        funcs[name] = m.group(0)
    return funcs


def build_html(funcs, more_inner, def_inner=""):
    return f"""<!doctype html><html><head><meta charset="utf-8"></head><body>
<div class="card-wrapper back-card"><div class="card-container">
<div class="definition-box primary-definition">{def_inner}</div>
<div class="more-section" hidden>{more_inner}</div>
<button type="button" class="more-toggle" aria-expanded="false">More</button>
</div></div>
<script>
var report = {{}};
try {{
{funcs['toggleMore']}
{funcs['showTagsBar']}
{funcs['hideTagsBar']}
{funcs['initSecondarySection']}
{funcs['pruneCompactedGlossary']}
{funcs['hasVisualContent']}
{funcs['prepareDefinitionBoxes']}
{funcs['initDefinitionTruncation']}
window.initSecondarySection();
window.pruneCompactedGlossary();
window.initDefinitionTruncation();
var section = document.querySelector('.more-section');
var btn = document.querySelector('.more-toggle');
report.moreAlive = !!(section && section.parentNode);
report.btnAlive = !!(btn && btn.parentNode);
var host = document.querySelector('.extended-full');
report.hostKids = host ? host.childNodes.length : -1;
report.hostHidden = host ? host.hasAttribute('hidden') : null;
if (btn && report.moreAlive) window.toggleMore(btn);
var host2 = document.querySelector('.extended-full');
report.stamped = host2 ? host2.textContent : null;
report.tplGone = document.querySelector('template.extended-full-tpl') === null;
report.expanded = btn ? btn.getAttribute('aria-expanded') : null;
var def = document.querySelector('.primary-definition');
report.defAlive = !!(def && def.parentNode);
report.defMediaOnly = def ? def.classList.contains('is-media-only') : false;
report.defRole = def ? def.getAttribute('role') : null;
report.defTabindex = def ? def.getAttribute('tabindex') : null;
report.defText = def ? def.textContent : '';
report.defNodes = def ? def.querySelectorAll('*').length : -1;
if (btn && report.moreAlive) window.toggleMore(btn);
var stillEl = document.querySelector('.extended-full');
report.stillStamped = stillEl ? stillEl.textContent : null;
}} catch(e) {{ report.err = String(e && e.stack || e); }}
document.title = 'X' + JSON.stringify(report) + 'X';
</scr""" + "ipt></body></html>"


def render(html, size="412,892"):
    import json as _json
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "back.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        try:
            out = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu",
                 "--no-sandbox", "--hide-scrollbars",
                 f"--window-size={size}",
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
        return _json.loads(m.group(1))
    except ValueError:
        return None


def build_geometry_html(funcs, css):
    """Real stylesheet + a tall More section, so the reveal pushes the tag
    footer below the fold. Regression for issue #4: the old fixed panel
    overlapped the More toggle and clipped the page bottom."""
    filler = "<p>" + ("Long secondary context that pushes the tag footer below the fold. " * 80) + "</p>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>html, body {{ margin: 0; padding: 20px; }}</style>
<style>{css}</style></head><body class="card card1 nightMode">
<div class="card-wrapper back-card"><div class="card-container">
<div class="hero-header"><div class="hero-word-wrap"><div class="word-display">言葉</div></div></div>
<div class="definition-box primary-definition">definition text</div>
<div class="more-section" hidden>
<div class="html-content secondary-block">{filler}</div>
</div>
<button type="button" class="more-toggle" aria-expanded="false">
<span class="more-text">詳細</span> <span class="more-caret">▾</span></button>
<div class="shortcut-hints"><button type="button" class="shortcut-item"
data-shortcut="c"><kbd>C</kbd> 展開</button></div>
<div class="tags-source" hidden>tag-alpha tag-beta tag-gamma</div>
</div></div>
<script>
var report = {{}};
try {{
{funcs['toggleMore']}
{funcs['showTagsBar']}
{funcs['hideTagsBar']}
{funcs['initSecondarySection']}
var sec = document.querySelector('.more-section');
var btn = document.querySelector('.more-toggle');
var hints = document.querySelector('.shortcut-hints');
function box(el) {{
  var b = el.getBoundingClientRect();
  return {{ top: b.top, bottom: b.bottom, left: b.left, right: b.right }};
}}
function hit(el) {{
  var b = el.getBoundingClientRect();
  var n = document.elementFromPoint((b.left + b.right) / 2, (b.top + b.bottom) / 2);
  return !!(n && (n === el || el.contains(n)));
}}
function state() {{
  var bar = document.querySelector('.tags-bar');
  return {{
    hidden: sec.hidden,
    tagsBarVisible: !!bar,
    tagsBarOnBody: !!(bar && bar.parentNode === document.body),
    tagsBarCount: document.querySelectorAll('.tags-bar').length,
    panel: !!document.querySelector('.tags-panel')
  }};
}}
report.before = state();
window.toggleMore(btn);
var bar = document.querySelector('.tags-bar');
report.afterOpen = Object.assign(state(), {{
  barRect: bar ? box(bar) : null,
  toggleRect: box(btn), hintsRect: box(hints),
  barFixed: bar ? getComputedStyle(bar).position === 'fixed' : false,
  viewportH: window.innerHeight,
  noHOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  toggleHit: hit(btn), hintsHit: hit(hints)
}});
window.toggleMore(btn);
report.afterClose = state();
window.initSecondarySection();
window.initSecondarySection();
report.afterReinit = state();
window.toggleMore(btn);
report.afterReopen = Object.assign(state(), {{
  toggleHit: hit(btn), hintsHit: hit(hints)
}});
}} catch(e) {{ report.err = String(e && e.stack || e); }}
document.title = 'X' + JSON.stringify(report) + 'X';
</scr""" + "ipt></body></html>"


def main():
    if not CHROME:
        print("[SKIP] no headless Chrome found — back-more checks skipped")
        return 0
    funcs = load_functions()
    fixture = open(FIXTURE, encoding="utf-8").read()

    # Case 1: template + one text block → lazy stamp on open, kept section.
    more = ('<div class="html-content secondary-block">ctx</div>'
            '<div class="extended-def-wrapper"><div class="extended-def-header">x</div>'
            '<template class="extended-full-tpl"><div>LAZY-EXTENDED-MARKER</div></template>'
            '<div class="html-content secondary-block extended-full" data-lazy hidden></div></div>')
    r = render(build_html(funcs, more))
    check("lazy More: probe returned", r is not None)
    if r:
        check("lazy More: ran without errors", "err" not in r, r.get("err", ""))
        check("lazy More: host empty before open", r.get("hostKids") == 0, str(r))
        check("lazy More: stamped on first open", (r.get("stamped") or "").strip() == "LAZY-EXTENDED-MARKER", str(r))
        check("lazy More: template consumed + toggle opened",
              r.get("tplGone") is True and r.get("expanded") == "true", str(r))
        check("lazy More: second toggle keeps stamped content",
              (r.get("stillStamped") or "").strip() == "LAZY-EXTENDED-MARKER", str(r))

    # Case 2: template is the ONLY content → More survives cleanup.
    more_only = ('<div class="extended-def-wrapper"><div class="extended-def-header">x</div>'
                 '<template class="extended-full-tpl"><div>ONLY</div></template>'
                 '<div class="html-content secondary-block extended-full" data-lazy hidden></div></div>')
    r = render(build_html(funcs, more_only))
    check("template-only More: probe returned", r is not None)
    if r:
        check("template-only More: section + toggle survive", r.get("moreAlive") and r.get("btnAlive"), str(r))
        check("template-only More: stamps on open", (r.get("stamped") or "").strip() == "ONLY", str(r))

    # Case 3: truly empty section → More + toggle removed.
    r = render(build_html(funcs, '<div class="html-content secondary-block">   </div>'))
    check("empty More: probe returned", r is not None)
    if r:
        check("empty More: section + toggle self-remove",
              r.get("moreAlive") is False and r.get("btnAlive") is False, str(r))

    # Case 4: prune compacts the real fixture in a real browser.
    r = render(build_html(funcs, '<div class="html-content secondary-block">ctx</div>', fixture))
    check("prune: probe returned", r is not None)
    if r:
        check("prune: ran without errors", "err" not in r, r.get("err", ""))
        t = r.get("defText", "")
        check("prune: senses ①② kept", "水などを濁りのない状態にする" in t and "雑念を払って" in t, t[:120])
        check("prune: sense ③+ gone", "一つのことに注意を向ける" not in t, t[:120])
        check("prune: 2nd dictionary gone", "汲み置いて井戸水を" not in t, t[:120])
        check("prune: live DOM shrunk (< 612 nodes)", 0 < r.get("defNodes", 9999) < 612, str(r.get("defNodes")))

    # Case 5: image-only definition (餃子 folding guide) is content, not a
    # blank shell. Regression: textContent-only emptiness deleted the <img>.
    r = render(build_html(
        funcs,
        '<div class="html-content secondary-block">ctx</div>',
        '<img alt="餃子包法" src="fit.webp">'))
    check("image-only definition: probe returned", r is not None)
    if r:
        check("image-only definition: box survives", r.get("defAlive") is True, str(r))
        check("image-only definition: marked media-only", r.get("defMediaOnly") is True, str(r))
        check("image-only definition: text-expand affordance removed",
              r.get("defRole") is None and r.get("defTabindex") is None, str(r))

    # Case 6: text definition keeps the normal truncation path.
    r = render(build_html(
        funcs,
        '<div class="html-content secondary-block">ctx</div>',
        '<div>水などを濁りのない状態にする</div>'))
    check("text definition: probe returned", r is not None)
    if r:
        check("text definition: survives and is not media-only",
              r.get("defAlive") is True and r.get("defMediaOnly") is False, str(r))

    # Case 7: image-only secondary block is content too (More must survive).
    r = render(build_html(
        funcs,
        '<div class="html-content secondary-block"><img alt="" src="notes.webp"></div>'))
    check("image-only More block: probe returned", r is not None)
    if r:
        check("image-only More block: section + toggle survive",
              r.get("moreAlive") is True and r.get("btnAlive") is True, str(r))

    # Case 8: revealed tags bar geometry (issue #4/#5 regression).
    # Tags are shown as a fixed bar at the viewport bottom (on
    # document.body). The bar must not cover the C control or hint bar,
    # must not clip the page, and must be removed when More closes.
    with open(CSS, encoding="utf-8") as f:
        css = f.read()
    for size in ("1280,900", "412,892"):
        r = render(build_geometry_html(funcs, css), size)
        check(f"tags bar [{size}]: probe returned", r is not None)
        if not r:
            continue
        check(f"tags bar [{size}]: ran without errors", "err" not in r, r.get("err", ""))
        before = r.get("before", {})
        opened = r.get("afterOpen", {})
        closed = r.get("afterClose", {})
        reinit = r.get("afterReinit", {})
        reopened = r.get("afterReopen", {})
        vh = opened.get("viewportH") or 1
        check(f"tags bar [{size}]: hidden by default",
              before.get("tagsBarVisible") is False
              and before.get("panel") is False,
              str(r))
        check(f"tags bar [{size}]: reveal creates fixed bar on body (no old panel)",
              opened.get("tagsBarVisible") is True
              and opened.get("tagsBarOnBody") is True
              and opened.get("barFixed") is True
              and opened.get("panel") is False,
              str(r))
        check(f"tags bar [{size}]: bar sits at viewport bottom",
              opened.get("barRect") is not None
              and opened.get("barRect", {}).get("bottom", 0) >= vh - 2
              and opened.get("barRect", {}).get("bottom", 0) <= vh + 2,
              str(r))
        check(f"tags bar [{size}]: C control not covered by tags bar",
              opened.get("toggleRect", {}).get("top", 0) < (opened.get("barRect") or {}).get("top", 0)
              or opened.get("toggleRect", {}).get("top", 0) > vh,
              str(r))
        check(f"tags bar [{size}]: no horizontal overflow",
              opened.get("noHOverflow") is True,
              str(r))
        check(f"tags bar [{size}]: closing removes bar, no stale panel",
              closed.get("hidden") is True
              and closed.get("tagsBarVisible") is False
              and closed.get("panel") is False
              and closed.get("tagsBarCount") == 0,
              str(r))
        check(f"tags bar [{size}]: re-init leaves no bar behind",
              reinit.get("hidden") is True
              and reinit.get("panel") is False
              and reinit.get("tagsBarCount") == 0,
              str(r))
        check(f"tags bar [{size}]: reopening is clean (one bar)",
              reopened.get("tagsBarVisible") is True
              and reopened.get("panel") is False
              and reopened.get("tagsBarCount") == 1,
              str(r))

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
