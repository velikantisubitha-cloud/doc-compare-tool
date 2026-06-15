"""
deep_comparator.py — Master comparison engine v3.

Compares ALL extracted properties:
  1.  Page count & size
  2.  Margins
  3.  Header / footer / body content
  4.  Font name, size, color, bold, italic, underline, strike
  5.  Word position (X, Y bounding box)
  6.  Text alignment per line (LEFT/CENTER/RIGHT/JUSTIFY)     NEW
  7.  Line spacing                                             NEW
  8.  Paragraph spacing (before/after)                        NEW
  9.  Letter spacing / kerning                                 NEW
  10. Highlight / background color                             NEW
  11. Embedded images (position + pixel similarity)            NEW
  12. Table cell border styling (color/width/style per side)   NEW
  13. Watermarks (detected vs not detected)                    NEW
  14. PDF form fields (name/type/value/position)               NEW
  15. Drawings / borders / lines
  16. Page rotation
  17. Visual pixel diff (OpenCV SSIM per page)
  18. Character-level Myers diff
"""

from __future__ import annotations
import difflib, math, hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from extractor import (DocumentData, WordToken, BBox,
                       LineSpacing, ParaSpacing, DrawingElement,
                       ImageElement, WatermarkElement, FormField, TableCell)

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False


SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_MAJOR    = "MAJOR"
SEVERITY_MINOR    = "MINOR"

# ── Tolerances ────────────────────────────────────────────────────────────────
TOL_FONT_SIZE      = 0.5    # pt
TOL_POSITION       = 3.0    # px
TOL_COLOR          = 10     # 0-255 per channel
TOL_LINE_SPACING   = 2.0    # pt
TOL_PARA_SPACING   = 3.0    # pt
TOL_LETTER_SPACING = 0.5    # pt
TOL_IMG_SIMILARITY = 95.0   # % — images below this are flagged


@dataclass
class Issue:
    category:      str
    check:         str
    severity:      str
    page:          int
    line:          int
    col:           int
    zone:          str
    template_val:  str
    generated_val: str
    detail:        str = ""


@dataclass
class ComparisonReport:
    issues:             List[Issue]
    total_words_tmpl:   int
    total_words_gen:    int
    pages_tmpl:         int
    pages_gen:          int
    text_similarity:    float
    visual_similarity:  float
    overall_score:      float
    overall_result:     str
    diff_images:        List[Dict]
    section_scores:     Dict[str, float]

    def issues_by_category(self) -> Dict[str, List[Issue]]:
        out: Dict[str, List[Issue]] = {}
        for i in self.issues:
            out.setdefault(i.category, []).append(i)
        return out

    def count_by_severity(self) -> Dict[str, int]:
        return {
            SEVERITY_CRITICAL: sum(1 for i in self.issues if i.severity == SEVERITY_CRITICAL),
            SEVERITY_MAJOR:    sum(1 for i in self.issues if i.severity == SEVERITY_MAJOR),
            SEVERITY_MINOR:    sum(1 for i in self.issues if i.severity == SEVERITY_MINOR),
        }


