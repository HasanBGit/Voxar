"""Generate the voxar logo SVGs in ``assets/`` from one geometry definition.

The mark is a waveform inside a circle (voice); the wordmark is drawn from strokes, not from a
font, so it renders identically everywhere and needs no font license. Run:

    python scripts/make_logos.py          # rewrite assets/*.svg
    python scripts/make_logos.py --check  # exit 1 if the files on disk differ (used by a test)
"""

import sys
from pathlib import Path

ASSETS = Path(__file__).parent.parent / "assets"

# Palette: teal to indigo for the mark; slate wordmark on light pages, near-white on dark pages.
MARK_FROM, MARK_TO = "#0D9488", "#4F46E5"
MARK_FROM_DARK, MARK_TO_DARK = "#2DD4BF", "#818CF8"
INK_LIGHT, INK_DARK = "#0F172A", "#F1F5F9"

BAR_HEIGHTS = (22, 44, 70, 100, 70, 44, 22)  # a symmetric waveform
BAR_WIDTH, BAR_GAP = 11, 9


def mark(cx: float, cy: float, radius: float, gradient_id: str, bars: str) -> str:
    """The circular badge with the waveform bars, centered at (cx, cy)."""
    total = len(BAR_HEIGHTS) * BAR_WIDTH + (len(BAR_HEIGHTS) - 1) * BAR_GAP
    x = cx - total / 2
    rects = []
    for height in BAR_HEIGHTS:
        rects.append(
            f'<rect x="{x:.1f}" y="{cy - height / 2:.1f}" width="{BAR_WIDTH}" height="{height}" '
            f'rx="{BAR_WIDTH / 2}" fill="{bars}"/>'
        )
        x += BAR_WIDTH + BAR_GAP
    circle = f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="url(#{gradient_id})"/>'
    return circle + "".join(rects)


def wordmark(left: float, ink: str) -> str:
    """'voxar' in monoline strokes with round caps. Letters are 44 units tall (x-height)."""
    top, mid, bottom = 196, 213, 230  # stroke centerlines (outer edges are 5 units further out)
    paths = []

    def line(*points: tuple[float, float]) -> str:
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)
        return f'<path d="{d}"/>'

    x0 = left  # v
    paths.append(line((x0 + 5, top), (x0 + 22, bottom), (x0 + 39, top)))
    x0 += 60  # o
    paths.append(f'<circle cx="{x0 + 22}" cy="{mid}" r="17"/>')
    x0 += 60  # x
    paths.append(line((x0 + 5, top), (x0 + 39, bottom)))
    paths.append(line((x0 + 39, top), (x0 + 5, bottom)))
    x0 += 60  # a (single story: bowl and stem)
    paths.append(f'<circle cx="{x0 + 20}" cy="{mid}" r="17"/>')
    paths.append(line((x0 + 37, top), (x0 + 37, bottom)))
    x0 += 60  # r (stem and shoulder)
    paths.append(line((x0 + 6, top), (x0 + 6, bottom)))
    paths.append(f'<path d="M{x0 + 6} 216 Q{x0 + 6} {top} {x0 + 30} {top + 2}"/>')
    style = f'fill="none" stroke="{ink}" stroke-width="10" stroke-linecap="round"'
    return f'<g {style} stroke-linejoin="round">' + "".join(paths) + "</g>"


def gradient(gradient_id: str, start: str, end: str) -> str:
    return (
        f'<linearGradient id="{gradient_id}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{start}"/><stop offset="1" stop-color="{end}"/>'
        "</linearGradient>"
    )


def stacked(dark: bool) -> str:
    start, end = (MARK_FROM_DARK, MARK_TO_DARK) if dark else (MARK_FROM, MARK_TO)
    ink = INK_DARK if dark else INK_LIGHT
    bars = "#0B1220" if dark else "#FFFFFF"
    word_left = 240 - (4 * 60 + 41) / 2  # center the 5 letters (the last one is 41 wide)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 252" width="480" height="252" '
        'role="img" aria-label="voxar">'
        f"<title>voxar</title><defs>{gradient('g', start, end)}</defs>"
        f"{mark(240, 90, 78, 'g', bars)}{wordmark(word_left, ink)}</svg>\n"
    )


def icon(dark: bool) -> str:
    start, end = (MARK_FROM_DARK, MARK_TO_DARK) if dark else (MARK_FROM, MARK_TO)
    bars = "#0B1220" if dark else "#FFFFFF"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160" '
        'role="img" aria-label="voxar">'
        f"<title>voxar</title><defs>{gradient('g', start, end)}</defs>"
        f"{mark(80, 80, 78, 'g', bars)}</svg>\n"
    )


def files() -> dict[str, str]:
    return {
        "logo.svg": stacked(dark=False),
        "logo-dark.svg": stacked(dark=True),
        "logo-mark.svg": icon(dark=False),
        "logo-mark-dark.svg": icon(dark=True),
    }


def main(argv: list[str]) -> int:
    expected = files()
    if "--check" in argv:
        stale = [
            name
            for name, text in expected.items()
            if not (ASSETS / name).exists() or (ASSETS / name).read_text(encoding="utf-8") != text
        ]
        for name in stale:
            print(
                f"assets/{name} is out of date: run python scripts/make_logos.py", file=sys.stderr
            )
        return 1 if stale else 0
    ASSETS.mkdir(exist_ok=True)
    for name, text in expected.items():
        (ASSETS / name).write_text(text, encoding="utf-8")
        print(f"wrote assets/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
