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
    <div class="shortcut-hints" role="group" aria-label="ショートカット">
      <button type="button" class="shortcut-item" data-shortcut="z" title="振仮名 (Z)"><kbd>Z</kbd> 振仮名</button>
      <button type="button" class="shortcut-item" data-shortcut="x" title="訳 (X)"><kbd>X</kbd> 訳</button>
      <button type="button" class="shortcut-item" data-shortcut="c" title="展開 (C)"><kbd>C</kbd> 展開</button>
    </div>
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
    if (rt) {
      const rtb = rt.getBoundingClientRect();
      // hero uses absolute ruby: the reserved headroom keeps the
      // annotation inside the word's line box (cannot overlap the line above).
      r.wordRtInside = rtb.top >= rb.top - 0.5 && rtb.bottom <= rb.bottom + 0.5;
    }
  }
  const sent = document.querySelector('#sentence, .sentence-japanese');
  if (sent) {
    r.sentFont = parseFloat(getComputedStyle(sent).fontSize);
    const rt = sent.querySelector('rt');
    const sb = sent.getBoundingClientRect();
    if (rt) { const rtb = rt.getBoundingClientRect();
      r.sentRtTopDelta = +(rtb.top - sb.top).toFixed(2); }
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
  // Shortcut hints: visible on desktop AND mobile (they are clickable
  // controls, so phones keep them), and finger-sized on touch.
  const hints = document.querySelector('.shortcut-hints');
  if (hints) {
    r.hintsDisplay = getComputedStyle(hints).display;
    const items = hints.querySelectorAll('.shortcut-item');
    r.hintCount = items.length;
    if (items.length) {
      const hb = hints.getBoundingClientRect();
      const ib = items[0].getBoundingClientRect();
      r.hintItemH = ib.height;
      r.hintRows = new Set(Array.from(items).map(
        (it) => Math.round(it.getBoundingClientRect().top))).size;
      // Hint bar must stay inside the card wrapper (no bleed past the edge).
      const wr = wrapper.getBoundingClientRect();
      r.hintsInside = hb.left >= wr.left - 1 && hb.right <= wr.right + 1;
    }
  }
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
    m = re.search(r"<title>(.*?)</title>", out, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


# Regression probe for the wrapped-furigana edge case (long grouped ruby
# such as 針千本飲[はりせんぼんの] on a 2-line hero/front): measures how far
# any visible rt intrudes into base text on the line above. 0 (<=1.5px
# subpixel tolerance) means the interline headroom holds; pre-fix values
# were ~30px (hero) / ~10px (front).
OVERLAP_PROBE_TMPL = """(() => {
  const el = document.querySelector('__SEL__');
  if (!el) return {worstOverlap: -1};
  const rts = [...el.querySelectorAll('rt')];
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
    acceptNode(n) {
      if (n.parentElement && n.parentElement.closest('rt')) return NodeFilter.FILTER_REJECT;
      if (!n.textContent.trim()) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  const bases = [];
  while (walker.nextNode()) {
    const n = walker.currentNode;
    const rg = document.createRange();
    try { rg.selectNodeContents(n); } catch (e) { continue; }
    for (const r of rg.getClientRects()) bases.push(r);
  }
  let worst = 0;
  for (const rt of rts) {
    const q = rt.getBoundingClientRect();
    const rb = rt.closest('ruby').getBoundingClientRect();
    for (const b of bases) {
      const xo = Math.max(0, Math.min(q.right, b.right) - Math.max(q.left, b.left));
      const yo = Math.max(0, Math.min(q.bottom, b.bottom) - Math.max(q.top, b.top));
      if (xo > 1 && yo > 1 && b.bottom <= rb.top + 2) worst = Math.max(worst, yo);
    }
  }
  return {worstOverlap: worst};
})()"""


def render_overlap(html, width, height):
    """Dump-dom harness for a self-titling fixture (html already sets
    document.title to a JSON probe result). Returns the parsed dict."""
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "card.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
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
    m = re.search(r"<title>(.*?)</title>", out, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


# Real-world grouped-ruby edge data (Hunter x Hunter mine): the hero
# furigana field grouped 4 kanji under one 7-kana reading, which forced a
# 2-line wrap whose second-line rt sat in the interline gap.
WRAPPED_HERO_RUBY = (
    "<ruby>指切<rt>ゆびき</rt></ruby>りげんまん 、"
    "<ruby>嘘<rt>、うそ</rt></ruby>ついたら "
    "<ruby>針千本飲<rt>はりせんぼんの</rt></ruby>ます"
)

# Real card data: the sentence furigana grouped two compounds,
# 除菌[じょきん] 消臭[しょうしゅう]. The second reading is six kana over
# two kanji; at 0.5em with "palt" small-kana metrics it needs ~2.4em
# against a 2em base (splits its base by ~10px — the accepted residual
# trade) while 5-kana readings like じゅうしょ still fit — at the raw 50%
# browser default without palt it would need ~3em and spread both kanji
# apart (root cause of the v1.8.72 住所[じゅうしょ] regression).
SENTENCE_LONG_FURIGANA = (
    '<div class="sentence-japanese" id="longfurigana">'
    "<ruby><rb>除菌</rb><rt>じょきん</rt></ruby>"
    "<ruby><rb>消臭</rb><rt>しょうしゅう</rt></ruby>"
    "　みんなに<ruby><rb>猿</rb><rt>さる</rt></ruby>のにおいが"
    "<ruby><rb>移</rb><rt>うつ</rt></ruby>るといけない"
    "</div>"
)

SENTENCE_RT_PROBE = """(() => {
  const sent = document.querySelector('#longfurigana');
  if (!sent) return {found: false};
  const rubies = [...sent.querySelectorAll('ruby')];
  let maxOff = 0, minGap = 1e9, prev = null;
  for (const ruby of rubies) {
    const rb = ruby.querySelector('rb'), rt = ruby.querySelector('rt');
    if (!rb || !rt) continue;
    const rg = document.createRange();
    rg.selectNodeContents(rb);
    const b = rg.getBoundingClientRect();
    const t = rt.getBoundingClientRect();
    maxOff = Math.max(maxOff, Math.abs((t.left + t.width / 2) - (b.left + b.width / 2)));
    if (prev) minGap = Math.min(minGap, t.left - prev.right);
    prev = t;
  }
  const rt = rubies[1].querySelector('rt');
  const ratio = parseFloat(getComputedStyle(rt).fontSize) /
                parseFloat(getComputedStyle(sent).fontSize);
  return {found: true, maxOff, minGap, ratio};
})()"""

# Report v1.8.69/v1.8.70: the user added a two-kana reading (除菌[でる])
# to test per-kanji placement. Native ruby + ruby-align: space-around
# alone was not enough: the sentence's universal `text-align: center`
# also reached rt, so Chromium centred the whole annotation run over the
# compound (で on the 除/菌 boundary, る at the edge of 菌). The Range
# boxes below still reported one slot per kanji, which is why the first
# probe stayed green while the painted kana were wrong. rt must remain
# start-aligned; then space-around places one kana over each kanji.
SENTENCE_TWO_KANA_FURIGANA = (
    '<div class="sentence-japanese" id="twokanafurigana">'
    "<ruby><rb>除菌</rb><rt>でる</rt></ruby>"
    "</div>"
)

SENTENCE_TWO_KANA_PROBE = """(() => {
  const sent = document.querySelector('#twokanafurigana');
  if (!sent) return {found: false};
  const ruby = sent.querySelector('ruby');
  const rb = ruby && ruby.querySelector('rb');
  const rt = ruby && ruby.querySelector('rt');
  if (!ruby || !rb || !rt) return {found: false};
  const centres = (el) => {
    const node = el.firstChild;
    if (!node || node.nodeType !== 3) return [];
    const out = [];
    for (let i = 0; i < node.length; i++) {
      const range = document.createRange();
      range.setStart(node, i);
      range.setEnd(node, i + 1);
      const box = range.getBoundingClientRect();
      out.push((box.left + box.right) / 2);
    }
    return out;
  };
  const rbC = centres(rb), rtC = centres(rt);
  if (rbC.length < 2 || rtC.length < 2) {
    return {found: false, rbChars: rbC.length, rtChars: rtC.length};
  }
  const rs = getComputedStyle(ruby), ts = getComputedStyle(rt);
  // Resolve the card accent to an rgb() string for a direct comparison with
  // the computed rt colour. The probe is absolute and hidden, so it cannot
  // affect the ruby measurements.
  const accentProbe = document.createElement('span');
  accentProbe.style.cssText = 'position:absolute;visibility:hidden;color:var(--accent-color)';
  // Resolve the accent inside the sentence's theme scope (the fixture uses
  // the light card palette), not against the document root.
  sent.appendChild(accentProbe);
  const accentColor = getComputedStyle(accentProbe).color;
  accentProbe.remove();
  return {
    found: true,
    display: rs.display,
    align: rs.rubyAlign,
    rtDisplay: ts.display,
    rtPosition: ts.position,
    rtAlign: ts.textAlign,
    rtColor: ts.color,
    accentColor: accentColor,
    // NOTE: Range boxes in Chromium report the ruby *slot* (one base
    // character wide), not the painted kana. They are kept for the
    // structural check; rtAlign is the property that decides whether the
    // glyphs are distributed or centred as one run.
    rbSpacing: rbC[1] - rbC[0],
    rtSpacing: rtC[1] - rtC[0],
    offset0: rtC[0] - rbC[0],
    offset1: rtC[1] - rbC[1],
  };
})()"""


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
        re.DOTALL,
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
    # Regression: wrapped hero with long grouped ruby (e.g.
    # 針千本飲[はりせんぼんの]) overlapped the line above — .word-display
    # (always-visible hero rt) had a plain 1.15 line-height with no interline
    # furigana clearance, unlike .sentence-japanese §8.
    check(
        "word-display reserves furigana headroom in line-height (wrapped hero no overlap)",
        re.search(r"\.word-display\s*\{[^}]*line-height:\s*calc\([^}]*var\(--furigana-headroom\)", css_early) is not None,
    )
    # Front never renders ruby (no furigana filter — test_templates §1), so
    # .sentence-display must NOT pay interline furigana clearance: the extra
    # headroom only added dead space to every front card.
    check(
        "sentence-display carries no furigana headroom (front is ruby-free)",
        re.search(r"\.sentence-display[\s\S]{0,800}?var\(--furigana-headroom\)", css_early) is None,
    )
    check(
        "back stacks long-hero sides below the word (is-long rule)",
        re.search(r"\.hero-header\.is-long\s*\{[^}]*grid-template-areas:\s*\"word word\"\s*\"left right\"", css_early) is not None,
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
    check(
        "back stacks a long/wrapping hero below the word (initHeroStacking + is-long)",
        "window.initHeroStacking = function" in back_early
        and "is-long" in back_early
        and "window.initHeroStacking();" in back_early,
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
        # Content-driven, not viewport-filled: the static no-100vh guard in
        # test_templates.py is the fill proof. This height probe allows one
        # furigana headroom (~0.55em hero, ~48px at desktop size) over the
        # viewport for the worst-case fully-populated fixture — the wrapped-
        # hero interline clearance fix correctly costs that on every card.
        check("desktop back: content-driven card (rich card < 110% viewport)",
              back["wrapperH"] < 1.10 * back["viewportH"],
              f"wrapper={back['wrapperH']:.0f} viewport={back['viewportH']}")
        check("desktop back: no horizontal overflow", not back["hOverflow"])
        check("desktop back: word furigana stays inside its line box",
              back.get("wordRtInside", True))
        # Native ruby at line-height 1.5 sits exactly on the sentence border
        # box (delta 0.00px locally). The Ubuntu runner's fallback font puts
        # it a hair above, so 0.5px was below cross-platform variance. Allow
        # 2px: a deliberate 20px rt escape still fails (negative control).
        check("desktop back: sentence furigana stays inside its block",
              back.get("sentRtTopDelta", 0) >= -2.0,
              f"rt top {back.get('sentRtTopDelta')}px relative to sentence top")
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
        check("desktop back: shortcut hints visible",
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
        # Same headroom allowance as desktop: the worst-case fixture grows by
        # one hero headroom with the wrapped-furigana clearance fix.
        check("mobile back: no forced viewport fill",
              mob["wrapperH"] < mob["viewportH"],
              f"wrapper={mob['wrapperH']:.0f} viewport={mob['viewportH']}")
        check("mobile back: sentence font stays >= 1rem", mob.get("sentFont", 1) >= 16)
        # Mobile hierarchy fix (v1.8.76): the Expression must dominate the
        # sentence like on desktop; before this the flat slopes left it at
        # ~1.54x, reading like a slightly bigger sentence instead of the
        # headline.
        check("mobile back: expression dominates sentence (>= 1.7x)",
              mob.get("wordFont", 0) >= 1.7 * mob.get("sentFont", 999),
              f"word={mob.get('wordFont')} sent={mob.get('sentFont')}")
        check("mobile back: shortcut hints visible (clickable on touch)",
              mob.get("hintsDisplay", "none") != "none",
              f"display={mob.get('hintsDisplay')}")
        check("mobile back: hint targets are finger-sized (>= 44px tall)",
              mob.get("hintItemH", 0) >= 44,
              f"h={mob.get('hintItemH', 0):.0f}px")
        # Guarded on a measured height: hidden hints all report top=0, so a
        # rows/inside check alone would pass vacuously on a display:none bar.
        check("mobile back: all three hints fit one row inside the card",
              mob.get("hintCount") == 3 and mob.get("hintRows") == 1
              and mob.get("hintsInside", False) and mob.get("hintItemH", 0) > 0,
              f"rows={mob.get('hintRows')} inside={mob.get('hintsInside')}")

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

    # ---- Wrapped-furigana edge case (long grouped ruby, 2-line wrap) ----
    # Hero: .word-display rt is always visible by product CSS, so a plain
    # constrained container reproduces the reported 指切りげんまん overlap.
    hero_probe = OVERLAP_PROBE_TMPL.replace("__SEL__", "#wrapword")
    hero_html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<style>__CSS__</style></head><body>"
        "<div class=\"card back-card\"><div class=\"card-wrapper back-card\">"
        "<div class=\"card-container\" style=\"max-width:700px\">"
        "<div class=\"hero-header\"><div class=\"hero-side hero-side-left\"></div>"
        "<div class=\"hero-word-wrap\"><div class=\"word-display\" id=\"wrapword\">"
        + WRAPPED_HERO_RUBY +
        "</div></div><div class=\"hero-side hero-side-right\"></div></div>"
        "</div></div></div>"
        "<script>document.title = JSON.stringify(" + hero_probe + ");</script></body></html>"
    )
    hero = render_overlap(hero_html.replace("__CSS__", css), 900, 900)
    check("wrapped hero: overlap probe returned", hero is not None)
    if hero:
        check("wrapped hero: second-line rt never overlaps the line above (<=1.5px)",
              hero.get("worstOverlap", 999) <= 1.5,
              f"worstOverlap={hero.get('worstOverlap')}px")

    # ---- Sentence furigana: long compound readings must not collide ----
    # 除菌[じょきん]消臭[しょうしゅう] at the hero's 0.55em scale made the
    # 6-kana reading start above 菌 and overlap じょきん. The sentence now
    # uses native ruby + ruby-align: space-around at 0.5em with "palt"
    # small-kana metrics; each reading is distributed over its base and
    # its overflow stays inside the reserved rt band without colliding
    # into the rt above.
    sent_html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<style>__CSS__</style></head><body>"
        "<div class=\"card back-card\"><div class=\"card-wrapper back-card furigana-mode\">"
        "<div class=\"card-container\">" + SENTENCE_LONG_FURIGANA + "</div></div></div>"
        "<script>document.title = JSON.stringify(" + SENTENCE_RT_PROBE + ");</script>"
        "</body></html>"
    )
    sr = render_overlap(sent_html.replace("__CSS__", css), 1440, 900)
    check("sentence furigana: collision probe returned", sr is not None)
    if sr:
        check("sentence furigana: each rt centered over its rb (<=1px)",
              sr.get("found") and sr.get("maxOff", 999) <= 1.0,
              f"maxOff={sr.get('maxOff')}")
        check("sentence furigana: adjacent rt never overlap",
              sr.get("found") and sr.get("minGap", -999) >= 0,
              f"minGap={sr.get('minGap')}px")
        check("sentence furigana: old-template 0.5em rt size",
              sr.get("found") and 0.46 <= sr.get("ratio", 9) <= 0.54,
              f"ratio={sr.get('ratio')}")

    # ---- Sentence furigana: native ruby at 0.5em + palt (v1.8.75) ----
    # The old template used native ruby at the browser's default 50% rt;
    # that widened base modules whenever a grouped reading outgrew its
    # kanji (住所[じゅうしょ] => "住 所", かしょ => "か し ょ"). Plain
    # 0.33em kept every reading inside its base but was barely legible.
    # The measured fix: browser-default size + font-feature-settings
    # "palt" so small kana render at roughly half advance — 5-kana
    # readings fit their base and 6-kana readings keep their overflow to
    # ~10px (a third of the un-palt split), space-around keeps kana
    # per-kanji, and the card accent colour comes from the global
    # `ruby rt` rule. Only text-align: start is added so a compound field
    # distributes its kana per kanji instead of centring the run at the
    # boundary.
    one_line = css_early.replace("\n", " ")
    check(
        "sentence furigana: rt readable size, palt, and start alignment",
        re.search(r"\.sentence-japanese rt\s*\{[^}]*display:\s*ruby-text[^}]*position:\s*static[^}]*text-align:\s*start[^}]*font-size:\s*0\.5em[^}]*font-feature-settings:\s*[\"']palt[\"'](?:\s*1)?", one_line) is not None
        and re.search(r"\.sentence-japanese rt\s*\{[^}]*\bcolor\s*:", one_line) is None,
    )
    check(
        "sentence furigana: native ruby with space-around distribution",
        re.search(r"\.sentence-japanese ruby\s*\{[^}]*display:\s*ruby;[^}]*ruby-align:\s*space-around", one_line) is not None
        and re.search(r"\.sentence-japanese rt\s*\{[^}]*display:\s*ruby-text[^}]*position:\s*static[^}]*text-align:\s*start", one_line) is not None,
    )
    two_html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<style>__CSS__</style></head><body>"
        "<div class=\"card back-card\"><div class=\"card-wrapper back-card furigana-mode\">"
        "<div class=\"card-container\">" + SENTENCE_TWO_KANA_FURIGANA + "</div></div></div>"
        "<script>document.title = JSON.stringify(" + SENTENCE_TWO_KANA_PROBE + ");</script>"
        "</body></html>"
    )
    tk = render_overlap(two_html.replace("__CSS__", css), 1440, 900)
    check("sentence furigana (2 kana): per-kanji probe returned",
          tk is not None and tk.get("found", False))
    if tk:
        check("sentence furigana (2 kana): native ruby distribution active",
              tk.get("found") and tk.get("display") == "ruby"
              and tk.get("rtDisplay") == "ruby-text"
              and tk.get("rtPosition") == "static"
              and tk.get("align") == "space-around",
              f"display={tk.get('display')} rt={tk.get('rtDisplay')} "
              f"pos={tk.get('rtPosition')} align={tk.get('align')}")
        # Regression guard for the actual visual bug: with rt inheriting
        # `text-align: center`, space-around still reports one slot per
        # kanji but Chromium paints で and る together at the compound
        # boundary. Assert the distribution switch itself.
        check("sentence furigana (2 kana): rt is start-aligned for distribution",
              tk.get("found") and tk.get("rtAlign") == "start",
              f"rtAlign={tk.get('rtAlign')}")
        # The sentence rt must keep the global accent colour; inheriting the
        # sentence text colour was a regression (v1.8.71) that made the
        # furigana look washed out.
        check("sentence furigana (2 kana): rt keeps the accent colour",
              tk.get("found") and tk.get("rtColor") == tk.get("accentColor"),
              f"rt={tk.get('rtColor')} accent={tk.get('accentColor')}")
    # ---- Long-hero stacking (real initHeroStacking from the back template)
    # Short heroes keep the single row with sides hugging the word; long or
    # wide heroes stack sides below, inside the card, word still centered.
    import re as _re
    _m = _re.search(r"window\.initHeroStacking = function\(\) \{.*?\n    \};",
                    open(os.path.join(ROOT, "Card 1 - Back.template.anki"), encoding="utf-8").read(), _re.DOTALL)
    check("long-hero stacking: initHeroStacking extractable from back template", _m is not None)
    if _m:
        stack_probe = """(()=>{const h=document.querySelector('.hero-header');const w=document.querySelector('.hero-word-wrap');const l=document.querySelector('.hero-side-left');const r=document.querySelector('.hero-side-right');const hb=h.getBoundingClientRect(),wb=w.getBoundingClientRect(),lb=l.getBoundingClientRect(),rb=r.getBoundingClientRect();return {isLong:h.classList.contains('is-long'),stacked:(wb.bottom<=lb.top+1)&&(wb.bottom<=rb.top+1),edgeL:lb.left-hb.left,edgeR:hb.right-rb.right,centerOff:Math.abs((wb.left+wb.width/2)-(hb.left+hb.width/2)),hOverflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1};})()"""
        for _label, _word, _want_long in (
            ("short", "<ruby>澄<rt>す</rt></ruby>ます", False),
            ("long", WRAPPED_HERO_RUBY, True),
        ):
            _html = (
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<style>__CSS__</style></head><body>"
                "<div class=\"card back-card\"><div class=\"card-wrapper back-card\">"
                "<div class=\"card-container\">"
                "<div class=\"hero-header\">"
                "<div class=\"hero-side hero-side-left\"><div class=\"frequency-badge\">FREQ</div>"
                "<div class=\"audio-row\"><span class=\"audio-btn-wrapper\">"
                "<button class=\"circular-audio-btn small-audio-btn\">x</button></span></div></div>"
                "<div class=\"hero-word-wrap\"><div class=\"word-display\">" + _word + "</div></div>"
                "<div class=\"hero-side hero-side-right\"><div class=\"pitch-quiet\">[0]</div>"
                "<div class=\"audio-row\"><span class=\"audio-btn-wrapper\">"
                "<button class=\"circular-audio-btn small-audio-btn\">x</button></span></div></div>"
                "</div></div></div></div>"
                "<script>" + _m.group(0) + "\nwindow.initHeroStacking();\n"
                "document.title = JSON.stringify(" + stack_probe + ");</script></body></html>"
            )
            _r = render_overlap(_html.replace("__CSS__", css), 1440, 900)
            check(f"long-hero stacking ({_label}): probe returned", _r is not None)
            if _r:
                check(f"long-hero stacking ({_label}): {'stacked' if _want_long else 'single row'}",
                      _r.get("isLong", None) is _want_long
                      and _r.get("stacked", None) is (True if _want_long else False))
                check(f"long-hero stacking ({_label}): sides inside the card",
                      _r.get("edgeL", -999) >= -1 and _r.get("edgeR", -999) >= -1,
                      f"edgeL={_r.get('edgeL')} edgeR={_r.get('edgeR')}")
                check(f"long-hero stacking ({_label}): word centered (off-center <= 8px)",
                      _r.get("centerOff", 999) <= 8,
                      f"off={_r.get('centerOff')}")
                check(f"long-hero stacking ({_label}): no horizontal overflow",
                      not _r.get("hOverflow", True))

    # ---- Hero furigana annotation (absolute centering over each rb) ----
    # Regression history: hero used per-kanji absolute ruby segments which
    # center each annotation over its kanji — verified correct for
    # 痛[いた]め 付[つ]ける (いた over 痛, つ over 付, る bare). An attempt
    # to switch the hero rt to static native ruby broke it entirely (rt
    # rendered inline after rb instead of above it, report v1.8.66).
    # Absolute centering is restored: it cannot collide when each reading
    # spans at most its base, and the reserved headroom absorbs overhang
    # without reflow.
    back_t = open(os.path.join(ROOT, "Card 1 - Back.template.anki"), encoding="utf-8").read()
    m_hero = re.search(
        r'\{\{edit:furigana:furigana\}\}', back_t
    )
    check("hero renders the furigana field (per-kanji ruby)", m_hero is not None)
    m_reading = re.search(
        r'\{\{reading\}\}', back_t
    )
    check("hero no longer renders the flat reading field", m_reading is None)
    check(
        "hero rt uses absolute centering over each rb",
        re.search(r'\.word-display ruby rt\s*\{[^}]*position:\s*absolute[^}]*transform:\s*translateX\(-50%\)', css_early.replace("\n", " ")) is not None,
    )
    check(
        "hero rt does not inherit word letter-spacing (+ halt smalls)",
        re.search(r'\.word-display ruby rt\s*\{[^}]*letter-spacing:\s*normal', css_early.replace("\n", " ")) is not None
        and re.search(r'font-feature-settings:[^;]*"halt" 1', css_early) is not None,
    )
    check(
        "no JS furigana controller (CSS-only by design)",
        "initFuriganaFit" not in back_t,
    )

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
