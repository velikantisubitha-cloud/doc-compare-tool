# Smart Document Comparison Tool

Production-ready Streamlit app for validating generated letter outputs against template PDFs in a Collectors module.

---

## Features

| Feature | Details |
|---|---|
| **PDF Rendering** | PyMuPDF (primary) → pdf2image (fallback) |
| **Text Extraction** | PyMuPDF native → pytesseract OCR fallback |
| **Text Comparison** | rapidfuzz similarity + difflib line diffs |
| **Layout Analysis** | OpenCV structural diff + bounding boxes |
| **Font Heuristic** | Luminance histogram chi-squared distance |
| **AI Analysis** | Built-in Claude API (no key needed) |
| **Report Export** | Self-contained HTML download |

---

## Quick Start

### 1. Install system dependencies

```bash
# macOS
brew install tesseract poppler

# Ubuntu / Debian
sudo apt-get install -y tesseract-ocr poppler-utils

# Windows
# Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
# Install Poppler from: https://github.com/oschwartz10612/poppler-windows
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## Project Structure

```
doc_compare/
├── app.py           # Streamlit UI
├── comparator.py    # Core comparison logic
├── ai_analyzer.py   # Claude AI analysis
├── report.py        # HTML report generator
├── styles.py        # Custom CSS
├── requirements.txt
└── README.md
```

---

## How It Works

```
Upload PDFs
    ↓
convert_to_images()   — PyMuPDF / pdf2image → PIL Images
    ↓
extract_text()        — Native text or OCR (pytesseract)
    ↓
compare_text()        — rapidfuzz similarity + difflib diffs
    ↓
compare_layout()      — OpenCV absdiff + contour detection
    ↓
detect_font_diff()    — Histogram chi-squared heuristic
    ↓
generate_report()     — Structured result + HTML export
    ↓
AI Analysis (optional) — Claude explains findings + recommendations
```

---

## Result Codes

| Check | Pass Condition |
|---|---|
| Header | ≥ 85% similarity on first 5 lines |
| Footer | ≥ 85% similarity on last 5 lines |
| Content | 0 removed/changed lines |
| Layout | 0 significant contour regions |
| Font/Style | χ² histogram distance < 0.05 |
| **Overall** | **All checks pass** |

---

## Configuration

Edit `comparator.py` constants:

```python
DPI          = 150   # Image resolution (higher = slower but more accurate)
ZONE_LINES   = 5     # Lines to check for header/footer
MIN_CONTOUR  = 200   # Min pixel area for layout issue
ZONE_THRESH  = 85    # % similarity for header/footer pass
FONT_THRESH  = 0.05  # Chi² threshold for font diff
```

---

## Troubleshooting

**"No text extracted"** — Install Tesseract and ensure it's on your PATH.  
**"PDF rendering failed"** — Install poppler (for pdf2image) or PyMuPDF (`pip install PyMuPDF`).  
**OpenCV errors** — Use `opencv-python-headless` (not `opencv-python`) in server environments.  
**AI Analysis unavailable** — The Claude API integration works automatically in the Claude.ai environment; in other environments set up an API key via the Anthropic SDK.
