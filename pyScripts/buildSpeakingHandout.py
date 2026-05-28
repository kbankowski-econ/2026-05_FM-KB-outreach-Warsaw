"""Build a speaker-notes handout PDF that interleaves slides with their notes.

Inputs (paths relative to repo root):
  docu/2026-05_FM-outreach_PL-fiscal-council.pdf
  docu/2026-05_FM-outreach_PL-fiscal-council_speaking.md

Output:
  docu/2026-05_FM-outreach_PL-fiscal-council_speaking.pdf

Each output page contains: Slide N image (top, full text width), then the
parsed speaker notes for that slide below. Slides without notes show
"(no notes)".
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pdfplumber

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PRES_PDF = REPO_ROOT / "docu/2026-05_FM-outreach_PL-fiscal-council.pdf"
NOTES_MD = REPO_ROOT / "docu/2026-05_FM-outreach_PL-fiscal-council_speaking.md"
OUT_PDF = REPO_ROOT / "docu/2026-05_FM-outreach_PL-fiscal-council_speaking.pdf"

# Lenient heading match: "Slide N", "SLIDE N", "Next N" (typos exist in the source).
HEADER_RE = re.compile(r'^\s*(?:slide|next)\s+(\d+)\s*$', re.IGNORECASE)


def parse_notes(md_path: Path) -> dict[int, str]:
    """Return {slide_num: notes_text} parsed from the speaking-notes markdown."""
    notes: dict[int, str] = {}
    current: int | None = None
    buffer: list[str] = []
    for line in md_path.read_text(encoding="utf-8").splitlines():
        m = HEADER_RE.match(line)
        if m:
            if current is not None:
                notes[current] = "\n".join(buffer).strip()
            current = int(m.group(1))
            buffer = []
        else:
            buffer.append(line)
    if current is not None:
        notes[current] = "\n".join(buffer).strip()
    return notes


def latex_escape(text: str) -> str:
    """Escape LaTeX specials and translate common Unicode punctuation."""
    # Unicode-to-LaTeX before backslash handling
    unicode_map = [
        ("‘", "`"), ("’", "'"),
        ("“", "``"), ("”", "''"),
        ("–", "--"), ("—", "---"),
        ("…", r"\ldots{}"),
        (" ", "~"),  # non-breaking space
    ]
    for a, b in unicode_map:
        text = text.replace(a, b)

    # Stash literal backslashes behind a sentinel so subsequent escapes don't
    # double-process them, then escape special chars, then restore as
    # \textbackslash{}.
    SENTINEL = "\x00BSLASH\x00"
    text = text.replace("\\", SENTINEL)
    for ch, repl in [
        ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
        ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
        ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]:
        text = text.replace(ch, repl)
    text = text.replace(SENTINEL, r"\textbackslash{}")
    return text


# Markdown bold (**...**), italic (*...*), and <span style="color:NAME">…</span> — non-greedy.
_SPAN_RE = re.compile(r'<span style="color:([^"]+)">(.*?)</span>', re.DOTALL)
_MD_INLINE_RE = re.compile(r"(\*\*[^\*]+?\*\*|\*[^\*]+?\*)")


def render_inline(text: str) -> str:
    """Render a markdown-flavoured paragraph: **bold**, *italic*, colored spans, plain text."""

    def render_md(segment: str) -> str:
        out = []
        for token in _MD_INLINE_RE.split(segment):
            if not token:
                continue
            if token.startswith("**") and token.endswith("**"):
                out.append(r"\textbf{" + latex_escape(token[2:-2]) + "}")
            elif token.startswith("*") and token.endswith("*"):
                out.append(r"\textit{" + latex_escape(token[1:-1]) + "}")
            else:
                out.append(latex_escape(token))
        return "".join(out)

    parts = []
    pos = 0
    for m in _SPAN_RE.finditer(text):
        parts.append(render_md(text[pos:m.start()]))
        color = m.group(1).strip()
        inner = render_md(m.group(2))
        parts.append(r"\textcolor{" + color + "}{" + inner + "}")
        pos = m.end()
    parts.append(render_md(text[pos:]))
    return "".join(parts)


def render_notes(text: str) -> str:
    """Convert markdown-lite notes to LaTeX.

    Supports blank-line paragraph breaks, lines starting with '- ' (bulleted
    block → itemize), and inline **bold** / *italic*.
    """
    if not text.strip():
        return r"\textit{(no notes)}"
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    rendered: list[str] = []
    for block in blocks:
        lines = block.splitlines()
        if all(line.lstrip().startswith("- ") for line in lines):
            items = [render_inline(line.lstrip()[2:].strip()) for line in lines]
            body = "\n".join(f"  \\item {item}" for item in items)
            rendered.append(
                "\\begin{itemize}\n"
                "  \\setlength{\\itemsep}{0.3em}\n"
                f"{body}\n"
                "\\end{itemize}"
            )
        else:
            rendered.append(render_inline(" ".join(lines)))
    return "\n\\par\\medskip\n".join(rendered)


# Font preference order. The first font installed system-wide on the build
# machine wins. Segoe UI isn't a system font on macOS (Office only ships .woff
# variants inside app bundles, which xelatex can't load), so Calibri — also a
# Microsoft humanist sans-serif and bundled with Office for Mac — is the
# closest available substitute.
FONT_PREFERENCE = ["Avenir Next", "Segoe UI", "Calibri", "Helvetica Neue", "Helvetica"]


def pick_main_font() -> str:
    """Return the first font from FONT_PREFERENCE that's available locally."""
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONT_PREFERENCE:
        if name in available:
            return name
    return FONT_PREFERENCE[-1]