# ─────────────────────────────────────────────────────────────────────────────
def compare(tmpl: DocumentData, gen: DocumentData) -> ComparisonReport:
    issues: List[Issue] = []
    diff_images: List[Dict] = []

    _check_pages(tmpl, gen, issues)
    _check_margins(tmpl, gen, issues)
    _check_words(tmpl, gen, issues)
    _check_line_spacing(tmpl, gen, issues)
    _check_para_spacing(tmpl, gen, issues)
    _check_drawings(tmpl, gen, issues)
    _check_images(tmpl, gen, issues)
    _check_watermarks(tmpl, gen, issues)
    _check_form_fields(tmpl, gen, issues)
    _check_table_cells(tmpl, gen, issues)
    _check_text_precise(tmpl, gen, issues)

    visual_sim = _visual_diff(tmpl, gen, diff_images)
    text_sim   = _text_similarity(tmpl.raw_text, gen.raw_text)

    def _section_score(zone):
        z_issues = [i for i in issues if i.zone == zone]
        z_words  = [w for w in tmpl.words if w.zone == zone]
        if not z_words: return 100.0
        penalty = sum(3 if i.severity==SEVERITY_CRITICAL else
                      2 if i.severity==SEVERITY_MAJOR else 1
                      for i in z_issues)
        return max(0.0, round(100 - (penalty / len(z_words)) * 100, 2))

    section_scores = {
        "header": _section_score("header"),
        "body":   _section_score("body"),
        "footer": _section_score("footer"),
    }

    sc = {SEVERITY_CRITICAL: sum(1 for i in issues if i.severity==SEVERITY_CRITICAL),
          SEVERITY_MAJOR:    sum(1 for i in issues if i.severity==SEVERITY_MAJOR),
          SEVERITY_MINOR:    sum(1 for i in issues if i.severity==SEVERITY_MINOR)}

    total_w    = max(len(tmpl.words), 1)
    penalty    = sc[SEVERITY_CRITICAL]*3 + sc[SEVERITY_MAJOR]*2 + sc[SEVERITY_MINOR]*1
    overall    = max(0.0, round(100 - (penalty / total_w) * 100, 2))
    result     = "PASS" if (sc[SEVERITY_CRITICAL] == 0 and overall >= 95) else "FAIL"

    return ComparisonReport(
        issues            = issues,
        total_words_tmpl  = len(tmpl.words),
        total_words_gen   = len(gen.words),
        pages_tmpl        = len(tmpl.pages),
        pages_gen         = len(gen.pages),
        text_similarity   = round(text_sim, 4),
        visual_similarity = round(visual_sim, 4),
        overall_score     = overall,
        overall_result    = result,
        diff_images       = diff_images,
        section_scores    = section_scores,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Check functions
# ─────────────────────────────────────────────────────────────────────────────

def _check_pages(tmpl, gen, issues):
    if len(tmpl.pages) != len(gen.pages):
        issues.append(Issue("Page","Page Count", SEVERITY_CRITICAL,0,0,0,"body",
            str(len(tmpl.pages)), str(len(gen.pages)),
            f"Template has {len(tmpl.pages)} page(s), generated has {len(gen.pages)}"))

    for i, (t, g) in enumerate(zip(tmpl.pages, gen.pages), 1):
        if abs(t.width  - g.width)  > 1:
            issues.append(Issue("Page","Page Width",  SEVERITY_MAJOR, i,0,0,"body",
                f"{t.width}pt", f"{g.width}pt", f"Page {i} width mismatch"))
        if abs(t.height - g.height) > 1:
            issues.append(Issue("Page","Page Height", SEVERITY_MAJOR, i,0,0,"body",
                f"{t.height}pt", f"{g.height}pt", f"Page {i} height mismatch"))
        if t.rotation != g.rotation:
            issues.append(Issue("Page","Page Rotation", SEVERITY_MAJOR, i,0,0,"body",
                str(t.rotation), str(g.rotation), f"Page {i} rotation differs"))


def _check_margins(tmpl, gen, issues):
    for i, (t, g) in enumerate(zip(tmpl.pages, gen.pages), 1):
        for attr, label in [("margin_top","Top Margin"),("margin_bot","Bottom Margin"),
                             ("margin_left","Left Margin"),("margin_right","Right Margin")]:
            tv, gv = getattr(t, attr), getattr(g, attr)
            if tv > 0 and gv > 0 and abs(tv - gv) > 2:
                issues.append(Issue("Layout", label, SEVERITY_MAJOR, i,0,0,"body",
                    f"{tv}pt", f"{gv}pt", f"Page {i} {label} differs"))


def _check_words(tmpl, gen, issues):
    pages = max(len(tmpl.pages), len(gen.pages), 1)
    for page in range(1, pages + 1):
        for zone in ("header", "footer", "body"):
            t_words = [w for w in tmpl.words if w.page==page and w.zone==zone]
            g_words = [w for w in gen.words  if w.page==page and w.zone==zone]
            if not t_words and not g_words: continue

            t_texts = [w.text for w in t_words]
            g_texts = [w.text for w in g_words]
            sm      = difflib.SequenceMatcher(None, t_texts, g_texts, autojunk=False)
            cat     = {"header":"Header","footer":"Footer","body":"Body"}.get(zone,"Body")

            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    for ti, gi in zip(range(i1,i2), range(j1,j2)):
                        _compare_word_pair(t_words[ti], g_words[gi], issues, cat)
                elif tag == "replace":
                    tc = " ".join(t_texts[i1:i2]); gc = " ".join(g_texts[j1:j2])
                    ref = t_words[i1]
                    issues.append(Issue(cat,"Content",SEVERITY_CRITICAL,
                        page,ref.line,ref.col,zone,repr(tc),repr(gc),
                        f"Page {page} {zone}: text differs at line {ref.line}"))
                elif tag == "delete":
                    tc = " ".join(t_texts[i1:i2]); ref = t_words[i1]
                    issues.append(Issue(cat,"Missing Content",SEVERITY_CRITICAL,
                        page,ref.line,ref.col,zone,repr(tc),"[MISSING]",
                        f"Page {page} {zone}: content missing in generated"))
                elif tag == "insert":
                    gc = " ".join(g_texts[j1:j2]); ref = g_words[j1]
                    issues.append(Issue(cat,"Extra Content",SEVERITY_CRITICAL,
                        page,ref.line,ref.col,zone,"[NOT IN TEMPLATE]",repr(gc),
                        f"Page {page} {zone}: extra content in generated"))


def _compare_word_pair(tw: WordToken, gw: WordToken, issues, cat):
    p, ln, col, zone = tw.page, tw.line, tw.col, tw.zone

    if tw.text != gw.text:
        issues.append(Issue(cat,"Word Text",SEVERITY_CRITICAL,p,ln,col,zone,
            repr(tw.text),repr(gw.text),f"Word mismatch at line {ln} col {col}"))

    if tw.font_name and gw.font_name and tw.font_name != gw.font_name:
        issues.append(Issue(cat,"Font Name",SEVERITY_MAJOR,p,ln,col,zone,
            tw.font_name,gw.font_name,f"'{tw.text}' font name differs"))

    if tw.font_size>0 and gw.font_size>0 and abs(tw.font_size-gw.font_size)>TOL_FONT_SIZE:
        issues.append(Issue(cat,"Font Size",SEVERITY_MAJOR,p,ln,col,zone,
            f"{tw.font_size}pt",f"{gw.font_size}pt",
            f"'{tw.text}' size differs by {abs(tw.font_size-gw.font_size):.1f}pt"))

    if _color_diff(tw.font_color, gw.font_color) > TOL_COLOR:
        issues.append(Issue(cat,"Font Color",SEVERITY_MAJOR,p,ln,col,zone,
            _rgb_str(tw.font_color),_rgb_str(gw.font_color),
            f"'{tw.text}' color differs"))

    if tw.bold != gw.bold:
        issues.append(Issue(cat,"Bold",SEVERITY_MAJOR,p,ln,col,zone,
            str(tw.bold),str(gw.bold),f"'{tw.text}' bold differs"))

    if tw.italic != gw.italic:
        issues.append(Issue(cat,"Italic",SEVERITY_MAJOR,p,ln,col,zone,
            str(tw.italic),str(gw.italic),f"'{tw.text}' italic differs"))

    if tw.underline != gw.underline:
        issues.append(Issue(cat,"Underline",SEVERITY_MINOR,p,ln,col,zone,
            str(tw.underline),str(gw.underline),f"'{tw.text}' underline differs"))

    if tw.strike != gw.strike:
        issues.append(Issue(cat,"Strikethrough",SEVERITY_MINOR,p,ln,col,zone,
            str(tw.strike),str(gw.strike),f"'{tw.text}' strikethrough differs"))

    # Alignment NEW
    if tw.alignment != gw.alignment:
        issues.append(Issue(cat,"Text Alignment",SEVERITY_MAJOR,p,ln,col,zone,
            tw.alignment,gw.alignment,f"Line {ln} alignment differs"))

    # Highlight color NEW
    if tw.highlight_color != gw.highlight_color:
        if not (tw.highlight_color is None and gw.highlight_color is None):
            issues.append(Issue(cat,"Highlight Color",SEVERITY_MINOR,p,ln,col,zone,
                _rgb_str(tw.highlight_color),_rgb_str(gw.highlight_color),
                f"'{tw.text}' background highlight differs"))

    # Letter spacing NEW
    if abs(tw.letter_spacing - gw.letter_spacing) > TOL_LETTER_SPACING:
        issues.append(Issue(cat,"Letter Spacing",SEVERITY_MINOR,p,ln,col,zone,
            f"{tw.letter_spacing}pt",f"{gw.letter_spacing}pt",
            f"'{tw.text}' letter spacing differs"))

    # Position
    if tw.bbox and gw.bbox:
        dx = abs(tw.bbox.x0 - gw.bbox.x0)
        dy = abs(tw.bbox.y0 - gw.bbox.y0)
        if dx > TOL_POSITION:
            issues.append(Issue(cat,"Horizontal Position",SEVERITY_MAJOR,p,ln,col,zone,
                f"x={tw.bbox.x0}",f"x={gw.bbox.x0}",
                f"'{tw.text}' X off by {dx:.1f}px"))
        if dy > TOL_POSITION:
            issues.append(Issue(cat,"Vertical Position",SEVERITY_MAJOR,p,ln,col,zone,
                f"y={tw.bbox.y0}",f"y={gw.bbox.y0}",
                f"'{tw.text}' Y off by {dy:.1f}px"))


def _check_line_spacing(tmpl, gen, issues):
    """Compare average line spacing per page per zone."""
    def _avg(spacings, page, zone):
        vals = [s.spacing_pt for s in spacings if s.page==page and s.zone==zone]
        return round(sum(vals)/len(vals), 2) if vals else 0.0

    pages = max(len(tmpl.pages), len(gen.pages), 1)
    for page in range(1, pages+1):
        for zone in ("header","body","footer"):
            t_avg = _avg(tmpl.line_spacings, page, zone)
            g_avg = _avg(gen.line_spacings,  page, zone)
            if t_avg > 0 and g_avg > 0 and abs(t_avg - g_avg) > TOL_LINE_SPACING:
                cat = {"header":"Header","footer":"Footer","body":"Body"}.get(zone,"Body")
                issues.append(Issue(cat,"Line Spacing",SEVERITY_MINOR,page,0,0,zone,
                    f"{t_avg}pt avg",f"{g_avg}pt avg",
                    f"Page {page} {zone} line spacing differs by {abs(t_avg-g_avg):.1f}pt"))


def _check_para_spacing(tmpl, gen, issues):
    """Compare paragraph spacing before/after."""
    t_para = {(p.page, p.block_id): p for p in tmpl.para_spacings}
    g_para = {(p.page, p.block_id): p for p in gen.para_spacings}

    for key, tp in t_para.items():
        gp = g_para.get(key)
        if not gp: continue
        if abs(tp.space_before - gp.space_before) > TOL_PARA_SPACING:
            issues.append(Issue("Layout","Paragraph Space Before",SEVERITY_MINOR,
                tp.page,0,0,"body",
                f"{tp.space_before}pt",f"{gp.space_before}pt",
                f"Page {tp.page} block {tp.block_id} space-before differs"))
        if abs(tp.space_after - gp.space_after) > TOL_PARA_SPACING:
            issues.append(Issue("Layout","Paragraph Space After",SEVERITY_MINOR,
                tp.page,0,0,"body",
                f"{tp.space_after}pt",f"{gp.space_after}pt",
                f"Page {tp.page} block {tp.block_id} space-after differs"))


def _check_drawings(tmpl, gen, issues):
    tp, gp = len(tmpl.drawings), len(gen.drawings)
    if tp != gp:
        issues.append(Issue("Border","Drawing Count",SEVERITY_MAJOR,0,0,0,"body",
            str(tp),str(gp),f"Template has {tp} drawings, generated has {gp}"))
        return
    for i, (td, gd) in enumerate(zip(tmpl.drawings, gen.drawings)):
        if _color_diff(td.color, gd.color) > TOL_COLOR:
            issues.append(Issue("Border","Border Color",SEVERITY_MAJOR,td.page,0,0,"body",
                _rgb_str(td.color),_rgb_str(gd.color),f"Drawing {i+1} color differs"))
        if abs(td.width - gd.width) > 0.5:
            issues.append(Issue("Border","Border Width",SEVERITY_MINOR,td.page,0,0,"body",
                f"{td.width}pt",f"{gd.width}pt",f"Drawing {i+1} width differs"))
        if (abs(td.bbox.x0-gd.bbox.x0)>TOL_POSITION or
                abs(td.bbox.y0-gd.bbox.y0)>TOL_POSITION):
            issues.append(Issue("Border","Border Position",SEVERITY_MAJOR,td.page,0,0,"body",
                f"({td.bbox.x0},{td.bbox.y0})",f"({gd.bbox.x0},{gd.bbox.y0})",
                f"Drawing {i+1} position differs"))


def _check_images(tmpl, gen, issues):
    """Compare embedded images by hash and pixel similarity."""
    ti, gi = len(tmpl.images), len(gen.images)

    if ti != gi:
        issues.append(Issue("Image","Image Count",SEVERITY_MAJOR,0,0,0,"body",
            str(ti),str(gi),
            f"Template has {ti} image(s), generated has {gi}"))

    for idx, (t_img, g_img) in enumerate(zip(tmpl.images, gen.images), 1):
        # Hash comparison (exact match)
        if t_img.img_hash == g_img.img_hash:
            continue

        # Pixel similarity
        sim = _image_pixel_similarity(t_img.img_bytes, g_img.img_bytes)
        if sim < TOL_IMG_SIMILARITY:
            issues.append(Issue("Image","Image Content",
                SEVERITY_CRITICAL if sim < 80 else SEVERITY_MAJOR,
                t_img.page,0,0,"body",
                f"Image {idx} (hash:{t_img.img_hash[:8]})",
                f"Image {idx} (hash:{g_img.img_hash[:8]})",
                f"Image {idx} pixel similarity: {sim:.1f}% (expected ≥{TOL_IMG_SIMILARITY}%)"))

        # Position check
        if (t_img.bbox.x0 > 0 and g_img.bbox.x0 > 0 and
                abs(t_img.bbox.x0-g_img.bbox.x0) > TOL_POSITION):
            issues.append(Issue("Image","Image Position",SEVERITY_MAJOR,
                t_img.page,0,0,"body",
                f"x={t_img.bbox.x0}",f"x={g_img.bbox.x0}",
                f"Image {idx} X position differs"))

        # Size check
        if (t_img.width > 0 and g_img.width > 0 and
                abs(t_img.width - g_img.width) > 5):
            issues.append(Issue("Image","Image Size",SEVERITY_MINOR,
                t_img.page,0,0,"body",
                f"{t_img.width}x{t_img.height}",
                f"{g_img.width}x{g_img.height}",
                f"Image {idx} dimensions differ"))


def _check_watermarks(tmpl, gen, issues):
    """Compare watermark presence and content."""
    tw = [w for w in tmpl.watermarks if not w.kind == "image" or w.text]
    gw = [w for w in gen.watermarks  if not w.kind == "image" or w.text]

    if len(tw) != len(gw):
        issues.append(Issue("Watermark","Watermark Count",SEVERITY_MAJOR,0,0,0,"body",
            str(len(tw)),str(len(gw)),
            f"Template has {len(tw)} watermark(s), generated has {len(gw)}"))
        return

    for i, (t_wm, g_wm) in enumerate(zip(tw, gw), 1):
        if t_wm.kind == "text" and t_wm.text != g_wm.text:
            issues.append(Issue("Watermark","Watermark Text",SEVERITY_CRITICAL,
                t_wm.page,0,0,"body",
                repr(t_wm.text),repr(g_wm.text),
                f"Watermark {i} text differs"))
        if t_wm.color and g_wm.color and _color_diff(t_wm.color, g_wm.color) > TOL_COLOR:
            issues.append(Issue("Watermark","Watermark Color",SEVERITY_MINOR,
                t_wm.page,0,0,"body",
                _rgb_str(t_wm.color),_rgb_str(g_wm.color),
                f"Watermark {i} color differs"))


def _check_form_fields(tmpl, gen, issues):
    """Compare PDF form fields."""
    tf = {f.name: f for f in tmpl.form_fields}
    gf = {f.name: f for f in gen.form_fields}

    # Missing fields
    for name in tf:
        if name not in gf:
            issues.append(Issue("FormField","Missing Field",SEVERITY_CRITICAL,
                tf[name].page,0,0,"body",
                name,"[MISSING]",f"Form field '{name}' missing in generated"))

    # Extra fields
    for name in gf:
        if name not in tf:
            issues.append(Issue("FormField","Extra Field",SEVERITY_MAJOR,
                gf[name].page,0,0,"body",
                "[NOT IN TEMPLATE]",name,f"Extra form field '{name}' in generated"))

    # Mismatched fields
    for name in tf:
        if name not in gf: continue
        t_f, g_f = tf[name], gf[name]

        if t_f.field_type != g_f.field_type:
            issues.append(Issue("FormField","Field Type",SEVERITY_MAJOR,
                t_f.page,0,0,"body",t_f.field_type,g_f.field_type,
                f"Field '{name}' type differs"))

        if t_f.value != g_f.value:
            issues.append(Issue("FormField","Field Value",SEVERITY_CRITICAL,
                t_f.page,0,0,"body",repr(t_f.value),repr(g_f.value),
                f"Field '{name}' value differs"))

        if t_f.required != g_f.required:
            issues.append(Issue("FormField","Field Required",SEVERITY_MINOR,
                t_f.page,0,0,"body",str(t_f.required),str(g_f.required),
                f"Field '{name}' required flag differs"))

        if t_f.font_size>0 and g_f.font_size>0 and abs(t_f.font_size-g_f.font_size)>TOL_FONT_SIZE:
            issues.append(Issue("FormField","Field Font Size",SEVERITY_MINOR,
                t_f.page,0,0,"body",f"{t_f.font_size}pt",f"{g_f.font_size}pt",
                f"Field '{name}' font size differs"))


def _check_table_cells(tmpl, gen, issues):
    """Compare table cell borders."""
    t_cells = {(c.row, c.col): c for c in tmpl.table_cells}
    g_cells = {(c.row, c.col): c for c in gen.table_cells}

    if len(t_cells) != len(g_cells):
        issues.append(Issue("Table","Cell Count",SEVERITY_MAJOR,0,0,0,"body",
            str(len(t_cells)),str(len(g_cells)),
            f"Table cell count differs: {len(t_cells)} vs {len(g_cells)}"))

    for key, tc in t_cells.items():
        gc = g_cells.get(key)
        if not gc: continue

        # Cell text
        if tc.text.strip() != gc.text.strip():
            issues.append(Issue("Table","Cell Text",SEVERITY_CRITICAL,
                tc.page,tc.row,tc.col,"body",
                repr(tc.text),repr(gc.text),
                f"Table cell ({tc.row},{tc.col}) text differs"))

        # Cell borders
        for side in ("border_top","border_bottom","border_left","border_right"):
            t_b = getattr(tc, side)
            g_b = getattr(gc, side)
            if t_b is None and g_b is None: continue

            if (t_b is None) != (g_b is None):
                issues.append(Issue("Table",f"Cell {side.replace('_',' ').title()}",
                    SEVERITY_MAJOR, tc.page, tc.row, tc.col, "body",
                    str(t_b), str(g_b),
                    f"Cell ({tc.row},{tc.col}) {side} presence differs"))
                continue

            if t_b and g_b:
                if _color_diff(t_b.get("color",(0,0,0)), g_b.get("color",(0,0,0))) > TOL_COLOR:
                    issues.append(Issue("Table",f"Cell Border Color",SEVERITY_MINOR,
                        tc.page,tc.row,tc.col,"body",
                        _rgb_str(t_b.get("color")),_rgb_str(g_b.get("color")),
                        f"Cell ({tc.row},{tc.col}) {side} color differs"))

                if abs(t_b.get("width",0) - g_b.get("width",0)) > 0.3:
                    issues.append(Issue("Table","Cell Border Width",SEVERITY_MINOR,
                        tc.page,tc.row,tc.col,"body",
                        f"{t_b.get('width')}pt",f"{g_b.get('width')}pt",
                        f"Cell ({tc.row},{tc.col}) {side} width differs"))

                if t_b.get("style") != g_b.get("style"):
                    issues.append(Issue("Table","Cell Border Style",SEVERITY_MINOR,
                        tc.page,tc.row,tc.col,"body",
                        t_b.get("style",""),g_b.get("style",""),
                        f"Cell ({tc.row},{tc.col}) {side} style differs"))


def _check_text_precise(tmpl, gen, issues):
    from precise_diff import precise_diff
    report = precise_diff(tmpl.raw_text, gen.raw_text)
    for c in report.changes:
        if not c.original and not c.modified: continue
        issues.append(Issue(
            category      = "Content",
            check         = f"Char-level {c.change_type}",
            severity      = SEVERITY_CRITICAL,
            page          = 1,
            line          = c.tmpl_line or c.gen_line,
            col           = c.tmpl_col  or c.gen_col,
            zone          = "body",
            template_val  = repr(c.original) if c.original else "[none]",
            generated_val = repr(c.modified) if c.modified else "[none]",
            detail        = (f"Line {c.tmpl_line or c.gen_line}, "
                             f"Col {c.tmpl_col or c.gen_col} — "
                             f"context: …{c.context_before}[CHANGE]{c.context_after}…")
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Visual diff
# ─────────────────────────────────────────────────────────────────────────────

def _visual_diff(tmpl, gen, diff_images):
    if not _CV2 and not _PIL: return 0.0
    t_imgs = tmpl.page_images
    g_imgs = gen.page_images
    if not t_imgs or not g_imgs: return 0.0

    scores = []
    max_pg = max(len(t_imgs), len(g_imgs))

    for idx in range(max_pg):
        has_t = idx < len(t_imgs)
        has_g = idx < len(g_imgs)

        if has_t and has_g:
            t_img = t_imgs[idx].convert("RGB")
            g_img = g_imgs[idx].convert("RGB").resize(t_img.size, Image.LANCZOS)
            result = _cv2_diff(t_img, g_img) if _CV2 else _pil_diff(t_img, g_img)
            scores.append(result["similarity"])
            diff_images.append({
                "page": idx+1, "template_img": t_img, "generated_img": g_img,
                "diff_img": result["diff_img"], "page_score": result["similarity"],
                "region_count": result["region_count"], "status": "compared", "note": None,
            })
        elif has_t:
            t_img = t_imgs[idx].convert("RGB")
            b = Image.new("RGB", t_img.size, (245,245,245))
            _draw_label(b, "MISSING IN GENERATED")
            scores.append(0.0)
            diff_images.append({"page":idx+1,"template_img":t_img,"generated_img":b,
                "diff_img":b.copy(),"page_score":0.0,"region_count":99,
                "status":"missing","note":f"⚠️ Page {idx+1} missing in generated"})
        else:
            g_img = g_imgs[idx].convert("RGB")
            b = Image.new("RGB", g_img.size, (245,245,245))
            _draw_label(b, "NOT IN TEMPLATE")
            scores.append(0.0)
            diff_images.append({"page":idx+1,"template_img":b,"generated_img":g_img,
                "diff_img":b.copy(),"page_score":0.0,"region_count":99,
                "status":"extra","note":f"ℹ️ Page {idx+1} extra in generated"})

    return sum(scores)/len(scores) if scores else 0.0


def _cv2_diff(t_img, g_img):
    t_arr  = cv2.cvtColor(np.array(t_img), cv2.COLOR_RGB2BGR)
    g_arr  = cv2.cvtColor(np.array(g_img), cv2.COLOR_RGB2BGR)
    t_gray = cv2.cvtColor(t_arr, cv2.COLOR_BGR2GRAY)
    g_gray = cv2.cvtColor(g_arr, cv2.COLOR_BGR2GRAY)
    diff   = cv2.absdiff(t_gray, g_gray)
    _, thr = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
    thr    = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel)
    thr    = cv2.morphologyEx(thr, cv2.MORPH_DILATE, kernel)
    contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    annotated   = g_arr.copy()
    sig = [c for c in contours if cv2.contourArea(c) > 100]
    for c in sig:
        x,y,w,h = cv2.boundingRect(c)
        cv2.rectangle(annotated,(x,y),(x+w,y+h),(0,0,220),2)
    total = t_gray.shape[0]*t_gray.shape[1]
    sim   = max(0.0,(1-np.count_nonzero(thr)/total)*100)
    return {"diff_img":Image.fromarray(cv2.cvtColor(annotated,cv2.COLOR_BGR2RGB)),
            "region_count":len(sig),"similarity":round(sim,4)}


def _pil_diff(t_img, g_img):
    from PIL import ImageChops
    import numpy as np
    diff     = ImageChops.difference(t_img, g_img)
    arr      = np.array(diff.convert("L"))
    mask     = arr > 20
    sim      = max(0.0,(1-mask.sum()/mask.size)*100)
    annotated = g_img.copy()
    draw      = ImageDraw.Draw(annotated, "RGBA")
    rows,cols = np.where(mask)
    for r,c in zip(rows[::10],cols[::10]):
        draw.point((c,r),fill=(220,0,0,100))
    return {"diff_img":annotated,"region_count":int(mask.sum()//500),"similarity":round(sim,4)}


def _draw_label(img, label):
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    try: font = ImageFont.truetype("arial.ttf",22)
    except: font = ImageFont.load_default()
    w,h = img.size
    draw.rectangle([20,h//2-40,w-20,h//2+40],outline=(220,50,50),width=3)
    draw.text((w//2-80,h//2-12),label,fill=(220,50,50),font=font)


def _image_pixel_similarity(bytes1: bytes, bytes2: bytes) -> float:
    """Compare two images by pixel diff. Returns 0-100 similarity."""
    try:
        import io
        from PIL import Image as PILImg
        img1 = PILImg.open(io.BytesIO(bytes1)).convert("RGB").resize((128,128))
        img2 = PILImg.open(io.BytesIO(bytes2)).convert("RGB").resize((128,128))
        if _CV2:
            a1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2GRAY)
            a2 = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2GRAY)
            diff = cv2.absdiff(a1, a2)
            sim  = (1 - diff.mean()/255) * 100
        else:
            import numpy as np
            a1 = np.array(img1, dtype=float)
            a2 = np.array(img2, dtype=float)
            sim = (1 - np.abs(a1-a2).mean()/255) * 100
        return round(sim, 2)
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _text_similarity(a, b):
    if not a and not b: return 100.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).quick_ratio() * 100

def _color_diff(c1, c2):
    if not c1 or not c2: return 0.0
    return math.sqrt(sum((a-b)**2 for a,b in zip(c1,c2)))

def _rgb_str(c):
    if not c: return "N/A"
    try: return f"rgb({c[0]},{c[1]},{c[2]})"
    except: return str(c)
