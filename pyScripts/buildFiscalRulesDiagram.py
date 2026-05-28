"""Build an editable SVG of the SER v1.0 vs. SER v2.0 fiscal-rules comparison.

Reproduces the one-page "Upgraded Framework" summary as a pure-vector SVG so it
can be dropped into PowerPoint (Insert > Picture, then right-click > Convert to
Shapes) and edited element by element. Icons are drawn as vector paths, not
embedded images, so they stay editable too.

Out: docu/fiscal_rules_ser_comparison.svg
"""
import os
import shutil
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_DIR = os.path.join(PROJECT_ROOT, "docu")
OUT_SVG = os.path.join(OUT_DIR, "fiscal_rules_ser_comparison.svg")
OUT_PNG = os.path.join(OUT_DIR, "fiscal_rules_ser_comparison.png")
PNG_WIDTH = 2560  # ~2x of the 1280-wide canvas, matching the project's scale=2

# ---------------------------------------------------------------- palette
# On-brand: purple = current (v1.0), teal-green = upgraded (v2.0).
GRAY_TXT = "#5A5A5A"
CELL_TXT = "#2A2A2A"

DIM_HDR_BG = "#C9CDD4"
DIM_CELL_BG = "#ECEEF1"
V1_HDR_BG = "#6A1B9A"      # purple = current
V1_HDR_TXT = "#FFFFFF"
V1_CELL_BG = "#F3EAF8"
V1_ICON = "#6A1B9A"
V2_HDR_BG = "#00897B"      # teal-green = upgraded / EU-aligned
V2_HDR_TXT = "#FFFFFF"
V2_CELL_BG = "#E3F2EF"
V2_ICON = "#00897B"

WARN = "#6A1B9A"           # purple marker on current column
CHECK = "#00897B"          # teal check on upgraded column
WHITE = "#FFFFFF"

# ---------------------------------------------------------------- geometry
# Target print size 32 x 13 cm -> fix the canvas aspect (1280 x 520 px).
W_CM, H_CM = 32, 13
W = 1280
H = round(W * H_CM / W_CM)     # 520
M = 40
DIM_X, DIM_W = M, 220
GAP = 16
V1_X = DIM_X + DIM_W + GAP
V1_W = 466
V2_X = V1_X + V1_W + GAP
V2_W = W - M - V2_X            # fills to right margin
HDR_Y, HDR_H = 16, 46
ROW_Y0, ROW_H, ROW_GAP = 72, 80, 8
RX = 10

# ---------------------------------------------------------------- rows
# (dimension, v1_icon, [v1 lines], v2_icon, [v2 lines])
ROWS = [
    ("Time Horizon", "clock", ["1-year binding limit"],
     "calendar", ["Multi-year binding limit", "aligned with EU path"]),
    ("Growth Formula", "arrow_back", ["Largely backward-looking average", "(t–6 to t+1)"],
     "arrow_fwd", ["3-year forward projection +", "error correction"]),
    ("Coverage", "arc70", ["~70% binding with", "off-budget leaks"],
     "shield", ["Broadened ESA 2010 alignment", "(including securities transfers)"]),
    ("Oversight", "magnifier", ["Ex-post NIK legal audit only"],
     "badge", ["Ex-ante & Ex-post Independent", "Fiscal Council validation"]),
    ("Shock Response", "bolt", ["Ad-hoc amendments /", "Epidemic trigger"],
     "target", ["Standalone recession trigger +", "debt-linked return trajectory"]),
]


