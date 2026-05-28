"""Build an editable SVG (+ PNG) of the Independent Fiscal Council's roles.

Five stacked cards (icon badge + title + description) in the project's
purple palette. Pure-vector SVG so it can be dropped into PowerPoint
(Insert > Picture, then Convert to Shapes) and edited element by element.

Out: docu/fiscal_council_roles.svg / .png
"""
import os
import shutil
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_DIR = os.path.join(PROJECT_ROOT, "docu")
OUT_SVG = os.path.join(OUT_DIR, "fiscal_council_roles.svg")
OUT_PNG = os.path.join(OUT_DIR, "fiscal_council_roles.png")
PNG_WIDTH = 2560

# ---------------------------------------------------------------- palette
PURPLE = "#6A1B9A"
PURPLE_DARK = "#4A148C"
PURPLE_LT = "#CE93D8"
CARD_BG = "#F6EFFA"
BADGE_BG = "#FFFFFF"
TITLE_TXT = "#4A148C"
DESC_TXT = "#3A3A3A"
WHITE = "#FFFFFF"

# ---------------------------------------------------------------- geometry
W = 1280
M = 40
CARD_X = M
CARD_W = W - 2 * M
ACCENT_W = 6
BADGE_CX = M + 78
BADGE_R = 27
TEXT_X = M + 130
TEXT_W = CARD_X + CARD_W - 30 - TEXT_X
RX = 12

# Target print size 32 x 13 cm -> fix the canvas aspect (1280 x 520 px).
W_CM, H_CM = 32, 13
FIXED_H = round(W * H_CM / W_CM)
CARD_GAP = 11
TITLE_FS, DESC_FS, DESC_LH = 20, 16, 21
PAD_TOP, PAD_BOT, TITLE_DESC_GAP = 12, 13, 21
MAX_CHARS = 116

# ---------------------------------------------------------------- content
# (icon, title, description)
ROLES = [
    ("chart", "Macro-Fiscal Evaluation",
     "Mandated to evaluate the quality and realism of the macro-fiscal projections that "
     "underpin the Medium-Term Fiscal Framework and the SER formula."),
    ("flag", "Escape Clause Stewardship",
     "Monitors the activation and extension of escape clauses, assesses the costing of "
     "extraordinary measures, and oversees the return path to rule limits."),
    ("clipboard", "Compliance Oversight",
     "Provides detailed ex-ante and ex-post assessments of adherence to the SER, bridging "
     "the current gap in independent retrospective and prospective analysis."),
    ("shield", "Sustainability Safeguards",
     "Conducts regular debt sustainability analyses (DSA) to ensure national fiscal policy "
     "remains consistent with long-term objectives and the new EU framework."),
    ("building", "Institutional Autonomy",
     "Requires full operational independence and sufficient resources to provide an "
     "authoritative, “single voice” on fiscal transparency and discipline."),
]


# ---------------------------------------------------------------- helpers
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rrect(x, y, w, h, fill, rx=RX):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{rx}" ry="{rx}" fill="{fill}"/>')


def text(x, y, s, size, color, weight="normal", anchor="start"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{color}" '
            f'text-anchor="{anchor}">{esc(s)}</text>')


def wrap(s, max_chars):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if not cur or len(cur) + 1 + len(w) <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def icon(name, cx, cy):
    sw = 2.4
    c = (f'fill="none" stroke="{PURPLE}" stroke-width="{sw}" '
         f'stroke-linecap="round" stroke-linejoin="round"')
    if name == "chart":      # axes + upward trend
        return (f'<polyline points="{cx-12},{cy-12} {cx-12},{cy+12} {cx+13},{cy+12}" {c}/>'
                f'<polyline points="{cx-7},{cy+5} {cx-1},{cy-3} {cx+4},{cy+1} {cx+11},{cy-9}" {c}/>')
    if name == "flag":       # pole + pennant
        return (f'<line x1="{cx-9}" y1="{cy-13}" x2="{cx-9}" y2="{cy+13}" {c}/>'
                f'<path d="M {cx-9} {cy-13} L {cx+11} {cy-8} L {cx-9} {cy-2} Z" {c}/>')
    if name == "clipboard":  # board + clip + check
        return (f'<rect x="{cx-12}" y="{cy-11}" width="24" height="25" rx="3" {c}/>'
                f'<rect x="{cx-5}" y="{cy-16}" width="10" height="7" rx="2" {c}/>'
                f'<polyline points="{cx-6},{cy+2} {cx-1},{cy+7} {cx+7},{cy-4}" {c}/>')
    if name == "shield":     # shield + check
        return (f'<path d="M {cx} {cy-13} L {cx+11} {cy-8} L {cx+11} {cy+1} '
                f'Q {cx+11} {cy+10} {cx} {cy+13} Q {cx-11} {cy+10} {cx-11} {cy+1} '
                f'L {cx-11} {cy-8} Z" {c}/>'
                f'<polyline points="{cx-5},{cy} {cx-1},{cy+5} {cx+6},{cy-5}" {c}/>')
    if name == "building":   # classical institution facade
        return (f'<polyline points="{cx-13},{cy-5} {cx},{cy-14} {cx+13},{cy-5}" {c}/>'
                f'<line x1="{cx-13}" y1="{cy-5}" x2="{cx+13}" y2="{cy-5}" {c}/>'
                f'<line x1="{cx-9}" y1="{cy-5}" x2="{cx-9}" y2="{cy+9}" {c}/>'
                f'<line x1="{cx}" y1="{cy-5}" x2="{cx}" y2="{cy+9}" {c}/>'
                f'<line x1="{cx+9}" y1="{cy-5}" x2="{cx+9}" y2="{cy+9}" {c}/>'
                f'<line x1="{cx-13}" y1="{cy+11}" x2="{cx+13}" y2="{cy+11}" {c}/>')
    return ""


