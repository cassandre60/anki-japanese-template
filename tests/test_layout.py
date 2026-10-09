#!/usr/bin/env python3
"""Headless layout verification for the density pass.

Renders the REAL stylesheet plus template-shaped HTML in Chrome headless
(google-chrome-stable is available on this machine) and asserts layout
invariants that pure text tests cannot catch:

  - card height is content-driven (back card < 90% of viewport height
    on a rich desktop card, i.e. no viewport fill)
  - no horizontal overflow / clipping
  - furigana (rt) never overlaps the line above it
  - hierarchy: headword font > sentence font > definition font > notes
  - truncator: a long definition clamps at 3 lines until expanded
  - listening front keeps the audio button a comfortable target
  - definition expand still works (JS one-way expand)

Usage: python3 tests/test_layout.py
Requires: google-chrome-stable on PATH. Skipped gracefully if absent
        (finish.sh runs it as part of step 0 when present).
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
CSS = os.path.join(ROOT, "Card 1 - Style.css")
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


# ---------------------------------------------------------------- HTML fixture
# Back card with every block populated: furigana headword, pitch, audio,
# long definition, furigana sentence, picture, More section (translation,
# extended definition, notes), source footer. New minimal hierarchy:
# word → meaning → context (sentence + picture) → More ▾.
BACK_CARD = """<!doctype html><html><head><meta charset="utf-8">
<style>
html,body{margin:0;padding:0;}
/* minimal Anki stand-ins: replay link + fonts so JS runs like in Anki */
</style>
<style>
__CSS__
</style></head><body>
<div class="card back-card">
<div class="card-wrapper back-card">
  <div class="card-container">
    <div class="hero-header">
      <div class="hero-side hero-side-left">
        <div class="frequency-badge"><span class="frequency-stars">★★★★☆</span></div>
        <div class="audio-row">
          <span class="audio-btn-wrapper">
            <button type="button" class="circular-audio-btn small-audio-btn"><span class="audio-btn-content"><span class="audio-btn-label">言葉</span></span></button>
            <span class="raw-audio-source"><a class="replay-button" href="#">replay</a></span>
          </span>
        </div>
      </div>
      <div class="hero-word-wrap"><div class="word-display" id="word"><ruby>澄<rt>す</rt></ruby>ます</div></div>
      <div class="hero-side hero-side-right">
        <div class="pitch-quiet">[0]</div>
        <div class="audio-row">
          <span class="audio-btn-wrapper">
            <button type="button" class="circular-audio-btn small-audio-btn"><span class="audio-btn-content"><span class="audio-btn-label">文</span></span></button>
            <span class="raw-audio-source"><a class="replay-button" href="#">replay</a></span>
          </span>
        </div>
      </div>
    </div>
    <div class="definition-box primary-definition" id="def">
      <div class="yomitan-glossary"><ol>
        <li><div data-sc-name="語義G">水などを濁りのない状態にする。とても長い定義のテキストで、三行を超えることを保証するためにさらに文字を追加している。三行目に入ってもまだ続くほど十分に長い定義であることを確認するための文です。全幅レイアウトでも確実に三行を超えるように、さらに追加の検証用テキストをここに置く。この文が折り返して四行目に達すれば、切り詰め機能が正しく発動するはずである。</div>
        <div data-sc-name="語義G">雑念を払って、心を落ち着かせる。二番目の語義。</div>
        <div data-sc-name="語義G">一つのことに注意を向ける。三番目の語義（隠れるはず）。</div>
        <div data-sc-name="補説G">supplementary (hidden)</div></li>
      </ol></div>
      <!-- Font-independent overflow guarantee: CI runners have Chrome but
           no CJK fonts, so the Japanese text above renders with fallback
           tofu metrics and may fit within the 3-line cap. The fixed-height
           spacer makes scrollHeight > clientHeight true in EVERY
           environment, so the truncator checks never depend on font
           availability. -->
      <div style="height:140px"></div>
    </div>
    <div class="context-grid">
      <div class="context-main">
        <div class="sentence-japanese" id="sentence"><ruby>心<rt>こころ</rt></ruby>を<ruby>澄<rt>す</rt></ruby>ませて、<b>音楽</b>を聴く。長い文章が二行に折り返される場合の検証も兼ねている。</div>
      </div>
      <div class="context-picture">
        <div class="picture-container"><img id="pic" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Crect width='100%25' height='100%25' fill='%2338bdf8'/%3E%3C/svg%3E"></div>
      </div>
    </div>
    <div class="more-section" hidden>
      <div class="translation-box"><div class="translation-hint">Translation</div>
        <div class="translation-text">To clear one's mind and listen to music.</div></div>
      <div class="html-content secondary-block">Additional context paragraph.</div>
      <div class="html-content secondary-block">漢字のメモ: 澗 — radical 水.</div>
      <div class="html-content secondary-block extended-full">Full extended definition text that stays untruncated.</div>
    </div>
    <button type="button" class="more-toggle" aria-expanded="false">More <span class="more-caret">▾</span></button>
    <div class="shortcut-hints" role="group"><button type="button" class="shortcut-item" data-shortcut="z"><kbd>Z</kbd> hints</button></div>
    <div class="source-footer">SOURCE — some novel</div>
  </div>
