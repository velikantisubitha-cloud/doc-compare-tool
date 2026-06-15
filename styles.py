"""
styles.py — All custom CSS for the Streamlit app.
"""

CUSTOM_CSS = """
<style>
/* ── Google Fonts ─────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

/* ── Reset & base ─────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── App Header ───────────────────────────────────────── */
.app-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #0f172a 100%);
    border-radius: 16px;
    padding: 40px 48px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
}
.app-header::after {
    content: "";
    position: absolute;
    top: -40px; right: -40px;
    width: 280px; height: 280px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 70%);
    pointer-events: none;
}
.header-badge {
    display: inline-block;
    background: rgba(59,130,246,0.2);
    color: #93c5fd;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    padding: 4px 12px;
    border-radius: 20px;
    border: 1px solid rgba(93,165,246,0.3);
    margin-bottom: 14px;
}
.app-title {
    font-size: 32px !important;
    font-weight: 800 !important;
    color: #f8fafc !important;
    margin: 0 0 10px 0 !important;
    letter-spacing: -0.02em;
}
.app-subtitle {
    color: #94a3b8;
    font-size: 15px;
    margin: 0;
}

/* ── Section labels ───────────────────────────────────── */
.section-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: #64748b;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e2e8f0;
}

/* ── Upload cards ─────────────────────────────────────── */
.upload-card {
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 14px;
    border: 1px solid;
}
.template-card {
    background: #eff6ff;
    border-color: #bfdbfe;
}
.generated-card {
    background: #f0fdf4;
    border-color: #bbf7d0;
}
.upload-card-icon { font-size: 28px; }
.upload-card-title {
    font-size: 15px;
    font-weight: 700;
    color: #1e293b;
}
.upload-card-desc {
    font-size: 12px;
    color: #64748b;
    margin-top: 2px;
}

/* ── File chips ───────────────────────────────────────── */
.file-chip {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    margin-top: 4px;
}
.file-chip.success {
    background: #dcfce7;
    color: #16a34a;
    border: 1px solid #bbf7d0;
}

/* ── Hint text ────────────────────────────────────────── */
.info-hint {
    color: #94a3b8;
    font-size: 13px;
    padding-top: 12px;
}

/* ── Result hero ──────────────────────────────────────── */
.result-hero {
    padding: 20px 28px;
    border-radius: 14px;
    font-size: 22px;
    font-weight: 800;
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 24px;
    border: 2px solid;
}
.badge-pass {
    background: #f0fdf4;
    border-color: #86efac;
    color: #15803d;
}
.badge-fail {
    background: #fef2f2;
    border-color: #fca5a5;
    color: #dc2626;
}
.result-icon { font-size: 28px; }
.result-label { font-weight: 600; color: #475569; font-size: 16px; }
.result-value { font-size: 26px; font-weight: 900; }

/* ── Metric cards ─────────────────────────────────────── */
.metric-card {
    border-radius: 12px;
    padding: 18px 14px;
    text-align: center;
    border: 1px solid;
}
.metric-ok {
    background: #f0fdf4;
    border-color: #bbf7d0;
}
.metric-issue {
    background: #fef9f0;
    border-color: #fed7aa;
}
.metric-icon {
    font-size: 22px;
    font-weight: 900;
    margin-bottom: 6px;
}
.metric-ok .metric-icon  { color: #22c55e; }
.metric-issue .metric-icon { color: #f59e0b; }
.metric-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 14px;
    font-weight: 700;
    color: #1e293b;
}

/* ── Diff rows ────────────────────────────────────────── */
.diff-row {
    padding: 10px 14px;
    margin-bottom: 6px;
    background: #f8fafc;
    border-radius: 8px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 13px;
}
.diff-icon  { font-weight: 900; font-size: 16px; flex-shrink: 0; }
.diff-type  { font-weight: 700; font-size: 11px; letter-spacing:.06em; padding-top:2px; flex-shrink:0; width:70px; }
.diff-text  { font-family: 'JetBrains Mono', monospace; color: #334155; line-height: 1.5; }

/* ── Similarity bar ───────────────────────────────────── */
.similarity-bar-wrap {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 20px;
    font-size: 13px;
    color: #475569;
}
.similarity-bar {
    flex: 1;
    height: 10px;
    background: #e2e8f0;
    border-radius: 99px;
    overflow: hidden;
}
.similarity-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #22c55e);
    border-radius: 99px;
    transition: width .6s ease;
}

/* ── Image labels ─────────────────────────────────────── */
.img-label {
    font-size: 12px;
    font-weight: 700;
    color: #64748b;
    text-align: center;
    margin-bottom: 6px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.page-score {
    font-size: 13px;
    color: #64748b;
    text-align: right;
    margin-top: -8px;
}

/* ── AI card ──────────────────────────────────────────── */
.ai-card {
    background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
    border: 1px solid #bae6fd;
    border-radius: 12px;
    overflow: hidden;
}
.ai-header {
    background: #1e3a5f;
    color: #e2e8f0;
    font-weight: 700;
    font-size: 13px;
    padding: 10px 18px;
    letter-spacing: 0.05em;
}
.ai-body {
    padding: 18px;
    font-size: 14px;
    line-height: 1.75;
    color: #1e293b;
    white-space: pre-wrap;
}

/* ── No issues ────────────────────────────────────────── */
.no-issues {
    color: #16a34a;
    font-weight: 600;
    font-size: 14px;
    padding: 16px;
    background: #f0fdf4;
    border-radius: 8px;
}

/* ── Streamlit overrides ──────────────────────────────── */
div[data-testid="stFileUploader"] {
    background: #f8fafc;
    border: 2px dashed #cbd5e1;
    border-radius: 10px;
    padding: 8px;
    transition: border-color .2s;
}
div[data-testid="stFileUploader"]:hover { border-color: #3b82f6; }

/* Compare button */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    padding: 12px 28px !important;
    border: none !important;
    border-radius: 10px !important;
    transition: all .2s !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.35) !important;
}
div[data-testid="stButton"] > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 18px rgba(37,99,235,0.45) !important;
}
div[data-testid="stButton"] > button:disabled {
    background: #94a3b8 !important;
    box-shadow: none !important;
    transform: none !important;
    cursor: not-allowed !important;
}

/* Tab styling */
div[data-testid="stTabs"] [data-baseweb="tab"] {
    font-weight: 600;
    font-size: 14px;
}

/* Hide default Streamlit header */
header[data-testid="stHeader"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
"""
