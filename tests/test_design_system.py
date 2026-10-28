#!/usr/bin/env python3
"""Design-system invariants adapted from the landing-page-design skill.

The upstream skill (vendored at .opencode/skills/landing-page-design/) is a
landing-page system. Only its transferable Part B visual rules apply to a
flashcard; the full rule-by-rule scope is recorded in
docs/design/VISUAL_SYSTEM.md.

These checks run against the real stylesheet, stdlib only:
  - motion resolves through the shared tokens (no browser-default easing)
  - every interactive control has focus + press states
  - no single-sided card borders
  - radii stay on the Tailwind scale
  - UI chrome labels use one fixed 12px step
  - muted text meets WCAG AA against the surface it sits on
  - CJK body copy opts into text-wrap pretty/balance
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

# Top-level rule scanner. At-rule wrappers carry no declarations, so their
# inner rules match individually; @keyframes steps match as harmless rules.
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
    body = match.group(2)
    RULES.append(([s for s in selectors if s], body))


def bodies_for(exact: str) -> list[str]:
    """Bodies of rules whose selector list contains exactly `exact`."""
    return [body for selectors, body in RULES if exact in selectors]


def body_for(exact: str) -> str:
    found = bodies_for(exact)
    return found[0] if found else ""


def bodies_ending_with(suffix: str) -> list[str]:
    return [
        body
        for selectors, body in RULES
        if any(selector.endswith(suffix) for selector in selectors)
    ]


def block(pattern: str) -> str:
    match = re.search(pattern + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else ""


def token(body: str, name: str) -> str | None:
    match = re.search(rf"{re.escape(name)}\s*:\s*([^;]+);", body)
    return match.group(1).strip() if match else None


# --- 1. Motion tokens -------------------------------------------------------
root = block(r":root")

check(
    "motion: single decelerating curve token",
    token(root, "--ease-settle") == "cubic-bezier(0.22, 1, 0.36, 1)",
    f"--ease-settle={token(root, '--ease-settle')!r}",
)
check(
    "motion: hover + settle duration tokens",
    token(root, "--motion-hover") == "200ms"
    and token(root, "--motion-settle") == "300ms",
    f"hover={token(root, '--motion-hover')!r}, settle={token(root, '--motion-settle')!r}",
)

# --- 2. Every transition resolves through the tokens ------------------------
RAW_EASING = re.compile(
    r"(?<![-\w])(ease-in-out|ease-in|ease-out|ease|linear|step-start|step-end)(?![-\w])"
)
DURATION = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)(?![\w.])")
RING_EXCEPTION = ".audio-progress-ring .ring-fill"

bad_transitions: list[str] = []
for selectors, body in RULES:
    if RING_EXCEPTION in selectors:
        continue  # decorative playback stroke: functional, not UI motion
    for declaration in re.findall(r"transition\s*:\s*([^;]+);", body):
        for part in re.split(r",(?![^(]*\))", declaration):
            if RAW_EASING.search(part):
                bad_transitions.append(f"{', '.join(selectors)}: {part.strip()}")
            for value, unit in DURATION.findall(part):
                seconds = float(value) / 1000 if unit == "ms" else float(value)
                if seconds < 0.2:
                    bad_transitions.append(
                        f"{', '.join(selectors)}: {part.strip()} (<200ms)"
                    )
            if "var(--motion-" not in part or "var(--ease-settle)" not in part:
                bad_transitions.append(
                    f"{', '.join(selectors)}: {part.strip()} (untokenised)"
                )
check(
    "motion: no raw easing, no sub-200ms hover, all tokenised",
    not bad_transitions,
    "; ".join(sorted(set(bad_transitions))[:6]),
)

# --- 3. Border discipline ---------------------------------------------------
secondary = body_for(".secondary-block")
check(
    "borders: .secondary-block has no single-sided border",
    secondary != "" and not re.search(r"border-(top|right|bottom|left)\s*:", secondary),
    "found a one-sided border",
)

# --- 4. Focus + press states ------------------------------------------------
definition_focus = [
    body
    for body in bodies_ending_with(".definition-box.primary-definition:focus-visible")
]
check(
    "states: clickable definition has a visible focus ring",
    any("outline:" in body for body in definition_focus),
    "missing .definition-box.primary-definition:focus-visible outline",
)

press_controls = [
    ".more-toggle:active",
    ".translation-box:active",
    ".circular-audio-btn:active",
    ".shortcut-item:active",
    ".picture-container img:active",
    ".scenic-photo:active img",
]
missing_press = [
    selector
    for selector in press_controls
    if not any(
        re.search(r"transform\s*:", body) for body in bodies_ending_with(selector)
    )
]
check(
    "states: every interactive control has press feedback",
    not missing_press,
    f"missing transform on {', '.join(missing_press)}",
)

# --- 5. Radius scale --------------------------------------------------------
RADIUS_STEPS = {0, 2, 4, 6, 8, 12, 16, 24, 9999}
radius_tokens = {
    name: token(root, name)
    for name in ("--border-radius-lg", "--border-radius-md", "--border-radius-sm")
}
bad_radius_tokens = {
    name: value
    for name, value in radius_tokens.items()
    if value is None or not re.fullmatch(r"\d+px", value)
    or int(value.removesuffix("px")) not in RADIUS_STEPS
}
check(
    "radius: tokens snap to the Tailwind scale",
    not bad_radius_tokens,
    f"{bad_radius_tokens}",
)

bad_radius_literals: list[str] = []
for selectors, body in RULES:
    for declaration in re.findall(r"(?<![\w-])border-radius\s*:\s*([^;]+);", body):
        for part in declaration.split():
            px = re.fullmatch(r"(\d+)px", part)
            if px and int(px.group(1)) not in RADIUS_STEPS:
                bad_radius_literals.append(f"{', '.join(selectors)}: {part}")
check(
    "radius: no off-scale literal radii",
    not bad_radius_literals,
    "; ".join(sorted(set(bad_radius_literals))[:6]),
)

# --- 6. Chrome label scale --------------------------------------------------
check(
    "type: one 12px chrome label token",
    token(root, "--text-label") == "0.75rem",
    f"--text-label={token(root, '--text-label')!r}",
)
label_selectors = [
    ".more-toggle",
    ".frequency-badge",
    ".frequency-stars",
    ".translation-hint",
    ".source-footer",
    ".extended-def-header",
    ".shortcut-item",
]
off_scale_labels = [
    selector
    for selector in label_selectors
    if token(body_for(selector), "font-size") != "var(--text-label)"
]
check(
    "type: chrome labels use the shared step",
    not off_scale_labels,
    f"off-scale: {', '.join(off_scale_labels)}",
)

# --- 7. Text contrast -------------------------------------------------------
def luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: str) -> float:
    high, low = sorted(
        (luminance(foreground), luminance(background)), reverse=True
    )
    return (high + 0.05) / (low + 0.05)


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

# Opacity multipliers would undo the token contrast; keep them off text.
check(
    "contrast: no opacity multiplier on hint/footer text",
    not re.search(r"opacity\s*:", body_for(".shortcut-hints"))
    and not re.search(r"opacity\s*:", body_for(".source-footer")),
    "opacity on .shortcut-hints/.source-footer",
)

# --- 8. CJK line-breaking ---------------------------------------------------
check(
    "type: CJK body copy opts into pretty/balance wrapping",
    "text-wrap: pretty" in body_for(".definition-box")
    and "text-wrap: pretty" in body_for(".sentence-japanese")
    and "text-wrap: balance" in body_for(".word-display"),
    "missing text-wrap on .definition-box/.sentence-japanese/.word-display",
)

print()
if failures:
    print(f"{len(failures)} design-system check(s) failed")
    sys.exit(1)
print("design-system: OK")
