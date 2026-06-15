"""
deep_comparator.py — Master comparison engine.

Compares two DocumentData objects across ALL dimensions:

  1.  Page count & page size
  2.  Margins
  3.  Header content + formatting (font, size, color, bold, italic, position)
  4.  Footer content + formatting
  5.  Body content (word-by-word)
  6.  Font name mismatches
  7.  Font size mismatches
  8.  Font color mismatches
  9.  Bold / Italic / Underline / Strikethrough mismatches
  10. Word position (bounding box X,Y) mismatches
  11. Word spacing (gap between words)
  12. Line spacing
  13. Drawings / borders / lines / rectangles
  14. Page rotation
  15. Visual pixel diff (OpenCV SSIM per page)
  16. Character-level text diff (precise Myers)
  17. Special characters
  18. Whitespace & indentation
"""

from __future__ import annotations
import difflib, math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from extractor import DocumentData, WordToken, BBox

try:
    import cv2, numpy as np
    from PIL import Image, ImageDraw
    _CV2 = True
except ImportError:
    _CV2 = False


# ─────────────────────────────────────────────────────────────────────────────
# Issue record
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_CRITICAL = "CRITICAL"   # text / content wrong
SEVERITY_MAJOR    = "MAJOR"      # font size, color, position off
SEVERITY_MINOR    = "MINOR"      # spacing, style hints

@dataclass
class Issue:
    category:   str     # "Header"|"Footer"|"Body"|"Layout"|"Font"|"Color"|"Position"|"Border"|"Page"
    check:      str     # human label e.g. "Font Size"
    severity:   str     # CRITICAL / MAJOR / MINOR
    page:       int
    line:       int
    col:        int
    zone:       str     # header/footer/body
    template_val: str
    generated_val: str
    detail:     str     = ""


@dataclass
class ComparisonReport:
    issues:             List[Issue]
    total_words_tmpl:   int
    total_words_gen:    int
    pages_tmpl:         int
    pages_gen:          int
    text_similarity:    float        # 0-100
    visual_similarity:  float        # 0-100 (per page average)
    overall_score:      float        # 0-100 (100 = perfect match)
    overall_result:     str          # PASS / FAIL
    diff_images:        List[Dict]   # annotated page images
    section_scores:     Dict[str, float]  # per-section accuracy %

    def issues_by_category(self) -> Dict[str, List[Issue]]:
        out: Dict[str, List[Issue]] = {}
        for iss in self.issues:
            out.setdefault(iss.category, []).append(iss)
        return out

    def count_by_severity(self) -> Dict[str, int]:
        counts = {SEVERITY_CRITICAL:0, SEVERITY_MAJOR:0, SEVERITY_MINOR:0}
        for i in self.issues:
            counts[i.severity] = counts.get(i.severity,0) + 1
        return counts


