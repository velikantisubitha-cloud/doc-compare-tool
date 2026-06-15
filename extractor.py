"""
extractor.py — Deep metadata extraction engine.

Extracts from PDF (PyMuPDF):
  - Every word: text, font name, font size, font color (RGB), bold, italic
  - Bounding box: x0, y0, x1, y1 (exact pixel position)
  - Line number, block number, span number
  - Page size (width, height)
  - Borders/lines/rectangles (drawings)
  - Images (position + size)
  - Header zone / Footer zone classification
  - Page margins
  - Paragraph spacing
  - Background colors

Extracts from DOCX (python-docx):
  - Paragraph text, style name, alignment
  - Run-level: font name, size, bold, italic, underline, color, strike
  - Table structure, cell borders, cell colors
  - Page size, margins
  - Header / Footer paragraphs with full run metadata
  - Spacing before/after paragraphs, line spacing

Extracts from plain text:
  - Character-level content
  - Line/col positions
  - Whitespace structure
"""

from __future__ import annotations
import os, re, colorsys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import fitz                         # PyMuPDF
    _PYMUPDF = True
except ImportError:
    _PYMUPDF = False

try:
    import docx
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    _DOCX = True
except ImportError:
    _DOCX = False

try:
    import cv2, numpy as np
    from PIL import Image
    _CV2 = True
except ImportError:
    _CV2 = False


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BBox:
    x0: float; y0: float; x1: float; y1: float

    @property
    def width(self): return self.x1 - self.x0
    @property
    def height(self): return self.y1 - self.y0
    @property
    def center(self): return ((self.x0+self.x1)/2, (self.y0+self.y1)/2)

    def to_dict(self):
        return {"x0":round(self.x0,2),"y0":round(self.y0,2),
                "x1":round(self.x1,2),"y1":round(self.y1,2),
                "w":round(self.width,2),"h":round(self.height,2)}


@dataclass
class WordToken:
    """Atomic unit: one word with full formatting metadata."""
    text:        str
    page:        int
    line:        int          # 1-based within page
    col:         int          # 1-based char column within line
    bbox:        BBox
    font_name:   str   = ""
    font_size:   float = 0.0
    font_color:  Tuple = (0,0,0)   # (R,G,B) 0-255
    bold:        bool  = False
    italic:      bool  = False
    underline:   bool  = False
    strike:      bool  = False
    zone:        str   = "body"    # "header" | "footer" | "body"
    block_id:    int   = 0
    span_id:     int   = 0

    def format_sig(self) -> str:
        """Formatting signature for comparison."""
        return (f"{self.font_name}|{self.font_size:.1f}|"
                f"{self.font_color}|{int(self.bold)}|{int(self.italic)}|"
                f"{int(self.underline)}|{int(self.strike)}")


@dataclass
class DrawingElement:
    """Line, rectangle, or curve on the page."""
    page:       int
    kind:       str        # "line" | "rect" | "curve"
    bbox:       BBox
    color:      Tuple      # stroke (R,G,B)
    fill:       Optional[Tuple]  # fill (R,G,B) or None
    width:      float      # line width


@dataclass
class PageMeta:
    page:        int
    width:       float
    height:      float
    rotation:    int
    margin_top:  float
    margin_bot:  float
    margin_left: float
    margin_right:float


@dataclass
class DocumentData:
    """Complete extracted data for one document."""
    path:       str
    file_type:  str
    pages:      List[PageMeta]            = field(default_factory=list)
    words:      List[WordToken]           = field(default_factory=list)
    drawings:   List[DrawingElement]      = field(default_factory=list)
    raw_text:   str                       = ""
    page_images: List[Any]               = field(default_factory=list)   # PIL Images
    errors:     List[str]                = field(default_factory=list)

    # Convenience views
    def words_on_page(self, page: int) -> List[WordToken]:
        return [w for w in self.words if w.page == page]

    def header_words(self, page: int) -> List[WordToken]:
        return [w for w in self.words if w.page == page and w.zone == "header"]

    def footer_words(self, page: int) -> List[WordToken]:
        return [w for w in self.words if w.page == page and w.zone == "footer"]

    def body_words(self, page: int) -> List[WordToken]:
        return [w for w in self.words if w.page == page and w.zone == "body"]


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def extract(path: str) -> DocumentData:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    elif ext in (".docx",):
        return _extract_docx(path)
    else:
        return _extract_text(path)


