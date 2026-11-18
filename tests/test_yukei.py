#!/usr/bin/env python3
"""Structural and browser contracts for the Yūkei scenic band (ADR 005/006).

This suite is intentionally back-template/CSS-only so it remains runnable while
the repository is on the minimal-front isolation branch. Headless Chrome probes
use the real stylesheet and the real openLightbox controller extracted from the
back template; they skip gracefully when Chrome is unavailable.
"""
from __future__ import annotations

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
CSS = os.path.join(ROOT, "Card 1 - Style.css")
CHROME = shutil.which("google-chrome-stable") or shutil.which("chromium")

PASS = 0
FAIL = 0


def check(name: str, condition: bool) -> None:
    global PASS, FAIL
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    if condition:
        PASS += 1
    else:
        FAIL += 1


def rule_body(css: str, selector_regex: str) -> str | None:
    match = re.search(selector_regex + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else None


def extract_open_lightbox(source: str) -> str:
    marker = "window.openLightbox = function(target)"
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError("unterminated openLightbox function")


def scenic_fixture(css: str, open_lightbox: str, mode: str) -> str:
    theme = " nightMode" if mode == "photo" else ""
    defs = """<svg class="scenic-side-defs" width="0" height="0" aria-hidden="true" focusable="false">
    <defs>
      <clipPath id="scenic-side-clip" clipPathUnits="objectBoundingBox">
        <rect x="0" y="0" width="0.04" height="1"/>
        <rect x="0.96" y="0" width="0.04" height="1"/>
      </clipPath>
    </defs>
  </svg>"""
    if mode == "photo":
        band = """<div class="scenic-band">
  """ + defs + """
  <div class="scenic-photo scenic-photo-trigger" onclick="openLightbox(this)"
       role="button" tabindex="0" aria-label="画像を拡大"
       onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); this.click()}">
    <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Crect width='100%25' height='100%25' fill='%23204080'/%3E%3Ccircle cx='400' cy='260' r='150' fill='%23e07050'/%3E%3C/svg%3E" alt="frame">
    <div class="tint"></div><div class="grain"></div><div class="wash"></div><div class="fade"></div>
  </div>
</div>"""
    else:
        band = """<div class="scenic-band" aria-hidden="true">
  """ + defs + """
  <svg class="scenic-scene" viewBox="0 0 400 60" preserveAspectRatio="none" focusable="false">
    <circle class="scenic-star" cx="70" cy="8" r="1.1" fill="#fff"/>
    <circle class="scenic-glow" cx="232" cy="18" r="15" fill="var(--accent-color)"/>
    <path d="M156,42 L185,2 L204,26 L211,23 L216,42 Z" fill="var(--scenic-fuji)"/>
    <g class="scenic-cloud is-far"><path d="M0,36 C50,28 100,38 160,31 C230,23 300,36 400,28 L400,60 L0,60 Z" fill="var(--scenic-cloud)"/></g>
    <path d="M0,54 C60,50 130,56 210,52 C290,48 340,55 400,51 L400,60 L0,60 Z" fill="var(--card-bg)"/>
  </svg>
</div>"""
    return ("""<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0}""" + css + """</style></head><body>
<div class="card""" + theme + '"><div class="card-wrapper back-card"><div class="card-container">\n'
            + band + """
<div class="card-content">
<div class="hero-header"><div class="hero-side hero-side-left"></div><div class="hero-word-wrap"><div class="word-display">名将</div></div><div class="hero-side hero-side-right"></div></div>
<div class="context-grid"><div class="context-main"><div class="sentence-japanese">文脈を読む。</div></div></div>
</div>
</div></div></div>
<script>""" + open_lightbox + """;</script>
</body></html>""")


SCENIC_PROBE = r"""(() => {
  const r = {};
  const container = document.querySelector('.card-container');
  const band = document.querySelector('.scenic-band');
  const content = document.querySelector('.card-content');
  const context = document.querySelector('.context-grid');
  const main = document.querySelector('.context-main');
  const hero = document.querySelector('.hero-header');
  const bandStyle = getComputedStyle(band);
  const hitClass = (el) => el ? (typeof el.className === 'string' ? el.className : el.getAttribute('class') || '') : '';
  r.first = container.firstElementChild === band;
  r.contentSecond = container.children[1] === content;
  const bandBox = band.getBoundingClientRect();
  const containerBox = container.getBoundingClientRect();
  const heroBox = hero.getBoundingClientRect();
  r.bandH = bandBox.height;
  r.containerH = containerBox.height;
  r.bandPosition = bandStyle.position;
  r.bandClip = bandStyle.clipPath;
  r.bandMask = bandStyle.maskImage;
  r.bandBackground = bandStyle.backgroundImage;
  r.railPseudoW = parseFloat(getComputedStyle(band, '::before').width) || 0;
  r.bandFlow = heroBox.top - (containerBox.top
    + (parseFloat(getComputedStyle(container).borderTopWidth) || 0)
    + (parseFloat(getComputedStyle(container).paddingTop) || 0));
  r.centerOffset = Math.abs(
    (bandBox.left + bandBox.right) / 2 - (containerBox.left + containerBox.right) / 2
  );
  r.wrapperFill = bandBox.left <= containerBox.left + 1 && bandBox.right >= containerBox.right - 1;
  r.overlap = bandBox.bottom - heroBox.top;
  r.noOverflow = document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1;
  r.contextRatio = main.getBoundingClientRect().width / context.getBoundingClientRect().width;
  r.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const defs = band.querySelector('.scenic-side-defs');
  r.defsW = defs.getBoundingClientRect().width;
  r.defsH = defs.getBoundingClientRect().height;
  const leftHit = document.elementFromPoint(bandBox.left + 10, bandBox.top + bandBox.height / 2);
  const rightHit = document.elementFromPoint(bandBox.right - 10, bandBox.top + bandBox.height / 2);
  const centerHit = document.elementFromPoint(
    (bandBox.left + bandBox.right) / 2, (bandBox.top + bandBox.bottom) / 2);
  r.leftHit = hitClass(leftHit);
  r.rightHit = hitClass(rightHit);
  r.centerInBand = !!(centerHit && centerHit.closest && centerHit.closest('.scenic-band'));
  const scene = band.querySelector('.scenic-scene');
  r.sceneDisplay = scene ? getComputedStyle(scene).display : null;
  const photo = document.querySelector('.scenic-photo');
  if (photo) {
    const source = photo.querySelector('img');
    r.role = photo.getAttribute('role');
    r.tabIndex = photo.tabIndex;
    r.photoChildDisplay = getComputedStyle(source).display;
    r.filter = getComputedStyle(source).filter;
    r.tintBlend = getComputedStyle(photo.querySelector('.tint')).mixBlendMode;
    photo.click();
    let overlay = document.querySelector('.lightbox-overlay');
    const clone = overlay && overlay.querySelector('.expanded-img');
    r.clickOpen = !!overlay;
    r.sameSource = !!clone && clone.src === source.src;
    r.cloneUnblurred = !!clone && !getComputedStyle(clone).filter.includes('blur');
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    r.escapeClose = !document.querySelector('.lightbox-overlay');
    r.focusReturn = document.activeElement === photo;
    photo.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    overlay = document.querySelector('.lightbox-overlay');
    r.enterOpen = !!overlay;
    if (overlay) overlay.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    r.backdropClose = !document.querySelector('.lightbox-overlay');
    photo.dispatchEvent(new KeyboardEvent('keydown', {key: ' ', bubbles: true}));
    overlay = document.querySelector('.lightbox-overlay');
    r.spaceOpen = !!overlay;
    if (overlay) overlay.dispatchEvent(new MouseEvent('click', {bubbles: true}));
  } else {
    r.fallbackAria = band.getAttribute('aria-hidden');
    r.fallbackFocusable = band.hasAttribute('tabindex') || band.hasAttribute('onclick');
    r.fallbackBackground = bandStyle.backgroundImage;
    const star = band.querySelector('.scenic-star');
    r.starAnimation = getComputedStyle(star).animationName;
  }
  document.title = JSON.stringify(r);
  return r;
})()"""



def render_probe(html: str, width: int, height: int, reduced_motion: bool = False) -> dict | None:
    probe_html = html.replace("</body>", f"<script>{SCENIC_PROBE}</script></body>")
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "scenic.html")
        with open(path, "w", encoding="utf-8") as file:
            file.write(probe_html)
        command = [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            "--virtual-time-budget=2000",
            "--dump-dom",
            f"file://{path}",
        ]
        if reduced_motion:
            command.insert(-2, "--force-prefers-reduced-motion")
        try:
            output = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            ).stdout
        except subprocess.TimeoutExpired:
            return None
    match = re.search(r"<title>(.*?)</title>", output, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def main() -> int:
    back = open(BACK, encoding="utf-8").read()
    css = open(CSS, encoding="utf-8").read()

    markup = re.sub(r"<!--.*?-->", "", back, flags=re.S)
    markup = re.sub(r"<script.*?</script>", "", markup, flags=re.S)

    # Markup shape: one Picture field, mutually exclusive photo/fallback bands,
    # and no retired context-grid thumbnail.
    check("Back: Picture is referenced exactly once", len(re.findall(r"\{\{Picture\}\}", back)) == 1)
    check(
        "Back: scenic photo/fallback conditionals are balanced and adjacent",
        re.search(
            r"\{\{#Picture\}\}[\s\S]*?\{\{/Picture\}\}\s*"
            r"\{\{\^Picture\}\}[\s\S]*?\{\{/Picture\}\}",
            back,
        )
        is not None,
    )
    check(
        "Back: scenic band is the first card-container child before hero",
        re.search(
            r'<div class="card-container">\s*\{\{#Picture\}\}\s*'
            r'<div class="scenic-band">',
            back,
        )
        is not None,
    )
    check(
        "Back: one card-content wrapper holds everything after the band",
        re.search(
            r"\{\{/Picture\}\}\s*<div class=\"card-content\">[\s\S]*?"
            r'<div class="hero-header">',
            back,
        )
        is not None
        and "<!-- End card-content -->" in back,
    )

    photo_branch = re.search(r"\{\{#Picture\}\}([\s\S]*?)\{\{/Picture\}\}", back)
    photo = photo_branch.group(1) if photo_branch else ""
    fallback_branch = re.search(r"\{\{\^Picture\}\}([\s\S]*?)\{\{/Picture\}\}", back)
    fallback = fallback_branch.group(1) if fallback_branch else ""

    check(
        "Back: both scenic branches define the wide-card side clip",
        photo_branch is not None
        and fallback_branch is not None
        and photo_branch.group(1).count('id="scenic-side-clip"') == 1
        and fallback_branch.group(1).count('id="scenic-side-clip"') == 1
        and photo_branch.group(1).count('width="0.04"') == 2
        and fallback_branch.group(1).count('width="0.04"') == 2
        and photo_branch.group(1).count('x="0.96"') == 1
        and fallback_branch.group(1).count('x="0.96"') == 1,
    )
    check(
        "Back: illustrated scene carries its own wide-card class",
        'class="scenic-scene"' in fallback,
    )

    check(
        "Back: photo band reuses the existing lightbox trigger",
        'class="scenic-photo scenic-photo-trigger"' in photo
        and 'onclick="openLightbox(this)"' in photo
        and "window.openLightbox = function(target)" in back,
    )
    check(
        "Back: photo trigger is keyboard-operable and labelled",
        'role="button"' in photo
        and 'tabindex="0"' in photo
        and 'aria-label="画像を拡大"' in photo
        and "event.key==='Enter'" in photo
        and 'event.key===\' \'' in photo,
    )
    check(
        "Back: fallback is decorative and not focusable/clickable",
        'class="scenic-band" aria-hidden="true"' in fallback
        and 'focusable="false"' in fallback
        and "onclick=" not in fallback
        and "tabindex=" not in fallback,
    )
    check(
        "Back: retired inline Picture markup is absent",
        "context-picture" not in back and "picture-container" not in back,
    )
    check(
        "Back: div structure remains balanced after thumbnail removal",
        len(re.findall(r"<div\b", markup, flags=re.I)) == len(re.findall(r"</div\s*>", markup, flags=re.I)),
    )
    check(
        "Back: lightbox clone still uses the source image rather than styled node",
        "const clone = document.createElement('img')" in back
        and "clone.src = img.src" in back
        and "clone.alt = img.alt || ''" in back,
    )
    guard = re.search(
        r"if \(/\^(.*)/i\.test\(img\.getAttribute\('src'\)\)\) return;",
        back,
    )
    if guard:
        hostile = [
            "https://evil.example/x.png",
            "http://evil.example/",
            "//evil.example/x.png",
            "///evil.example/x.png",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "data:text/html,<script>alert(1)</script>",
        ]
        allowed = [
            "paste-abc123.jpg",
            "collection.media/yuki.png",
            "../media/x.png",
            "data:image/png;base64,iVBORw0KGgo=",
            "data:image/svg+xml,%3Csvg/%3E",
        ]
        pattern = re.compile("^" + guard.group(1).replace("\\/", "/"), re.I)
        check(
            "Back: lightbox URL guard refuses remote/file/script sources",
            all(pattern.search(src) for src in hostile),
        )
        check(
            "Back: lightbox URL guard allows local media + image data URIs",
            all(not pattern.search(src) for src in allowed),
        )
    else:
        check("Back: lightbox URL guard is present and extractable", False)

    # CSS tokens and the exact corrected photo pipeline.
    for token, value in (
        ("--scenic-blur", "16px"),
        ("--scenic-sat", "0.8"),
        ("--scenic-tint", "0.25"),
        ("--scenic-wash", "0.25"),
        ("--scenic-rail-w", "4%"),
    ):
        check(f"CSS: {token} is declared once with {value}", len(re.findall(rf"{re.escape(token)}\s*:\s*{re.escape(value)}\s*;", css)) == 1)

    container = rule_body(css, r"\.back-card \.card-container")
    check("CSS: back container clips the scenic band corners", container is not None and "overflow: hidden" in container)
    check(
        "CSS: scenic photo shares the existing keyboard-focus selector group",
        re.search(
            r"\.circular-audio-btn:focus-visible,\s*"
            r"\.translation-box:focus-visible,\s*"
            r"\.picture-container:focus-visible,\s*"
            r"\.scenic-photo-trigger:focus-visible\s*\{[^}]*outline:",
            css,
        )
        is not None,
    )

    scenic = css.split("17. SCENIC BAND", 1)[1] if "17. SCENIC BAND" in css else ""
    shell = rule_body(scenic, r"\.scenic-band")
    fallback_bg = rule_body(scenic, r"\.scenic-band:not\(:has\(\.scenic-photo\)\)")
    check(
        "CSS: base scenic sky applies only to the illustrated fallback",
        shell is not None
        and "background:" not in shell
        and fallback_bg is not None
        and "var(--scenic-sky)" in fallback_bg,
    )
    check(
        "CSS: scenic band is centered and overhangs 12px without growing flow",
        shell is not None
        and "width: auto" in shell
        and "height: calc(var(--scenic-band-h) + 12px)" in shell
        and "-12px;" in shell,
    )

    photo_rule = rule_body(scenic, r"\.scenic-photo img")
    check(
        "CSS: photo keeps color and applies the tuned CSS filter",
        photo_rule is not None
        and "saturate(var(--scenic-sat))" in photo_rule
        and "contrast(1.05)" in photo_rule
        and "brightness(1.03)" in photo_rule
        and "blur(var(--scenic-blur))" in photo_rule,
    )
    check(
        "CSS: tint uses overlay and never replaces source hue",
        ".scenic-photo .tint" in scenic
        and "mix-blend-mode: overlay" in scenic
        and "mix-blend-mode: color" not in scenic
        and "filter: grayscale" not in scenic,
    )
    for layer in ("tint", "grain", "wash", "fade"):
        check(f"CSS: scenic photo includes the {layer} layer", f".scenic-photo .{layer}" in scenic)
    fade_rule = rule_body(scenic, r"\.scenic-photo \.fade")
    check(
        "CSS: photo fade becomes solid before the furigana overlap",
        fade_rule is not None
        and "transparent 40%" in fade_rule
        and "var(--card-bg) 82%" in fade_rule,
    )
    check(
        "CSS: reduced motion disables all fallback animations",
        re.search(
            r"@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*"
            r"\.scenic-star,\s*\.scenic-glow,\s*\.scenic-cloud\s*\{[^}]*animation:\s*none",
            scenic,
        )
        is not None,
    )

    # ADR 006 deliberately leaves the old CSS rules in place this pass.
    check(
        "CSS: retired context/picture rules remain for this compatibility pass",
        ".context-grid:has(.context-picture)" in css and ".picture-container" in css,
    )
    check(
        "CSS: scenic band isolates paint invalidation",
        re.search(r"\.scenic-band\s*\{[^}]*contain:\s*paint", scenic) is not None,
    )
    check(
        "CSS: mobile kills cloud drift but keeps stars/glow",
        re.search(
            r"@media \(max-width: 600px\)[\s\S]*?\.scenic-cloud\s*\{[^}]*animation:\s*none",
            css,
        )
        is not None,
    )

    wide = scenic.split("17b. WIDE-CARD SIDE RAILS", 1)[1] if "17b. WIDE-CARD SIDE RAILS" in scenic else ""
    check(
        "CSS: wide rails are gated by the 1000px card container",
        "@container anki-card (min-width: 1000px)" in wide,
    )
    defs_rule = rule_body(scenic, r"\.scenic-band \.scenic-side-defs")
    check(
        "CSS: clip definition box is zero-sized",
        defs_rule is not None
        and "position: absolute" in defs_rule
        and "width: 0" in defs_rule
        and "height: 0" in defs_rule,
    )
    wide_band = rule_body(wide, r"\.back-card \.card-container > \.scenic-band")
    check(
        "CSS: wide band leaves flow, fills the card, and clips to rails",
        wide_band is not None
        and "position: absolute" in wide_band
        and "inset: 0" in wide_band
        and "height: auto" in wide_band
        and "margin: 0" in wide_band
        and "clip-path: url(#scenic-side-clip)" in wide_band
        and "mask-image: linear-gradient" in wide_band
        and "background: var(--scenic-sky)" in wide_band,
    )
    check(
        "CSS: wide rails hide the top scene but keep the trigger",
        ".scenic-band .scenic-scene" in wide
        and ".scenic-band .scenic-photo > *" in wide
        and "display: none" in wide,
    )
    fade_pseudos = re.search(
        r"\.scenic-band::before,\s*\.scenic-band::after\s*\{([^}]*)\}", wide
    )
    check(
        "CSS: wide inner fade matches the 4% rail token",
        fade_pseudos is not None
        and "width: var(--scenic-rail-w, 4%)" in fade_pseudos.group(1)
        and wide.count("linear-gradient(to right, transparent 35%, var(--card-bg) 100%)") == 1
        and wide.count("linear-gradient(to left, transparent 35%, var(--card-bg) 100%)") == 1,
    )
    content_rule = rule_body(wide, r"\.card-content")
    check(
        "CSS: wide content layer paints above the rails",
        content_rule is not None
        and "position: relative" in content_rule
        and "z-index: 1" in content_rule,
    )
    check(
        "CSS: wide focus ring is inset and brightens the rails",
        "outline-offset: -4px" in wide
        and "brightness(1.25)" in wide,
    )

    # Dynamic browser contracts run against the real stylesheet and the real
    # openLightbox function extracted from the back template. They are skipped
    # gracefully when Chrome is unavailable, matching the existing test style.
    if not CHROME:
        print("[SKIP] no headless Chrome found — Yūkei browser checks skipped")
    else:
        open_lightbox = extract_open_lightbox(back)

        # Phone: the established top band, unchanged in structure and behavior.
        photo_mobile = render_probe(scenic_fixture(css, open_lightbox, "photo"), 412, 892)
        check("Browser: phone photo probe returned", photo_mobile is not None)
        if photo_mobile:
            check(
                "Browser: phone photo band stays centered, compact, and first",
                photo_mobile.get("first") is True
                and photo_mobile.get("contentSecond") is True
                and photo_mobile.get("centerOffset", 999) <= 1
                and photo_mobile.get("wrapperFill") is True
                and 56 <= photo_mobile.get("bandH", 0) <= 70
                and 11 <= photo_mobile.get("overlap", 0) <= 13,
            )
            check(
                "Browser: phone keeps the photo-derived top band and pipeline",
                photo_mobile.get("bandPosition") == "relative"
                and photo_mobile.get("bandClip") == "none"
                and photo_mobile.get("photoChildDisplay") == "block"
                and photo_mobile.get("defsW") == 0
                and photo_mobile.get("defsH") == 0
                and "saturate(0.8)" in photo_mobile.get("filter", "")
                and "blur(16px)" in photo_mobile.get("filter", "")
                and photo_mobile.get("tintBlend") == "overlay",
            )
            check("Browser: phone photo mode has no horizontal overflow", photo_mobile.get("noOverflow") is True)
            check(
                "Browser: phone sentence context uses the full grid width",
                photo_mobile.get("contextRatio", 0) >= 0.98,
            )
            check(
                "Browser: phone photo trigger keeps button role and tab order",
                photo_mobile.get("role") == "button"
                and photo_mobile.get("tabIndex") == 0,
            )
            check(
                "Browser: phone click/Enter/Space open the original in the lightbox",
                photo_mobile.get("clickOpen") is True
                and photo_mobile.get("sameSource") is True
                and photo_mobile.get("cloneUnblurred") is True
                and photo_mobile.get("enterOpen") is True
                and photo_mobile.get("spaceOpen") is True,
            )
            check(
                "Browser: phone Escape and backdrop close the lightbox",
                photo_mobile.get("escapeClose") is True
                and photo_mobile.get("backdropClose") is True,
            )
            check(
                "Browser: phone closing the lightbox returns focus to the trigger",
                photo_mobile.get("focusReturn") is True,
            )

        # A narrow desktop pane (below the 1000px container gate) keeps the
        # established top band, not a half-applied rail layout.
        photo_narrow = render_probe(scenic_fixture(css, open_lightbox, "photo"), 900, 900)
        check("Browser: narrow-pane photo probe returned", photo_narrow is not None)
        if photo_narrow:
            check(
                "Browser: narrow desktop pane keeps the top band",
                photo_narrow.get("bandPosition") == "relative"
                and photo_narrow.get("bandClip") == "none"
                and 56 <= photo_narrow.get("bandH", 0) <= 70
                and 11 <= photo_narrow.get("overlap", 0) <= 13
                and photo_narrow.get("photoChildDisplay") == "block",
            )

        # Wide pane: the band becomes two clipped, cool-sky side rails.
        photo_wide = render_probe(scenic_fixture(css, open_lightbox, "photo"), 1440, 900)
        check("Browser: wide-pane photo probe returned", photo_wide is not None)
        if photo_wide:
            check(
                "Browser: wide band leaves flow and fills the card",
                photo_wide.get("first") is True
                and photo_wide.get("bandPosition") == "absolute"
                and photo_wide.get("wrapperFill") is True
                and abs(photo_wide.get("bandH", 0) - photo_wide.get("containerH", 0)) <= 3
                and -1 <= photo_wide.get("bandFlow", 99) <= 1,
            )
            check(
                "Browser: wide band is clipped to two cool-sky rails",
                "scenic-side-clip" in photo_wide.get("bandClip", "")
                and photo_wide.get("bandMask") not in (None, "none")
                and "gradient" in photo_wide.get("bandBackground", "")
                and photo_wide.get("railPseudoW", 0) >= 45,
            )
            check(
                "Browser: wide rails hide the scene but keep the trigger",
                photo_wide.get("photoChildDisplay") == "none"
                and photo_wide.get("role") == "button"
                and photo_wide.get("tabIndex") == 0,
            )
            check(
                "Browser: wide rail hit-testing keeps one lightbox target",
                "scenic-photo" in photo_wide.get("leftHit", "")
                and "scenic-photo" in photo_wide.get("rightHit", "")
                and photo_wide.get("centerInBand") is False,
            )
            check(
                "Browser: wide content sits above the rails",
                photo_wide.get("contentSecond") is True
                and photo_wide.get("contextRatio", 0) >= 0.98
                and photo_wide.get("noOverflow") is True,
            )
            check(
                "Browser: wide click/Enter/Space open the original in the lightbox",
                photo_wide.get("clickOpen") is True
                and photo_wide.get("sameSource") is True
                and photo_wide.get("cloneUnblurred") is True
                and photo_wide.get("enterOpen") is True
                and photo_wide.get("spaceOpen") is True,
            )
            check(
                "Browser: wide Escape/backdrop close and focus return",
                photo_wide.get("escapeClose") is True
                and photo_wide.get("backdropClose") is True
                and photo_wide.get("focusReturn") is True,
            )

        # Wide fallback: decorative rails, no trigger, scene removed.
        fallback_wide = render_probe(scenic_fixture(css, open_lightbox, "fallback"), 1440, 900)
        check("Browser: wide fallback probe returned", fallback_wide is not None)
        if fallback_wide:
            check(
                "Browser: wide fallback renders decorative, non-focusable rails",
                fallback_wide.get("first") is True
                and fallback_wide.get("contentSecond") is True
                and fallback_wide.get("bandPosition") == "absolute"
                and "scenic-side-clip" in fallback_wide.get("bandClip", "")
                and fallback_wide.get("railPseudoW", 0) >= 45
                and fallback_wide.get("fallbackAria") == "true"
                and fallback_wide.get("fallbackFocusable") is False
                and "gradient" in fallback_wide.get("fallbackBackground", "")
                and fallback_wide.get("sceneDisplay") == "none"
                and "scenic-photo" not in fallback_wide.get("leftHit", ""),
            )

        # Phone fallback + reduced motion stays the ADR 005 band.
        fallback_reduced = render_probe(
            scenic_fixture(css, open_lightbox, "fallback"),
            412,
            892,
            reduced_motion=True,
        )
        check("Browser: reduced-motion fallback probe returned", fallback_reduced is not None)
        if fallback_reduced:
            check(
                "Browser: phone fallback remains decorative and non-focusable",
                fallback_reduced.get("fallbackAria") == "true"
                and fallback_reduced.get("fallbackFocusable") is False
                and "gradient" in fallback_reduced.get("fallbackBackground", "")
                and fallback_reduced.get("sceneDisplay") == "block",
            )
            check(
                "Browser: reduced motion disables fallback animation",
                fallback_reduced.get("reduced") is True
                and fallback_reduced.get("starAnimation") == "none",
            )

    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