# ─────────────────────────────────────────────────────────────────────────────
# Tolerances (tune here)
# ─────────────────────────────────────────────────────────────────────────────
TOL_FONT_SIZE   = 0.5    # pt  — differences smaller than this are ignored
TOL_POSITION    = 3.0    # px  — bbox position tolerance
TOL_COLOR       = 10     # 0-255 per channel
TOL_LINE_SPACE  = 2.0    # pt


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def compare(tmpl: DocumentData, gen: DocumentData) -> ComparisonReport:
    issues: List[Issue] = []
    diff_images: List[Dict] = []

    # 1. Page count & size
    _check_pages(tmpl, gen, issues)

    # 2. Margins
    _check_margins(tmpl, gen, issues)

    # 3-11. Word-level checks (content + formatting)
    _check_words(tmpl, gen, issues)

    # 12. Drawings / borders
    _check_drawings(tmpl, gen, issues)

    # 13. Visual pixel diff
    visual_sim = _visual_diff(tmpl, gen, diff_images)

    # 14. Character-level text diff
    _check_text_precise(tmpl, gen, issues)

    # ── Scoring ───────────────────────────────────────────────────────────────
    text_sim = _text_similarity(tmpl.raw_text, gen.raw_text)

    # Per-section scores
    def _section_score(zone):
        zone_issues = [i for i in issues if i.zone == zone]
        zone_words  = [w for w in tmpl.words if w.zone == zone]
        if not zone_words: return 100.0
        penalty = sum(
            3 if i.severity == SEVERITY_CRITICAL else
            2 if i.severity == SEVERITY_MAJOR    else 1
            for i in zone_issues
        )
        return max(0.0, 100 - (penalty / len(zone_words)) * 100)

    section_scores = {
        "header": round(_section_score("header"), 2),
        "body":   round(_section_score("body"),   2),
        "footer": round(_section_score("footer"), 2),
    }

    critical = sum(1 for i in issues if i.severity == SEVERITY_CRITICAL)
    major    = sum(1 for i in issues if i.severity == SEVERITY_MAJOR)
    minor    = sum(1 for i in issues if i.severity == SEVERITY_MINOR)

    total_w = max(len(tmpl.words), 1)
    penalty = (critical*3 + major*2 + minor*1)
    overall_score = max(0.0, round(100 - (penalty / total_w) * 100, 2))
    overall_result = "PASS" if (critical == 0 and overall_score >= 95) else "FAIL"

    return ComparisonReport(
        issues            = issues,
        total_words_tmpl  = len(tmpl.words),
        total_words_gen   = len(gen.words),
        pages_tmpl        = len(tmpl.pages),
        pages_gen         = len(gen.pages),
        text_similarity   = round(text_sim, 4),
        visual_similarity = round(visual_sim, 4),
        overall_score     = overall_score,
        overall_result    = overall_result,
        diff_images       = diff_images,
        section_scores    = section_scores,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Check functions
# ─────────────────────────────────────────────────────────────────────────────

def _check_pages(tmpl: DocumentData, gen: DocumentData, issues: List[Issue]):
    tp, gp = len(tmpl.pages), len(gen.pages)
    if tp != gp:
        issues.append(Issue(
            category="Page", check="Page Count", severity=SEVERITY_CRITICAL,
            page=0, line=0, col=0, zone="body",
            template_val=str(tp), generated_val=str(gp),
            detail=f"Template has {tp} page(s), generated has {gp}"
        ))

    for i, (t_pg, g_pg) in enumerate(zip(tmpl.pages, gen.pages), 1):
        if abs(t_pg.width  - g_pg.width)  > 1:
            issues.append(Issue("Page","Page Width", SEVERITY_MAJOR, i,0,0,"body",
                f"{t_pg.width}pt", f"{g_pg.width}pt",
                f"Page {i} width mismatch"))
        if abs(t_pg.height - g_pg.height) > 1:
            issues.append(Issue("Page","Page Height", SEVERITY_MAJOR, i,0,0,"body",
                f"{t_pg.height}pt", f"{g_pg.height}pt",
                f"Page {i} height mismatch"))
        if t_pg.rotation != g_pg.rotation:
            issues.append(Issue("Page","Page Rotation", SEVERITY_MAJOR, i,0,0,"body",
                str(t_pg.rotation), str(g_pg.rotation), f"Page {i} rotation mismatch"))


def _check_margins(tmpl: DocumentData, gen: DocumentData, issues: List[Issue]):
    for i, (t_pg, g_pg) in enumerate(zip(tmpl.pages, gen.pages), 1):
        for attr, label in [("margin_top","Top Margin"),("margin_bot","Bottom Margin"),
                             ("margin_left","Left Margin"),("margin_right","Right Margin")]:
            tv, gv = getattr(t_pg, attr), getattr(g_pg, attr)
            if tv > 0 and gv > 0 and abs(tv - gv) > 2:
                issues.append(Issue("Layout", label, SEVERITY_MAJOR, i, 0, 0, "body",
                    f"{tv}pt", f"{gv}pt", f"Page {i} {label} differs"))


def _check_words(tmpl: DocumentData, gen: DocumentData, issues: List[Issue]):
    """
    Align template words to generated words by page+zone, then compare
    every property for matched pairs.
    """
    pages = max(len(tmpl.pages), len(gen.pages), 1)

    for page in range(1, pages + 1):
        for zone in ("header", "footer", "body"):
            t_words = [w for w in tmpl.words if w.page == page and w.zone == zone]
            g_words = [w for w in gen.words  if w.page == page and w.zone == zone]

            if not t_words and not g_words:
                continue

            # ── Align word sequences ──────────────────────────────────────────
            t_texts = [w.text for w in t_words]
            g_texts = [w.text for w in g_words]
            sm      = difflib.SequenceMatcher(None, t_texts, g_texts, autojunk=False)

            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    # Matched words — compare formatting & position
                    for ti, gi in zip(range(i1,i2), range(j1,j2)):
                        tw, gw = t_words[ti], g_words[gi]
                        _compare_word_pair(tw, gw, issues)

                elif tag in ("replace",):
                    # Content mismatch
                    t_chunk = " ".join(t_texts[i1:i2])
                    g_chunk = " ".join(g_texts[j1:j2])
                    ref = t_words[i1]
                    issues.append(Issue(
                        category  = _zone_cat(zone),
                        check     = "Content",
                        severity  = SEVERITY_CRITICAL,
                        page      = page,
                        line      = ref.line,
                        col       = ref.col,
                        zone      = zone,
                        template_val  = repr(t_chunk),
                        generated_val = repr(g_chunk),
                        detail    = f"Page {page} {zone}: text differs"
                    ))

                elif tag == "delete":
                    t_chunk = " ".join(t_texts[i1:i2])
                    ref = t_words[i1]
                    issues.append(Issue(
                        category=_zone_cat(zone), check="Missing Content",
                        severity=SEVERITY_CRITICAL, page=page, line=ref.line,
                        col=ref.col, zone=zone,
                        template_val=repr(t_chunk), generated_val="[MISSING]",
                        detail=f"Page {page} {zone}: text missing in generated"
                    ))

                elif tag == "insert":
                    g_chunk = " ".join(g_texts[j1:j2])
                    ref = g_words[j1]
                    issues.append(Issue(
                        category=_zone_cat(zone), check="Extra Content",
                        severity=SEVERITY_CRITICAL, page=page, line=ref.line,
                        col=ref.col, zone=zone,
                        template_val="[NOT IN TEMPLATE]", generated_val=repr(g_chunk),
                        detail=f"Page {page} {zone}: extra text in generated"
                    ))


def _compare_word_pair(tw: WordToken, gw: WordToken, issues: List[Issue]):
    """Compare every formatting & position property for a matched word pair."""
    p, ln, col, zone = tw.page, tw.line, tw.col, tw.zone
    cat = _zone_cat(zone)

    # ── Content (character-level) ─────────────────────────────────────────────
    if tw.text != gw.text:
        issues.append(Issue(cat, "Word Text", SEVERITY_CRITICAL, p, ln, col, zone,
            repr(tw.text), repr(gw.text), f"Exact word mismatch at line {ln} col {col}"))

    # ── Font name ─────────────────────────────────────────────────────────────
    if tw.font_name and gw.font_name and tw.font_name != gw.font_name:
        issues.append(Issue(cat, "Font Name", SEVERITY_MAJOR, p, ln, col, zone,
            tw.font_name, gw.font_name, f"'{tw.text}' font differs"))

    # ── Font size ─────────────────────────────────────────────────────────────
    if tw.font_size > 0 and gw.font_size > 0:
        if abs(tw.font_size - gw.font_size) > TOL_FONT_SIZE:
            issues.append(Issue(cat, "Font Size", SEVERITY_MAJOR, p, ln, col, zone,
                f"{tw.font_size}pt", f"{gw.font_size}pt",
                f"'{tw.text}' size differs by {abs(tw.font_size-gw.font_size):.1f}pt"))

    # ── Font color ────────────────────────────────────────────────────────────
    if _color_diff(tw.font_color, gw.font_color) > TOL_COLOR:
        issues.append(Issue(cat, "Font Color", SEVERITY_MAJOR, p, ln, col, zone,
            _rgb_str(tw.font_color), _rgb_str(gw.font_color),
            f"'{tw.text}' color differs"))

    # ── Bold ──────────────────────────────────────────────────────────────────
    if tw.bold != gw.bold:
        issues.append(Issue(cat, "Bold", SEVERITY_MAJOR, p, ln, col, zone,
            str(tw.bold), str(gw.bold), f"'{tw.text}' bold style differs"))

    # ── Italic ────────────────────────────────────────────────────────────────
    if tw.italic != gw.italic:
        issues.append(Issue(cat, "Italic", SEVERITY_MAJOR, p, ln, col, zone,
            str(tw.italic), str(gw.italic), f"'{tw.text}' italic style differs"))

    # ── Underline ─────────────────────────────────────────────────────────────
    if tw.underline != gw.underline:
        issues.append(Issue(cat, "Underline", SEVERITY_MINOR, p, ln, col, zone,
            str(tw.underline), str(gw.underline), f"'{tw.text}' underline differs"))

    # ── Strikethrough ─────────────────────────────────────────────────────────
    if tw.strike != gw.strike:
        issues.append(Issue(cat, "Strikethrough", SEVERITY_MINOR, p, ln, col, zone,
            str(tw.strike), str(gw.strike), f"'{tw.text}' strikethrough differs"))

    # ── Position (bbox) ───────────────────────────────────────────────────────
    if tw.bbox and gw.bbox:
        dx = abs(tw.bbox.x0 - gw.bbox.x0)
        dy = abs(tw.bbox.y0 - gw.bbox.y0)
        if dx > TOL_POSITION:
            issues.append(Issue(cat, "Horizontal Position", SEVERITY_MAJOR, p, ln, col, zone,
                f"x={tw.bbox.x0}", f"x={gw.bbox.x0}",
                f"'{tw.text}' X position off by {dx:.1f}px"))
        if dy > TOL_POSITION:
            issues.append(Issue(cat, "Vertical Position", SEVERITY_MAJOR, p, ln, col, zone,
                f"y={tw.bbox.y0}", f"y={gw.bbox.y0}",
                f"'{tw.text}' Y position off by {dy:.1f}px"))


def _check_drawings(tmpl: DocumentData, gen: DocumentData, issues: List[Issue]):
    """Compare borders, lines, rectangles."""
    tp, gp = len(tmpl.drawings), len(gen.drawings)
    if tp != gp:
        issues.append(Issue("Border", "Drawing Count", SEVERITY_MAJOR, 0, 0, 0, "body",
            str(tp), str(gp), f"Template has {tp} drawings, generated has {gp}"))
        return

    for i, (td, gd) in enumerate(zip(tmpl.drawings, gen.drawings)):
        if _color_diff(td.color, gd.color) > TOL_COLOR:
            issues.append(Issue("Border","Border Color", SEVERITY_MAJOR, td.page,0,0,"body",
                _rgb_str(td.color), _rgb_str(gd.color), f"Drawing {i+1} color differs"))
        if abs(td.width - gd.width) > 0.5:
            issues.append(Issue("Border","Border Width", SEVERITY_MINOR, td.page,0,0,"body",
                f"{td.width}pt", f"{gd.width}pt", f"Drawing {i+1} width differs"))
        if abs(td.bbox.x0-gd.bbox.x0)>TOL_POSITION or abs(td.bbox.y0-gd.bbox.y0)>TOL_POSITION:
            issues.append(Issue("Border","Border Position", SEVERITY_MAJOR, td.page,0,0,"body",
                f"({td.bbox.x0},{td.bbox.y0})", f"({gd.bbox.x0},{gd.bbox.y0})",
                f"Drawing {i+1} position differs"))


def _check_text_precise(tmpl: DocumentData, gen: DocumentData, issues: List[Issue]):
    """Character-level precise diff on raw text."""
    from precise_diff import precise_diff
    report = precise_diff(tmpl.raw_text, gen.raw_text)
    for c in report.changes:
        if not c.original and not c.modified:
            continue
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
                             f"context: …{c.context_before}[HERE]{c.context_after}…")
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Visual diff
# ─────────────────────────────────────────────────────────────────────────────

