#!/usr/bin/env python3
"""Readability invariants kept from the archived design-system branch.

Only the two user-facing fixes are enforced here:
  - muted text meets WCAG AA (4.5:1) in both themes
  - the hint bar and source footer carry no opacity multiplier
  - the three smallest chrome labels keep a 12px floor at every width

The rest of the design-system gate (motion tokens, radii, border treatment,
desktop label remap) lives on design/visual-system-alignment and is not part
of this file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "Card 1 - Style.css"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"[PASS] {name}")
        return
    print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))
    failures.append(name)


if not CSS_PATH.is_file():
    print(f"[FAIL] stylesheet missing: {CSS_PATH}")
    sys.exit(1)

css_raw = CSS_PATH.read_text(encoding="utf-8")
css = re.sub(r"/\*.*?\*/", "", css_raw, flags=re.S)


def split_selectors(text: str) -> list[str]:
    """Split a selector list on commas, ignoring commas inside :has()/:not()."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    parts.append(current)
    return [" ".join(part.split()) for part in parts]


RULES: list[tuple[list[str], str]] = []
for match in re.finditer(r"(?s)([^{}]+?)\{([^{}]*)\}", css):
    selectors = split_selectors(match.group(1))
    RULES.append(([selector for selector in selectors if selector], match.group(2)))


def bodies_for(exact: str) -> list[str]:
    """Bodies of rules whose selector list contains exactly `exact`."""
    return [body for selectors, body in RULES if exact in selectors]


def bodies_containing(fragment: str) -> list[str]:
    """Bodies of rules with any selector containing `fragment`."""
    return [
        body
        for selectors, body in RULES
        if any(fragment in selector for selector in selectors)
    ]


def block(pattern: str) -> str:
    match = re.search(pattern + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else ""


def token(body: str, name: str) -> str | None:
    match = re.search(rf"{re.escape(name)}\s*:\s*([^;]+);", body)
    return match.group(1).strip() if match else None


# --- 1. Muted-text contrast -------------------------------------------------
def luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]

    def linear(channel: float) -> float:
        return (
            channel / 12.92
            if channel <= 0.03928
            else ((channel + 0.055) / 1.055) ** 2.4
        )

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: str) -> float:
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


root = block(r":root")
light = block(r"\.card:not\(\.nightMode\):not\(\.night_mode\)")
themes = {
    "dark": (token(root, "--text-muted"), token(root, "--card-bg")),
    "light": (token(light, "--text-muted"), token(light, "--card-bg")),
}
contrast_failures = []
for name, (foreground, background) in themes.items():
    if not foreground or not background:
        contrast_failures.append(f"{name}: token missing")
        continue
    ratio = contrast(foreground, background)
    if ratio < 4.5:
        contrast_failures.append(f"{name}: {foreground} on {background} = {ratio:.2f}:1")

check(
    "contrast: muted text meets WCAG AA (4.5:1) in both themes",
    not contrast_failures,
    "; ".join(contrast_failures),
)

# --- 2. No opacity multipliers on quiet chrome ------------------------------
hint_bodies = bodies_containing(".shortcut-hints")
footer_bodies = bodies_containing(".source-footer")
opacity_offenders = [
    selector
    for selector, bodies in (
        (".shortcut-hints", hint_bodies),
        (".source-footer", footer_bodies),
    )
    if any(re.search(r"opacity\s*:", body) for body in bodies)
]
check(
    "contrast: no opacity multiplier on hint/footer text",
    bool(hint_bodies) and bool(footer_bodies) and not opacity_offenders,
    (
        "opacity on " + ", ".join(opacity_offenders)
        if opacity_offenders
        else "selector missing"
    ),
)

# --- 3. 12px floor for the smallest chrome labels --------------------------
LABEL_SELECTORS = (
    ".frequency-stars",
    ".shortcut-item",
    ".small-audio-btn .audio-btn-label",
)
below_floor = []
for selector in LABEL_SELECTORS:
    sizes = [token(body, "font-size") for body in bodies_for(selector)]
    sizes = [size for size in sizes if size]
    if not sizes or any(size != "0.75rem" for size in sizes):
        below_floor.append(f"{selector}: {sizes or 'missing'}")

check(
    "type: smallest chrome labels keep the 12px floor at every width",
    not below_floor,
    "; ".join(below_floor),
)

print()
if failures:
    print(f"{len(failures)} readability check(s) failed")
    sys.exit(1)
print("readability: OK")