def build_tex(num_pages: int, notes: dict[int, str], pdf_filename: str,
              main_font: str) -> str:
    """Generate the LaTeX source for the handout."""
    parts: list[str] = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[margin=1.5cm]{geometry}",
        r"\usepackage{graphicx}",
        r"\usepackage{microtype}",
        r"\usepackage[svgnames]{xcolor}",
        r"\usepackage{fontspec}",
        f"\\setmainfont{{{main_font}}}",
        f"\\setsansfont{{{main_font}}}",
        r"\renewcommand{\familydefault}{\sfdefault}",
        r"\definecolor{NotesGrey}{RGB}{60,60,60}",
        r"\definecolor{royalblue}{HTML}{4169E1}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{0.5em}",
        r"\pagestyle{plain}",
        r"\begin{document}",
    ]
    for n in range(1, num_pages + 1):
        body = render_notes(notes.get(n, ""))
        parts.extend([
            f"\\section*{{Slide {n}}}",
            "\\begin{center}",
            f"\\includegraphics[page={n},width=\\linewidth,keepaspectratio]{{{pdf_filename}}}",
            "\\end{center}",
            r"\par\bigskip",
            r"\textbf{Speaker notes}\par\smallskip",
            r"{\color{NotesGrey} " + body + r"}",
        ])
        if n < num_pages:
            parts.append(r"\newpage")
    parts.append(r"\end{document}")
    return "\n".join(parts) + "\n"


def main() -> None:
    if not PRES_PDF.exists():
        raise FileNotFoundError(f"Presentation PDF not found: {PRES_PDF}")
    if not NOTES_MD.exists():
        raise FileNotFoundError(f"Notes file not found: {NOTES_MD}")

    notes = parse_notes(NOTES_MD)
    with pdfplumber.open(PRES_PDF) as pdf:
        n_pages = len(pdf.pages)
    main_font = pick_main_font()
    print(f"Slides: {n_pages}; notes provided for slides: {sorted(notes)}")
    print(f"Using font: {main_font}")

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    # All pdflatex intermediates live in a temp directory and are discarded
    # after compilation; only the final PDF is written under docu/.
    with tempfile.TemporaryDirectory(prefix="speaking_handout_") as tmp_str:
        tmpdir = Path(tmp_str)
        shutil.copy(PRES_PDF, tmpdir / PRES_PDF.name)
        tex_path = tmpdir / "speaking_handout.tex"
        tex_path.write_text(
            build_tex(n_pages, notes, PRES_PDF.name, main_font), encoding="utf-8")
        # xelatex (not pdflatex) is required for fontspec / system fonts.
        result = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tmpdir, capture_output=True, text=True,
        )
        built_pdf = tmpdir / "speaking_handout.pdf"
        if not built_pdf.exists():
            tail = "\n".join(result.stdout.splitlines()[-30:])
            raise RuntimeError(f"pdflatex failed:\n{tail}")
        shutil.copy(built_pdf, OUT_PDF)
    print(f"Wrote {OUT_PDF}")


if __name__ == "__main__":
    main()