def _visual_diff(tmpl: DocumentData, gen: DocumentData, diff_images: List[Dict]) -> float:
    if not _CV2:
        return 0.0

    t_imgs = tmpl.page_images
    g_imgs = gen.page_images
    if not t_imgs or not g_imgs:
        return 0.0

    scores = []
    max_pages = max(len(t_imgs), len(g_imgs))

    for idx in range(max_pages):
        has_t = idx < len(t_imgs)
        has_g = idx < len(g_imgs)

        blank = lambda sz=(850,1100): Image.new("RGB", sz, (245,245,245))

        if has_t and has_g:
            t_img = t_imgs[idx].convert("RGB")
            g_img = g_imgs[idx].convert("RGB").resize(t_img.size, Image.LANCZOS)
            result = _cv2_annotated_diff(t_img, g_img)
            scores.append(result["similarity"])
            diff_images.append({
                "page": idx+1,
                "template_img":  t_img,
                "generated_img": g_img,
                "diff_img":      result["diff_img"],
                "page_score":    result["similarity"],
                "region_count":  result["region_count"],
                "status":        "compared",
                "note":          None,
            })
        elif has_t:
            t_img = t_imgs[idx].convert("RGB")
            b = blank(t_img.size); _draw_label(b, "MISSING IN GENERATED")
            scores.append(0.0)
            diff_images.append({"page":idx+1,"template_img":t_img,"generated_img":b,
                "diff_img":b.copy(),"page_score":0.0,"region_count":99,
                "status":"missing","note":f"⚠️ Page {idx+1} missing in generated"})
        else:
            g_img = g_imgs[idx].convert("RGB")
            b = blank(g_img.size); _draw_label(b, "NOT IN TEMPLATE")
            scores.append(0.0)
            diff_images.append({"page":idx+1,"template_img":b,"generated_img":g_img,
                "diff_img":b.copy(),"page_score":0.0,"region_count":99,
                "status":"extra","note":f"ℹ️ Page {idx+1} is extra in generated"})

    return sum(scores)/len(scores) if scores else 0.0