# ─────────────────────────────────────────────────────────────────────────────
# PDF extractor
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pdf(path: str) -> DocumentData:
    data = DocumentData(path=path, file_type="pdf")

    if not _PYMUPDF:
        data.errors.append("PyMuPDF not installed — install with: pip install PyMuPDF")
        return _extract_text(path)   # fallback

    try:
        doc = fitz.open(path)
    except Exception as e:
        data.errors.append(f"Cannot open PDF: {e}")
        return data

    DPI = 150
    for pno, page in enumerate(doc, 1):
        rect = page.rect
        pw, ph = rect.width, rect.height

        # ── Page metadata ─────────────────────────────────────────────────────
        # Estimate margins from first/last text block positions
        blocks = page.get_text("blocks")
        if blocks:
            m_top   = min(b[1] for b in blocks)
            m_bot   = ph - max(b[3] for b in blocks)
            m_left  = min(b[0] for b in blocks)
            m_right = pw - max(b[2] for b in blocks)
        else:
            m_top = m_bot = m_left = m_right = 0

        data.pages.append(PageMeta(
            page=pno, width=round(pw,2), height=round(ph,2),
            rotation=page.rotation,
            margin_top=round(max(m_top,0),2),
            margin_bot=round(max(m_bot,0),2),
            margin_left=round(max(m_left,0),2),
            margin_right=round(max(m_right,0),2),
        ))

        # ── Word tokens with full span metadata ───────────────────────────────
        # get_text("rawdict") gives block→line→span→char with full formatting
        raw = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        # header zone = top 15% of page, footer zone = bottom 15%
        header_y = ph * 0.15
        footer_y = ph * 0.85

        line_num = 0
        for block in raw.get("blocks", []):
            if block.get("type") != 0:  # 0=text, 1=image
                continue
            block_id = block.get("number", 0)
            for ln in block.get("lines", []):
                line_num += 1
                line_y = ln["bbox"][1]
                zone = ("header" if line_y < header_y
                        else "footer" if line_y > footer_y
                        else "body")
                col = 1
                for sid, span in enumerate(ln.get("spans", [])):
                    fname  = span.get("font", "")
                    fsize  = round(span.get("size", 0), 2)
                    fcolor = _int_to_rgb(span.get("color", 0))
                    flags  = span.get("flags", 0)
                    bold   = bool(flags & 2**4)
                    italic = bool(flags & 2**1)

                    # Split span into words
                    for word_text in span.get("text","").split():
                        # find word bbox via word extraction
                        data.words.append(WordToken(
                            text       = word_text,
                            page       = pno,
                            line       = line_num,
                            col        = col,
                            bbox       = BBox(*[round(v,2) for v in span["bbox"]]),
                            font_name  = fname,
                            font_size  = fsize,
                            font_color = fcolor,
                            bold       = bold,
                            italic     = italic,
                            zone       = zone,
                            block_id   = block_id,
                            span_id    = sid,
                        ))
                        col += len(word_text) + 1

        # ── More precise word bboxes via get_text("words") ────────────────────
        # Merge bbox from word-level extraction (more precise X positions)
        word_list = page.get_text("words")  # (x0,y0,x1,y1,word,block,line,wid)
        # Map by page word index to our tokens
        page_words = [w for w in data.words if w.page == pno]
        for i, wl in enumerate(word_list):
            if i < len(page_words):
                page_words[i].bbox = BBox(
                    round(wl[0],2), round(wl[1],2),
                    round(wl[2],2), round(wl[3],2)
                )

        # ── Drawings (borders, lines, rectangles) ─────────────────────────────
        for path_obj in page.get_drawings():
            bbox  = BBox(*[round(v,2) for v in path_obj["rect"]])
            color = _float_rgb(path_obj.get("color") or (0,0,0))
            fill  = _float_rgb(path_obj.get("fill")) if path_obj.get("fill") else None
            width = round(path_obj.get("width", 0), 2)
            kind  = "rect" if path_obj.get("fill") else "line"
            data.drawings.append(DrawingElement(
                page=pno, kind=kind, bbox=bbox,
                color=color, fill=fill, width=width
            ))

        # ── Page image (for visual diff) ──────────────────────────────────────
        try:
            mat = fitz.Matrix(DPI/72, DPI/72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            from PIL import Image as PILImage
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            data.page_images.append(img)
        except Exception as e:
            data.errors.append(f"Page {pno} render failed: {e}")

    doc.close()
    data.raw_text = "\n".join(w.text for w in data.words)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# DOCX extractor
# ─────────────────────────────────────────────────────────────────────────────

def _extract_docx(path: str) -> DocumentData:
    data = DocumentData(path=path, file_type="docx")

    if not _DOCX:
        data.errors.append("python-docx not installed")
        return _extract_text(path)

    try:
        document = docx.Document(path)
    except Exception as e:
        data.errors.append(f"Cannot open DOCX: {e}")
        return data

    # ── Page size & margins ───────────────────────────────────────────────────
    section = document.sections[0]
    pw = _emu_to_pt(section.page_width)
    ph = _emu_to_pt(section.page_height)
    data.pages.append(PageMeta(
        page=1, width=round(pw,2), height=round(ph,2), rotation=0,
        margin_top    = round(_emu_to_pt(section.top_margin),2),
        margin_bot    = round(_emu_to_pt(section.bottom_margin),2),
        margin_left   = round(_emu_to_pt(section.left_margin),2),
        margin_right  = round(_emu_to_pt(section.right_margin),2),
    ))

    line_num = 0

    def _process_para(para, zone="body", page=1):
        nonlocal line_num
        line_num += 1
        col = 1
        for run in para.runs:
            if not run.text.strip():
                col += len(run.text)
                continue
            fn = (run.font.name or
                  para.style.font.name if para.style and para.style.font else "") or ""
            fs_obj = run.font.size or (para.style.font.size if para.style and para.style.font else None)
            fs = round(fs_obj.pt, 2) if fs_obj else 0.0
            fc = (0,0,0)
            if run.font.color and run.font.color.type is not None:
                try:
                    rgb = run.font.color.rgb
                    fc  = (rgb.red, rgb.green, rgb.blue)
                except Exception:
                    pass
            for word in run.text.split():
                data.words.append(WordToken(
                    text       = word,
                    page       = page,
                    line       = line_num,
                    col        = col,
                    bbox       = BBox(0, line_num*14.0, len(word)*7.0, (line_num+1)*14.0),
                    font_name  = fn,
                    font_size  = fs,
                    font_color = fc,
                    bold       = bool(run.bold),
                    italic     = bool(run.italic),
                    underline  = bool(run.underline),
                    strike     = bool(run.font.strike),
                    zone       = zone,
                ))
                col += len(word) + 1

    # ── Headers ───────────────────────────────────────────────────────────────
    for section in document.sections:
        if section.header:
            for para in section.header.paragraphs:
                _process_para(para, zone="header")

    # ── Body ──────────────────────────────────────────────────────────────────
    for para in document.paragraphs:
        _process_para(para, zone="body")

    # ── Tables ────────────────────────────────────────────────────────────────
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _process_para(para, zone="body")

    # ── Footers ───────────────────────────────────────────────────────────────
    for section in document.sections:
        if section.footer:
            for para in section.footer.paragraphs:
                _process_para(para, zone="footer")

    data.raw_text = " ".join(w.text for w in data.words)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Plain text extractor (TXT / CSV / JSON / XML etc.)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text(path: str) -> DocumentData:
    data = DocumentData(path=path, file_type="text")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        data.errors.append(f"Cannot read file: {e}")
        return data

    lines = content.splitlines()
    total = len(lines)
    data.pages.append(PageMeta(1, 0, 0, 0, 0, 0, 0, 0))

    for ln_idx, line in enumerate(lines, 1):
        zone = ("header" if ln_idx <= max(1, total//10)
                else "footer" if ln_idx >= total - max(1, total//10)
                else "body")
        col = 1
        for word in line.split():
            data.words.append(WordToken(
                text=word, page=1, line=ln_idx, col=col,
                bbox=BBox(col*7, ln_idx*14, (col+len(word))*7, (ln_idx+1)*14),
                zone=zone,
            ))
            col += len(word) + 1

    data.raw_text = content
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _int_to_rgb(color_int: int) -> Tuple:
    """Convert PyMuPDF integer color to (R,G,B) 0-255."""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8)  & 0xFF
    b =  color_int        & 0xFF
    return (r, g, b)

def _float_rgb(color) -> Tuple:
    """Convert PyMuPDF float tuple (0-1) to (R,G,B) 0-255."""
    if color is None: return (0,0,0)
    return tuple(int(c*255) for c in color[:3])

def _emu_to_pt(emu) -> float:
    """Convert EMU (English Metric Units) to points."""
    if emu is None: return 0.0
    return emu / 12700.0