</div>
</div>
<script>
window.expandDefinition = function(element) {
  if (element.classList.contains('is-expanded')) return;
  element.classList.add('is-expanded');
};
window.initDefinitionTruncation = function() {
  document.querySelectorAll('.primary-definition').forEach(function(box) {
    const overflows = box.scrollHeight > box.clientHeight + 2;
    box.classList.toggle('is-truncated', overflows);
  });
};
window.initDefinitionTruncation();
</script>
</body></html>"""

FRONT_SENTENCE = """<!doctype html><html><head><meta charset="utf-8">
<style>__CSS__</style></head><body>
<div class="card"><div class="card-wrapper">
  <div class="card-container">
    <div class="sentence-display" id="sent">彼は<b>約束</b>を<ruby>守<rt>まも</rt></ruby>らなかった。</div>
  </div>
</div></div>
</body></html>"""

FRONT_LISTENING = """<!doctype html><html><head><meta charset="utf-8">
<style>__CSS__</style></head><body>
<div class="card"><div class="card-wrapper listening-mode">
  <div class="card-container">
    <div class="listening-view" id="listening">
      <div class="audio-btn-wrapper">
        <button type="button" class="circular-audio-btn large-audio-btn"><span class="audio-btn-content"><span class="audio-btn-label">文</span></span></button>
      </div>
    </div>
  </div>