def _cv2_annotated_diff(t_img, g_img):
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
        cv2.rectangle(annotated, (x,y), (x+w,y+h), (0,0,220), 2)

    total = t_gray.shape[0] * t_gray.shape[1]
    sim   = max(0.0, (1 - np.count_nonzero(thr)/total) * 100)
    diff_pil = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
    return {"diff_img":diff_pil, "region_count":len(sig), "similarity":round(sim,4)}


def _draw_label(img, label):
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    try: font = ImageFont.truetype("arial.ttf", 22)
    except: font = ImageFont.load_default()
    w,h = img.size
    draw.rectangle([20, h//2-40, w-20, h//2+40], outline=(220,50,50), width=3)
    draw.text((w//2-80, h//2-12), label, fill=(220,50,50), font=font)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _text_similarity(a: str, b: str) -> float:
    if not a and not b: return 100.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sm.quick_ratio() * 100

def _color_diff(c1, c2) -> float:
    if not c1 or not c2: return 0.0
    return math.sqrt(sum((a-b)**2 for a,b in zip(c1,c2)))

def _rgb_str(c) -> str:
    if not c: return "N/A"
    return f"rgb({c[0]},{c[1]},{c[2]})"

def _zone_cat(zone: str) -> str:
    return {"header":"Header","footer":"Footer","body":"Body"}.get(zone,"Body")
