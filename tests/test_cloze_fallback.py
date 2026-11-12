#!/usr/bin/env python3
"""Cloze-fallback behavioral tests (sentence preservation).

Extracts the CLOZE FALLBACK block verbatim from the real
`Card 1 - Front.template.anki` and runs it in headless Chrome against
three front harnesses, asserting the sentence on screen:

  1. Yomitan card: unbolded Sentence carries the WHOLE sentence while the
     cloze trio holds only a context window that is ALREADY CONTAINED in
     it -> the full sentence must survive untouched (no <b> injected, no
     text replaced). Regression for: front showed only the cloze fragment
     (そう自分に言い聞かせながらブレーキを踏み続けるのも) instead of the
     full five-line sentence.
  2. jidoujisho card: unbolded Sentence does NOT contain the trio ->
     the rebuild still fires (prefix + <b>body</b> + suffix), preserving
     the original purpose of the fallback.
  3. Proper Yomitan card: Sentence already has <b> -> untouched.

Run directly:  python3 tests/test_cloze_fallback.py
Wired into ./verify alongside the other suites. Skipped gracefully
without Chrome.

Dependencies: headless Chrome only (same as test_front_modes.py).
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
FRONT = os.path.join(ROOT, "Card 1 - Front.template.anki")
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


def load_cloze_block():
    """Extract the CLOZE FALLBACK block verbatim from the real front template."""
    with open(FRONT, encoding="utf-8") as f:
        front = f.read()
    m = re.search(
        r"/\* --- CLOZE FALLBACK \(BEGIN.*?"
        r"/\* --- CLOZE FALLBACK \(END\) --- \*/",
        front,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("cloze fallback block not found in front template")
    return m.group(0)


# The real card that exposed the bug (note 1794493500508, 言い聞かせる):
# full Sentence field, no <b> anywhere, and a cloze trio that is a short
# context window strictly inside that sentence.
FULL_SENTENCE = (
    "(福原) 恋愛とは<br>"
    "一過性の精神疾患でしかないと先生は おっしゃいましたが<br>"
    "そう自分に言い聞かせながらブレーキを踏み続けるのも<br>"
    "もう… 限界！<br>"
    "かぁ～｡"
)
TRIO = {
    "pre": "そう自分に",
    "mid": "言い聞かせ",
    "suf": "ながらブレーキを踏み続けるのも",
}
TRIO_TEXT = TRIO["pre"] + TRIO["mid"] + TRIO["suf"]


def build_html(block, sentence_html):
    return f"""<!doctype html><html><head><meta charset="utf-8"></head><body>
<div class="card"><div class="card-wrapper"><div class="card-container">
<div class="cloze-probe" hidden>
  <span class="cloze-pre">{TRIO["pre"]}</span>
  <span class="cloze-mid">{TRIO["mid"]}</span>
  <span class="cloze-suf">{TRIO["suf"]}</span>
</div>
<div class="sentence-display">{sentence_html}</div>
</div></div></div>
<script>
var report = {{}};
try {{
  var container = document.querySelector('.card-container');
{block}
  var sd = container.querySelector('.sentence-display');
  report.exists = !!sd;
  report.text = sd ? sd.textContent : null;
  report.hasBold = sd ? !!sd.querySelector('b, strong') : null;
}} catch(e) {{ report.err = String(e && e.stack || e); }}
document.title = JSON.stringify(report);
</script>
</body></html>"""


def render(html):
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "cloze.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        try:
            out = subprocess.run(
                [
                    CHROME,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--hide-scrollbars",
                    "--window-size=1440,900",
                    "--virtual-time-budget=1500",
                    "--dump-dom",
                    f"file://{path}",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
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


def case(block, name, sentence_html):
    r = render(build_html(block, sentence_html))
    check(f"{name}: probe returned", r is not None)
    if not r:
        return None
    if "err" in r:
        check(f"{name}: block ran without errors", False, r["err"])
        return None
    check(f"{name}: block ran without errors", True)
    return r


def main():
    if not CHROME:
        print("[SKIP] no headless Chrome found — cloze-fallback checks skipped")
        return 0
    block = load_cloze_block()

    # Case 1: THE BUG. Unbolded full sentence, trio contained in it.
    # The sentence is the richer content — it must survive verbatim and
    # must NOT be replaced by the short cloze fragment.
    r = case(block, "contained trio: full sentence preserved", FULL_SENTENCE)
    if r:
        text = r["text"] or ""
        check("contained trio: sentence-display still present", r["exists"])
        check(
            "contained trio: full sentence kept (限界！ line intact)",
            "もう… 限界！" in text,
        )
        check("contained trio: trio context still on the front", TRIO_TEXT in text)
        check(
            "contained trio: no <b> injected into a plain sentence",
            r["hasBold"] is False,
        )

    # Case 2: original jidoujisho purpose. Unbolded sentence that does NOT
    # contain the trio — the rebuild must still fire, with the bold target.
    r = case(block, "jidoujisho rebuild still fires", "全く別の文が入っている場合")
    if r:
        check("jidoujisho: sentence rebuilt from trio", (r["text"] or "") == TRIO_TEXT)
        check("jidoujisho: target term bolded", r["hasBold"] is True)

    # Case 3: proper Yomitan card — bold already present, never touched.
    r = case(block, "bolded sentence untouched", "世の中って<b>不公平</b>よね")
    if r:
        check(
            "bolded: original sentence kept",
            (r["text"] or "") == "世の中って不公平よね",
        )
        check("bolded: bold marker preserved", r["hasBold"] is True)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
