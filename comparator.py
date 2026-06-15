"""
comparator.py — Core comparison logic (file-type agnostic).
Delegates loading/extraction to file_handler.py.
"""

import os
import logging
import difflib
from typing import List, Dict, Any

import numpy as np
from PIL import Image

from file_handler import file_to_images, file_to_text, get_file_category

logger = logging.getLogger(__name__)

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    from rapidfuzz import fuzz as rfuzz
    _RAPIDFUZZ = True
except ImportError:
    _RAPIDFUZZ = False


class DocumentComparator:
    def __init__(self, template_path: str, generated_path: str, work_dir: str):
        self.template_path  = template_path
        self.generated_path = generated_path
        self.work_dir       = work_dir

    def run(self) -> Dict[str, Any]:
        tmpl_cat = get_file_category(self.template_path)
        gen_cat  = get_file_category(self.generated_path)

        # Convert to images
        tmpl_imgs = file_to_images(self.template_path)
        gen_imgs  = file_to_images(self.generated_path)

        # Extract text
        tmpl_text = file_to_text(self.template_path, tmpl_imgs)
        gen_text  = file_to_text(self.generated_path, gen_imgs)

        # Compare
        text_result  = compare_text(tmpl_text, gen_text)
        diff_images, layout_issues = compare_layout(tmpl_imgs, gen_imgs)
        font_diff    = detect_font_diff(tmpl_imgs, gen_imgs)
        header_match = _zone_match(tmpl_text, gen_text, "header")
        footer_match = _zone_match(tmpl_text, gen_text, "footer")

        has_issues = (
            header_match == "Mismatch"
            or footer_match == "Mismatch"
            or text_result["issue_count"] > 0
            or layout_issues > 0
            or font_diff == "Detected"
        )

        return {
            "overall_result":   "FAIL" if has_issues else "PASS",
            "header_match":     header_match,
            "footer_match":     footer_match,
            "content_issues":   text_result["issue_count"],
            "layout_issues":    layout_issues,
            "font_diff":        font_diff,
            "text_diffs":       text_result["diffs"],
            "similarity_score": text_result["similarity"],
            "diff_images":      diff_images,
            "template_text":    tmpl_text,
            "generated_text":   gen_text,
            "template_type":    tmpl_cat,
            "generated_type":   gen_cat,
            "ai_analysis":      None,
        }


# ── Text comparison ───────────────────────────────────────────────────────────