# ---------------------------------------------------------------- helpers
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rrect(x, y, w, h, fill, rx=RX, stroke="none", sw=0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke != "none" else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" ry="{rx}" fill="{fill}"{s}/>'


def text(x, y, s, size, color, weight="normal", anchor="start"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{color}" '
            f'text-anchor="{anchor}">{esc(s)}</text>')


def multiline(x, cy, lines, size, color):
    """Left-aligned, vertically centred block of lines."""
    lh = size + 6
    total = lh * len(lines)
    start = cy - total / 2 + size  # first baseline
    out = []
    for i, ln in enumerate(lines):
        out.append(text(x, start + i * lh, ln, size, color))
    return "".join(out)


# ---- vector icons (drawn around centre cx, cy) -------------------------
def icon(name, cx, cy, color):
    sw = 2.6
    common = f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
    if name == "clock":
        return (f'<circle cx="{cx}" cy="{cy}" r="13" {common}/>'
                f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy-8}" {common}/>'
                f'<line x1="{cx}" y1="{cy}" x2="{cx+6}" y2="{cy+3}" {common}/>')
    if name == "calendar":
        return (f'<rect x="{cx-13}" y="{cy-10}" width="26" height="23" rx="3" {common}/>'
                f'<line x1="{cx-13}" y1="{cy-3}" x2="{cx+13}" y2="{cy-3}" {common}/>'
                f'<line x1="{cx-7}" y1="{cy-15}" x2="{cx-7}" y2="{cy-7}" {common}/>'
                f'<line x1="{cx+7}" y1="{cy-15}" x2="{cx+7}" y2="{cy-7}" {common}/>')
    if name == "arrow_back":
        return (f'<line x1="{cx+13}" y1="{cy}" x2="{cx-11}" y2="{cy}" {common}/>'
                f'<polyline points="{cx-4},{cy-7} {cx-11},{cy} {cx-4},{cy+7}" {common}/>')
    if name == "arrow_fwd":
        return (f'<line x1="{cx-13}" y1="{cy}" x2="{cx+11}" y2="{cy}" {common}/>'
                f'<polyline points="{cx+4},{cy-7} {cx+11},{cy} {cx+4},{cy+7}" {common}/>')
    if name == "arc70":   # ~270deg arc = partial coverage
        import math
        a0, a1 = -60, 240
        x0 = cx + 13 * math.cos(math.radians(a0))
        y0 = cy - 13 * math.sin(math.radians(a0))
        x1 = cx + 13 * math.cos(math.radians(a1))
        y1 = cy - 13 * math.sin(math.radians(a1))
        return f'<path d="M {x0:.1f} {y0:.1f} A 13 13 0 1 0 {x1:.1f} {y1:.1f}" {common}/>'
    if name == "shield":
        return (f'<path d="M {cx} {cy-13} L {cx+11} {cy-8} L {cx+11} {cy+1} '
                f'Q {cx+11} {cy+10} {cx} {cy+13} Q {cx-11} {cy+10} {cx-11} {cy+1} '
                f'L {cx-11} {cy-8} Z" {common}/>'
                f'<polyline points="{cx-5},{cy} {cx-1},{cy+5} {cx+6},{cy-5}" {common}/>')
    if name == "magnifier":
        return (f'<circle cx="{cx-3}" cy="{cy-3}" r="9" {common}/>'
                f'<line x1="{cx+4}" y1="{cy+4}" x2="{cx+12}" y2="{cy+12}" {common}/>')
    if name == "badge":
        return (f'<circle cx="{cx}" cy="{cy}" r="13" {common}/>'
                f'<polyline points="{cx-6},{cy} {cx-2},{cy+5} {cx+7},{cy-6}" {common}/>')
    if name == "bolt":
        return (f'<polygon points="{cx+3},{cy-13} {cx-9},{cy+2} {cx-1},{cy+2} '
                f'{cx-3},{cy+13} {cx+9},{cy-2} {cx+1},{cy-2}" '
                f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"/>')
    if name == "target":
        return (f'<circle cx="{cx}" cy="{cy}" r="13" {common}/>'
                f'<circle cx="{cx}" cy="{cy}" r="6.5" {common}/>'
                f'<circle cx="{cx}" cy="{cy}" r="1.6" fill="{color}" stroke="none"/>')
    return ""


def warn_mark(x, cy):
    """Amber warning triangle with '!'."""
    p = f'{x},{cy-9} {x+10},{cy+8} {x-10},{cy+8}'
    return (f'<polygon points="{p}" fill="{WARN}" stroke="none"/>'
            f'<line x1="{x}" y1="{cy-3}" x2="{x}" y2="{cy+3}" stroke="{WHITE}" stroke-width="2" stroke-linecap="round"/>'
            f'<circle cx="{x}" cy="{cy+6}" r="1.3" fill="{WHITE}"/>')


def check_mark(x, cy):
    """Green filled circle with check."""
    return (f'<circle cx="{x}" cy="{cy}" r="10" fill="{CHECK}" stroke="none"/>'
            f'<polyline points="{x-5},{cy} {x-1.5},{cy+4} {x+5},{cy-4}" '
            f'fill="none" stroke="{WHITE}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')


def up_right_arrow(x, y, color):
    return (f'<line x1="{x-7}" y1="{y+7}" x2="{x+7}" y2="{y-7}" stroke="{color}" '
            f'stroke-width="2.4" stroke-linecap="round"/>'
            f'<polyline points="{x+1},{y-7} {x+7},{y-7} {x+7},{y-1}" fill="none" '
            f'stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')


# ---------------------------------------------------------------- build
def build(canvas_h=H):
    """Return the SVG. canvas_h > H pads white space below (used only to
    coax qlmanage, which renders into a square, to keep the full width)."""
    e = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{canvas_h}" '
         f'viewBox="0 0 {W} {canvas_h}">']
    e.append(rrect(0, 0, W, canvas_h, WHITE, rx=0))

    # header row
    e.append(rrect(DIM_X, HDR_Y, DIM_W, HDR_H, DIM_HDR_BG))
    e.append(text(DIM_X + DIM_W / 2, HDR_Y + HDR_H / 2 + 6, "System Dimension",
                  17, "#2B2B2B", "bold", "middle"))
    e.append(rrect(V1_X, HDR_Y, V1_W, HDR_H, V1_HDR_BG))
    e.append(text(V1_X + V1_W / 2, HDR_Y + 21, "SER v1.0", 18, V1_HDR_TXT, "bold", "middle"))
    e.append(text(V1_X + V1_W / 2, HDR_Y + 38, "(Current)", 12, V1_HDR_TXT, "normal", "middle"))
    e.append(up_right_arrow(V1_X + V1_W - 20, HDR_Y + 16, "#D9B8E8"))
    e.append(rrect(V2_X, HDR_Y, V2_W, HDR_H, V2_HDR_BG))
    e.append(text(V2_X + V2_W / 2, HDR_Y + 21, "SER v2.0", 18, V2_HDR_TXT, "bold", "middle"))
    e.append(text(V2_X + V2_W / 2, HDR_Y + 38, "(Upgraded & more EU-aligned)", 12, V2_HDR_TXT, "normal", "middle"))
    e.append(up_right_arrow(V2_X + V2_W - 20, HDR_Y + 16, "#A7D8D0"))

    # data rows
    for r, (dim, v1ic, v1tx, v2ic, v2tx) in enumerate(ROWS):
        y = ROW_Y0 + r * (ROW_H + ROW_GAP)
        cy = y + ROW_H / 2
        # dimension cell
        e.append(rrect(DIM_X, y, DIM_W, ROW_H, DIM_CELL_BG))
        e.append(text(DIM_X + DIM_W / 2, cy + 6, dim, 17, CELL_TXT, "bold", "middle"))
        # v1 cell
        e.append(rrect(V1_X, y, V1_W, ROW_H, V1_CELL_BG))
        e.append(icon(v1ic, V1_X + 34, cy, V1_ICON))
        e.append(multiline(V1_X + 64, cy, v1tx, 18, CELL_TXT))
        e.append(warn_mark(V1_X + V1_W - 28, cy))
        # v2 cell
        e.append(rrect(V2_X, y, V2_W, ROW_H, V2_CELL_BG))
        e.append(icon(v2ic, V2_X + 34, cy, V2_ICON))
        e.append(multiline(V2_X + 64, cy, v2tx, 18, CELL_TXT))
        e.append(check_mark(V2_X + V2_W - 26, cy))

    e.append("</svg>")
    return "\n".join(e)