# ---------------------------------------------------------------- layout
def layout():
    """Return (cards, height). Cards are vertically centred in the fixed
    32:13 canvas. Each card: (y, h, icon, title, lines)."""
    sized, stack = [], 0
    for ic, title, desc in ROLES:
        lines = wrap(desc, MAX_CHARS)
        h = PAD_TOP + TITLE_FS + TITLE_DESC_GAP + (len(lines) - 1) * DESC_LH + PAD_BOT
        sized.append((h, ic, title, lines))
        stack += h
    stack += CARD_GAP * (len(sized) - 1)
    y = max((FIXED_H - stack) / 2, 0)
    cards = []
    for h, ic, title, lines in sized:
        cards.append((y, h, ic, title, lines))
        y += h + CARD_GAP
    return cards, FIXED_H


def build(canvas_h=None):
    cards, total_h = layout()
    H = canvas_h or total_h
    e = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}">']
    e.append(rrect(0, 0, W, H, WHITE, rx=0))
    for y, h, ic, title, lines in cards:
        cy = y + h / 2
        e.append(rrect(CARD_X, y, CARD_W, h, CARD_BG))
        e.append(rrect(CARD_X, y, ACCENT_W + RX, h, PURPLE))     # left accent
        e.append(rrect(CARD_X + ACCENT_W, y, RX, h, CARD_BG))    # mask accent's right round
        e.append(f'<circle cx="{BADGE_CX}" cy="{cy:.1f}" r="{BADGE_R}" '
                 f'fill="{BADGE_BG}" stroke="{PURPLE_LT}" stroke-width="1.6"/>')
        e.append(icon(ic, BADGE_CX, cy))
        e.append(text(TEXT_X, y + PAD_TOP + TITLE_FS, title, TITLE_FS, TITLE_TXT, "bold"))
        dy = y + PAD_TOP + TITLE_FS + TITLE_DESC_GAP
        for i, ln in enumerate(lines):
            e.append(text(TEXT_X, dy + i * DESC_LH, ln, DESC_FS, DESC_TXT))
    e.append("</svg>")
    return "\n".join(e)


def export_png(width=PNG_WIDTH):
    if not shutil.which("qlmanage"):
        print("PNG skipped: qlmanage not found (macOS only). SVG written.")
        return
    try:
        from PIL import Image
    except ImportError:
        print("PNG skipped: Pillow not installed. SVG written.")
        return
    _, H = layout()
    with tempfile.TemporaryDirectory() as td:
        sq = os.path.join(td, "sq.svg")
        with open(sq, "w", encoding="utf-8") as f:
            f.write(build(canvas_h=W))          # square canvas keeps full width
        subprocess.run(["qlmanage", "-t", "-s", str(width), "-o", td, sq],
                       capture_output=True, check=False)
        thumb = os.path.join(td, "sq.svg.png")
        if not os.path.exists(thumb):
            print("PNG skipped: qlmanage produced no thumbnail. SVG written.")
            return
        im = Image.open(thumb)
        w, _ = im.size
        im.crop((0, 0, w, round(w * H / W))).save(OUT_PNG)
    print(f"Wrote {OUT_PNG}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_SVG, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"Wrote {OUT_SVG}")
    export_png()


if __name__ == "__main__":
    main()