def compare_text(template_text: str, generated_text: str) -> Dict[str, Any]:
    tmpl_lines = [l.strip() for l in template_text.splitlines() if l.strip()]
    gen_lines  = [l.strip() for l in generated_text.splitlines() if l.strip()]

    if _RAPIDFUZZ:
        similarity = rfuzz.token_set_ratio(template_text, generated_text)
    else:
        sm = difflib.SequenceMatcher(None, template_text, generated_text)
        similarity = sm.ratio() * 100

    diffs = []
    matcher = difflib.SequenceMatcher(None, tmpl_lines, gen_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            for line in tmpl_lines[i1:i2]:
                diffs.append({"type": "removed", "text": line})
        elif tag == "insert":
            for line in gen_lines[j1:j2]:
                diffs.append({"type": "added", "text": line})
        elif tag == "replace":
            for line in tmpl_lines[i1:i2]:
                diffs.append({"type": "changed", "text": f"Expected: {line}"})
            for line in gen_lines[j1:j2]:
                diffs.append({"type": "changed", "text": f"Got:      {line}"})

    return {
        "similarity":  round(similarity, 2),
        "issue_count": len([d for d in diffs if d["type"] in ("removed", "changed")]),
        "diffs":       diffs[:40],
    }


# ── Layout comparison ─────────────────────────────────────────────────────────

def compare_layout(template_imgs, generated_imgs):
    """
    Compare every page across both documents.
    - Pages present in both   → pixel diff with bounding boxes
    - Pages missing in generated → flagged as 0% similarity (MISSING page)
    - Extra pages in generated   → flagged as 0% similarity (EXTRA page)
    """
    diff_images   = []
    total_issues  = 0
    t_count       = len(template_imgs)
    g_count       = len(generated_imgs)
    max_pages     = max(t_count, g_count)

    # Blank white placeholder for missing pages
    def _blank(size=(850, 1100)):
        return Image.new("RGB", size, (245, 245, 245))

    for idx in range(max_pages):
        has_template  = idx < t_count
        has_generated = idx < g_count

        t_img = template_imgs[idx].convert("RGB")  if has_template  else None
        g_img = generated_imgs[idx].convert("RGB") if has_generated else None

        # ── Both pages exist → normal diff ───────────────────────────────────
        if has_template and has_generated:
            g_img_resized = g_img.resize(t_img.size, Image.LANCZOS)
            result = _cv2_diff(t_img, g_img_resized) if _CV2 else _pillow_diff(t_img, g_img_resized)
            total_issues += result["region_count"]
            diff_images.append({
                "template_img":  t_img,
                "generated_img": g_img_resized,
                "diff_img":      result["diff_img"],
                "page_score":    result["similarity"],
                "status":        "compared",
                "note":          None,
            })

        # ── Page exists in template but MISSING in generated ─────────────────
        elif has_template and not has_generated:
            blank = _blank(t_img.size)
            # Draw red "MISSING" label on blank
            _draw_missing_label(blank, "MISSING IN GENERATED")
            total_issues += 5   # count as significant issue
            diff_images.append({
                "template_img":  t_img,
                "generated_img": blank,
                "diff_img":      blank.copy(),
                "page_score":    0.0,
                "status":        "missing",
                "note":          f"⚠️ Page {idx+1} exists in template but is MISSING in generated document",
            })

        # ── Extra page in generated that template doesn't have ───────────────
        else:
            blank = _blank(g_img.size)
            _draw_missing_label(blank, "NOT IN TEMPLATE")
            total_issues += 3
            diff_images.append({
                "template_img":  blank,
                "generated_img": g_img,
                "diff_img":      blank.copy(),
                "page_score":    0.0,
                "status":        "extra",
                "note":          f"ℹ️ Page {idx+1} is an EXTRA page in generated (not in template)",
            })

    return diff_images, total_issues


def _draw_missing_label(img: Image.Image, label: str):
    """Draw a centred red warning label on an image."""
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    w, h = img.size
    draw.rectangle([20, h//2 - 40, w - 20, h//2 + 40], outline=(220, 50, 50), width=3)
    draw.text((w // 2 - 80, h // 2 - 12), label, fill=(220, 50, 50), font=font)


def _cv2_diff(t_img, g_img):
    t_arr  = cv2.cvtColor(np.array(t_img), cv2.COLOR_RGB2BGR)
    g_arr  = cv2.cvtColor(np.array(g_img), cv2.COLOR_RGB2BGR)
    t_gray = cv2.cvtColor(t_arr, cv2.COLOR_BGR2GRAY)
    g_gray = cv2.cvtColor(g_arr, cv2.COLOR_BGR2GRAY)

    diff = cv2.absdiff(t_gray, g_gray)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_DILATE, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    annotated   = g_arr.copy()
    significant = [c for c in contours if cv2.contourArea(c) > 200]
    for c in significant:
        x, y, w, h = cv2.boundingRect(c)
        cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 0, 220), 2)

    total_px   = t_gray.shape[0] * t_gray.shape[1]
    similarity = max(0, (1 - np.count_nonzero(thresh) / total_px) * 100)
    diff_pil   = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
    return {"diff_img": diff_pil, "region_count": len(significant), "similarity": round(similarity, 2)}


def _pillow_diff(t_img, g_img):
    from PIL import ImageChops, ImageDraw
    diff      = ImageChops.difference(t_img, g_img)
    diff_arr  = np.array(diff.convert("L"))
    mask      = diff_arr > 25
    total_px  = mask.size
    similarity = max(0, (1 - mask.sum() / total_px) * 100)
    annotated  = g_img.copy()
    draw       = ImageDraw.Draw(annotated, "RGBA")
    rows, cols = np.where(mask)
    for r, c in zip(rows[::5], cols[::5]):
        draw.point((c, r), fill=(220, 0, 0, 120))
    return {"diff_img": annotated, "region_count": min(int(mask.sum()) // 500, 99), "similarity": round(similarity, 2)}


# ── Font heuristic ────────────────────────────────────────────────────────────

def detect_font_diff(template_imgs, generated_imgs):
    if not template_imgs or not generated_imgs:
        return "Not detected"
    t_gray = np.array(template_imgs[0].convert("L"), dtype=np.float32)
    g_gray = np.array(generated_imgs[0].convert("L"), dtype=np.float32)
    t_hist, _ = np.histogram(t_gray.flatten(), bins=64, range=(0, 256))
    g_hist, _ = np.histogram(g_gray.flatten(), bins=64, range=(0, 256))
    t_hist = t_hist / (t_hist.sum() + 1e-8)
    g_hist = g_hist / (g_hist.sum() + 1e-8)
    chi2 = float(np.sum((t_hist - g_hist) ** 2 / (t_hist + g_hist + 1e-8)))
    return "Detected" if chi2 > 0.05 else "Not detected"


# ── Zone match ────────────────────────────────────────────────────────────────

def _zone_match(template_text, generated_text, zone):
    t_lines = [l.strip() for l in template_text.splitlines() if l.strip()]
    g_lines = [l.strip() for l in generated_text.splitlines() if l.strip()]
    if not t_lines or not g_lines:
        return "Unknown"
    t_zone = "\n".join(t_lines[:5]  if zone == "header" else t_lines[-5:])
    g_zone = "\n".join(g_lines[:5]  if zone == "header" else g_lines[-5:])
    if _RAPIDFUZZ:
        score = rfuzz.token_set_ratio(t_zone, g_zone)
    else:
        score = difflib.SequenceMatcher(None, t_zone, g_zone).ratio() * 100
    return "Match" if score >= 85 else "Mismatch"


# ── Precise character-level diff (exposed for UI) ─────────────────────────────

def run_precise_diff(template_text: str, generated_text: str):
    """Call the precise diff engine. Returns a DiffReport."""
    from precise_diff import precise_diff
    return precise_diff(template_text, generated_text)
