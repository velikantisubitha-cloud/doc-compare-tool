Smart Document Comparison Tool — Final v3
Collectors Module — Complete Deep Comparison

========================================
SETUP (run once)
========================================

1. Open PowerShell in this folder

2. Install dependencies:
   pip install -r requirements.txt

3. Run the app:
   python -m streamlit run app.py

4. Open browser: http://localhost:8501

========================================
FILES
========================================
app.py              Main Streamlit UI
extractor.py        Deep metadata extraction
deep_comparator.py  All comparison logic
precise_diff.py     Character-level Myers diff
ai_analyzer.py      Claude AI analysis
requirements.txt    Python packages

========================================
ALL CHECKS IN v3
========================================
TEXT:
  - Every word exact text (character-level)
  - Missing / extra / changed words
  - Header, body, footer zones

FONT & STYLE:
  - Font name
  - Font size (pt)
  - Font color (RGB)
  - Bold / Italic / Underline / Strikethrough

POSITION & LAYOUT:
  - Word X Y position (bounding box)
  - Text alignment (Left/Center/Right/Justify)
  - Page size (width x height)
  - Page count and rotation
  - Margins (top/bottom/left/right)

SPACING (NEW in v3):
  - Line spacing in pt
  - Paragraph spacing before/after
  - Letter spacing / kerning

VISUAL (NEW in v3):
  - Background highlight color
  - Embedded image pixel similarity
  - Table cell border color/width/style
  - Watermark text and image detection
  - PDF form fields (name/type/value)

VISUAL DIFF:
  - OpenCV pixel diff per page
  - Red boxes on changed regions
  - Side-by-side comparison

REPORTS:
  - Overall score 0-100%
  - Per-section: Header / Body / Footer %
  - PASS / FAIL verdict
  - Critical / Major / Minor severity
  - HTML report download
  - JSON report download
  - AI analysis with fix recommendations