def export_png(width=PNG_WIDTH):
    """Rasterise the SVG to PNG via macOS qlmanage (WebKit), then crop the
    square thumbnail back to the diagram's aspect. Skips with a note if
    qlmanage or Pillow are unavailable (e.g. non-macOS)."""
    if not shutil.which("qlmanage"):
        print("PNG skipped: qlmanage not found (macOS only). SVG written.")
        return
    try:
        from PIL import Image
    except ImportError:
        print("PNG skipped: Pillow not installed. SVG written.")
        return
    with tempfile.TemporaryDirectory() as td:
        # Square canvas so qlmanage's square thumbnail keeps the full width.
        sq_svg = os.path.join(td, "sq.svg")
        with open(sq_svg, "w", encoding="utf-8") as f:
            f.write(build(canvas_h=W))
        subprocess.run(["qlmanage", "-t", "-s", str(width), "-o", td, sq_svg],
                       capture_output=True, check=False)
        thumb = os.path.join(td, "sq.svg.png")
        if not os.path.exists(thumb):
            print("PNG skipped: qlmanage produced no thumbnail. SVG written.")
            return
        im = Image.open(thumb)
        w, _ = im.size
        crop_h = round(w * H / W)
        im.crop((0, 0, w, crop_h)).save(OUT_PNG)
    print(f"Wrote {OUT_PNG}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_SVG, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"Wrote {OUT_SVG}")
    export_png()


if __name__ == "__main__":
    main()