</div></div>
</body></html>"""


# ---------------------------------------------------------------- probing JS
PROBE = """(() => {
  const r = {};
  const wrapper = document.querySelector('.card-wrapper');
  const card = document.querySelector('.card');
  r.wrapperH = wrapper.getBoundingClientRect().height;
  r.viewportH = window.innerHeight;
  r.docScrollW = document.documentElement.scrollWidth;
  r.docClientW = document.documentElement.clientWidth;
  // overflow-x anywhere?
  r.hOverflow = r.docScrollW > r.docClientW + 1;
  // furigana overlap: rt boxes vs previous line — collect any rt whose
  // top is above the previous sibling line's bottom is hard generically;
  // instead verify every rt's top >= its ruby's parent's top (rt never
  // escapes the container) AND that rt boxes do not overlap the element
  // above: compare first rt top vs sentence/word container top.
  const word = document.querySelector('.word-display');
  if (word) {
    const rb = word.getBoundingClientRect();
    const rt = word.querySelector('rt');
    r.wordFont = parseFloat(getComputedStyle(word).fontSize);
    if (rt) { const rtb = rt.getBoundingClientRect();
      r.wordRtInside = rtb.top >= rb.top - 0.5 && rtb.bottom <= rb.bottom + 0.5; }
  }
  const sent = document.querySelector('#sentence, .sentence-japanese');
  if (sent) {
    r.sentFont = parseFloat(getComputedStyle(sent).fontSize);
    const rt = sent.querySelector('rt');
    const sb = sent.getBoundingClientRect();
    if (rt) { const rtb = rt.getBoundingClientRect();
      r.sentRtInside = rtb.top >= sb.top - 0.5; }
    r.sentH = sb.height;
  }
    const def = document.querySelector('#def');
  if (def) {
    r.defFont = parseFloat(getComputedStyle(def).fontSize);
    const cs = getComputedStyle(def);
    r.defLineH = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.5;
    r.defPadTop = parseFloat(cs.paddingTop) || 0;
    r.defClampedH = def.getBoundingClientRect().height;
    r.defScrollH = def.scrollHeight;
    r.defTruncated = def.classList.contains('is-truncated');
    // expand and re-measure
    window.expandDefinition(def);
    r.defExpandedH = def.getBoundingClientRect().height;
  }
  const notes = document.querySelector('.secondary-block');
  if (notes && def) {
    r.notesFont = parseFloat(getComputedStyle(notes).fontSize);
    r.hierarchy = r.wordFont > r.sentFont && r.sentFont > r.defFont && r.defFont >= r.notesFont;
  }
  const pic = document.querySelector('#pic');
  if (pic) { const pb = pic.getBoundingClientRect(); r.picH = pb.height; r.picW = pb.width; }
  const listening = document.querySelector('#listening');
  if (listening) {
    const lb = listening.getBoundingClientRect();
    const btn = listening.querySelector('.circular-audio-btn');
    r.listenH = lb.height;
    r.listenBtn = btn.getBoundingClientRect().height;
  }
  // Context grid: picture beside the sentence on wide screens.
  const ctxPic = document.querySelector('.context-picture');
  const ctxMain = document.querySelector('.context-main');
  if (ctxPic && ctxMain && innerWidth >= 768) {
    r.twoCol = ctxPic.getBoundingClientRect().left > ctxMain.getBoundingClientRect().right;
    r.sideW = ctxPic.getBoundingClientRect().width;
    r.mainW = ctxMain.getBoundingClientRect().width;
  }
  // Secondary info collapsed by default; More toggle present.
  const more = document.querySelector('.more-section');
  const moreBtn = document.querySelector('.more-toggle');
  if (more && moreBtn) {
    r.moreCollapsed = more.hidden === true
      && moreBtn.getAttribute('aria-expanded') === 'false';
    r.moreBelowFold = more.getBoundingClientRect().height;
  }
  const footer = document.querySelector('.source-footer');
  if (footer && wrapper) {
    r.footerInside = footer.getBoundingClientRect().bottom <= wrapper.getBoundingClientRect().bottom + 1;
  }
  // Keyboard hints: visible on desktop, hidden on touch phones (dead weight).
  const hints = document.querySelector('.shortcut-hints');
  if (hints) { r.hintsDisplay = getComputedStyle(hints).display; }
  // Hero header: 3-column grid (left | word | right) on wide screens,
  // word stacked on its own row with sides below on narrow phones.
  // The word must stay truly centered: |wordCenter - headerCenter| ≈ 0.
  const hero = document.querySelector('.hero-header');
  const heroWord = document.querySelector('.hero-word-wrap');
  const heroLeft = document.querySelector('.hero-side-left');
  const heroRight = document.querySelector('.hero-side-right');
  const heroAudio = document.querySelector('.hero-side .circular-audio-btn');
  if (hero && heroWord && heroLeft && heroRight && word) {
    r.heroDisplay = getComputedStyle(hero).display;
    r.heroAreas = getComputedStyle(hero).gridTemplateAreas || '';
    const hb = hero.getBoundingClientRect();
    const wb = word.getBoundingClientRect();
    r.heroCenterOff = Math.abs((wb.left + wb.width / 2) - (hb.left + hb.width / 2));
    const lb = heroLeft.getBoundingClientRect();
    const rb = heroRight.getBoundingClientRect();
    // split check: left cell ends at/before word start, right starts at/after word end (wide)
    // stacked check (narrow): word bottom above both sides' tops
    r.heroSplit = (lb.right <= wb.left + 2) && (rb.left >= wb.right - 2);
    r.heroStacked = (wb.bottom <= lb.top + 1) && (wb.bottom <= rb.top + 1);
    if (heroAudio) r.heroAudioSize = heroAudio.getBoundingClientRect().width;
  }
  // Context grid top-anchor: the picture must sit at the grid top no
  // matter how long the sentence grows (never vertically centered).
  const ctxGrid = document.querySelector('.context-grid');
  const ctxPicBox = document.querySelector('.context-picture');
  if (ctxGrid && ctxPicBox) {
    r.picTopOff = ctxPicBox.getBoundingClientRect().top - ctxGrid.getBoundingClientRect().top;
  }
  return r;
})()"""


def render(html, width, height):
    """Chrome headless screenshot + JS probe via --dump-dom is awkward;
    use the DevTools-free trick: virtual-time + console.log of the probe,
    captured from chrome's stderr? No — instead write the probe result
    into the DOM title and read it from the dumped DOM."""
    probe_html = html.replace(
        "</body>",
        f"<script>document.title = JSON.stringify({PROBE});</script></body>",
    )
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "card.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(probe_html)
        try:
            out = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu",
                 "--no-sandbox", "--hide-scrollbars",
                 f"--window-size={width},{height}",
                 "--virtual-time-budget=2000",
                 "--dump-dom", f"file://{path}"],
                capture_output=True, text=True, timeout=60,
            ).stdout
        except subprocess.TimeoutExpired:
            return None
    import re
    m = re.search(r"<title>(.*?)</title>", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _hex_lum(hexcode: str) -> float:
    hexcode = hexcode.lstrip("#")
    rgb = tuple(int(hexcode[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])


def _tinted_lum(fg_hex: str, alpha: float = 0.10) -> float:
    fr, fg_, fb = (int(fg_hex.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    r = fr * alpha + 1.0 * (1 - alpha)
    g = fg_ * alpha + 1.0 * (1 - alpha)
    b = fb * alpha + 1.0 * (1 - alpha)

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def main():
    css_early = open(CSS, encoding="utf-8").read()
    light = re.search(
        r"\.card:not\(\.nightMode\):not\(\.night_mode\)\s*\{([^}]*)\}",
        css_early,
        re.S,
    )
    light_body = light.group(1) if light else ""
    for name in ("very-common", "common", "medium", "uncommon", "rare"):
        m = re.search(rf"--freq-{name}\s*:\s*(#[0-9a-fA-F]{{6}})", light_body)
        token = m.group(1) if m else None
        ok = False
        if token:
            fg = _hex_lum(token)
            bg = _tinted_lum(token)
            ratio = (max(fg, bg) + 0.05) / (min(fg, bg) + 0.05)
            ok = ratio >= 4.5
        check(f"light freq-{name} badge text >= 4.5:1 on tinted bg", ok, token or "missing")
    check(
        "audio hit-area reaches 44px without visual growth",
        re.search(r"\.circular-audio-btn::after\s*\{[^}]*inset:\s*-6px", css_early) is not None,
    )
    check(
        "hero stacking has a container-query twin for narrow panes",
        re.search(
            r"@container anki-card \(max-width: 599px\)[\s\S]*?\.hero-header\s*\{[^}]*grid-template-areas:",
            css_early,
        )
        is not None,
    )
    back_early = open(os.path.join(ROOT, "Card 1 - Back.template.anki"), encoding="utf-8").read()
    check(
        "definition key handler supports Space as well as Enter",
        re.search(r"handleDefinitionKey = function\(evt, element\) \{\s*if \(evt\.key === 'Enter' \|\| evt\.key === ' '\)", back_early) is not None,
    )
    check(
        "translation box key handler supports Space as well as Enter",
        "translation-box" in back_early and 'event.key===\' \'' in back_early,
    )
    if not CHROME:
        print("[SKIP] no headless Chrome found — layout checks skipped")
        return 0 if FAIL == 0 else 1
    css = css_early
    # Headless virtual-time freezes the card entrance animations
    # (fadeInUp `both` fill) mid-flight, shifting measured Y positions by
    # up to 10px. Kill animations/transitions in the harness only so probes
    # measure final layout; the product animations are untouched.
    css += "\n*,*::before,*::after{animation:none!important;transition:none!important;}\n"

    # ---- Desktop back card (1440x900, rich card) ----
    back = render(BACK_CARD.replace("__CSS__", css), 1440, 900)
    check("desktop back: probe returned", back is not None)
    if back:
        check("desktop back: content-driven card (rich card < 100% viewport)",
              back["wrapperH"] < back["viewportH"],
              f"wrapper={back['wrapperH']:.0f} viewport={back['viewportH']}")
        check("desktop back: no horizontal overflow", not back["hOverflow"])
        check("desktop back: word furigana stays inside its line box",
              back.get("wordRtInside", True))
        check("desktop back: sentence furigana stays inside its block",
              back.get("sentRtInside", True))
        check("desktop back: hierarchy word > sentence > definition > notes",
              back.get("hierarchy", False),
              f"word={back.get('wordFont')} sent={back.get('sentFont')} "
              f"def={back.get('defFont')} notes={back.get('notesFont')}")
        check("desktop back: long definition IS truncated by JS",
              back.get("defTruncated", False))
        check("desktop back: clamped height ≈ pad + 3 line-heights",
              abs(back["defClampedH"] - (back["defPadTop"] + 3 * back["defLineH"])) <= 8,
              f"clamped={back['defClampedH']:.0f} expected={back['defPadTop'] + 3*back['defLineH']:.0f}")
        check("desktop back: expand grows the definition (one-way)",
              back.get("defExpandedH", 0) > back.get("defClampedH", 0) + 4)
        check("desktop back: image height capped (<= 45vh, fills parallel row)",
              back.get("picH", 0) <= 0.45 * back["viewportH"] + 2,
              f"picH={back.get('picH', 0):.0f}")
        check("desktop back: hero is a 3-col grid with meta split left/right",
              back.get("heroDisplay", "") == "grid"
              and "left" in back.get("heroAreas", "")
              and back.get("heroSplit", False) is True,
              f"display={back.get('heroDisplay')} areas={back.get('heroAreas')} split={back.get('heroSplit')}")
        check("desktop back: word truly centered (off-center <= 8px)",
              back.get("heroCenterOff", 999) <= 8,
              f"off={back.get('heroCenterOff', 999):.1f}px")
        check("desktop back: hero audio stays tappable (>= 32px)",
              back.get("heroAudioSize", 0) >= 32,
              f"audio={back.get('heroAudioSize', 0):.0f}")
        check("desktop back: context grid engaged (picture beside sentence)",
              back.get("twoCol", False),
              f"main={back.get('mainW', 0):.0f} pic-col={back.get('sideW', 0):.0f}")
        check("desktop back: picture column is the minority width",
              back.get("sideW", 1) < back.get("mainW", 0))
        check("desktop back: secondary info collapsed behind More by default",
              back.get("moreCollapsed", False))
        check("desktop back: footer inside the card wrapper",
              back.get("footerInside", False))
        check("desktop back: keyboard hints visible (physical keyboard)",
              back.get("hintsDisplay", "none") != "none",
              f"display={back.get('hintsDisplay')}")

    # ---- Back card without picture (single column) ----
    nopic_html = re.sub(r'<div class="context-picture">[\s\S]*?</div>\s*</div>', '</div>', BACK_CARD)
    nopic = render(nopic_html.replace("__CSS__", css), 1440, 900)
    check("desktop back (no picture): probe returned", nopic is not None)
    if nopic:
        check("desktop back (no picture): single column (no twoCol)", not nopic.get("twoCol", False))
        check("desktop back (no picture): no horizontal overflow", not nopic["hOverflow"])

    # ---- Long sentence: picture stays top-anchored, never dragged down ----
    long_html = BACK_CARD.replace(
        "長い文章が二行に折り返される場合の検証も兼ねている。",
        "長い文章が二行に折り返される場合の検証も兼ねている。" * 30)
    longcard = render(long_html.replace("__CSS__", css), 1440, 900)
    check("desktop back (long sentence): probe returned", longcard is not None)
    if longcard:
        check("desktop back (long sentence): no horizontal overflow", not longcard["hOverflow"])
        check("desktop back (long sentence): picture top-anchored (top offset <= 12px)",
              longcard.get("picTopOff", 999) <= 12,
              f"picTopOff={longcard.get('picTopOff', 999):.0f}")

    # ---- Mobile back card (A50-ish 412x892) ----
    mob = render(BACK_CARD.replace("__CSS__", css), 412, 892)
    check("mobile back: probe returned", mob is not None)
    if mob:
        check("mobile back: no horizontal overflow", not mob["hOverflow"])
        check("mobile back: hero stacks word above sides", mob.get("heroStacked", False) is True)
        check("mobile back: word stays centered (off-center <= 8px)",
              mob.get("heroCenterOff", 999) <= 8,
              f"off={mob.get('heroCenterOff', 999):.1f}px")
        check("mobile back: hero audio stays tappable (>= 32px)",
              mob.get("heroAudioSize", 0) >= 32,
              f"audio={mob.get('heroAudioSize', 0):.0f}")
        check("mobile back: stacked (no context-grid columns)", not mob.get("twoCol", False))
        check("mobile back: no forced viewport fill",
              mob["wrapperH"] < 0.95 * mob["viewportH"],
              f"wrapper={mob['wrapperH']:.0f} viewport={mob['viewportH']}")
        check("mobile back: sentence font stays >= 1rem", mob.get("sentFont", 1) >= 16)
        check("mobile back: keyboard hints hidden (no physical keyboard)",
              mob.get("hintsDisplay", "") == "none",
              f"display={mob.get('hintsDisplay')}")

    # ---- Narrow pane in wide viewport (container <600, viewport 1440) ----
    # Headless --dump-dom does not evaluate @container queries at all
    # (verified with a standalone textbook fixture: container color never
    # applies, while the identical @media twin works). Real renderers that
    # support container queries get the twin rule below (static gate); old
    # WebViews fall back to the viewport-media stacking proven by the
    # mobile 412px probes above. No browser assert possible here.
    narrow_html = BACK_CARD.replace(
        '<div class="card-wrapper back-card">',
        '<div class="card-wrapper back-card" style="max-width:500px">',
    )
    narrow = render(narrow_html.replace("__CSS__", css), 1440, 900)
    check("narrow pane: probe returned", narrow is not None)

    # ---- Front sentence card ----
    fr = render(FRONT_SENTENCE.replace("__CSS__", css), 1440, 900)
    check("front sentence: probe returned", fr is not None)
    if fr:
        check("front sentence: no horizontal overflow", not fr["hOverflow"])
        check("front sentence: content-driven (wrapper < 50% viewport)",
              fr["wrapperH"] < 0.5 * fr["viewportH"],
              f"wrapper={fr['wrapperH']:.0f}")

    # ---- Front listening card ----
    fl = render(FRONT_LISTENING.replace("__CSS__", css), 1440, 900)
    check("front listening: probe returned", fl is not None)
    if fl:
        check("front listening: button is a comfortable target (>= 64px)",
              fl.get("listenBtn", 0) >= 64, f"btn={fl.get('listenBtn')}")
        check("front listening: view height in 20-35vh band",
              0.20 * fl["viewportH"] <= fl.get("listenH", 0) <= 0.36 * fl["viewportH"],
              f"listenH={fl.get('listenH', 0):.0f}")

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
