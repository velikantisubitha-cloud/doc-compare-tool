"""
report.py — Generates a self-contained HTML comparison report for download.
"""

from datetime import datetime
from typing import Dict, Any


def generate_html_report(results: Dict[str, Any], tmpl_name: str, gen_name: str) -> str:
    """Build and return a complete HTML report as a string."""

    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overall = results["overall_result"]
    ok_col  = "#22c55e" if overall == "PASS" else "#ef4444"
    badge   = "✅ PASS" if overall == "PASS" else "❌ FAIL"

    def status_badge(value, good_values=("Match", "Not detected")):
        ok = value in good_values
        color = "#22c55e" if ok else "#ef4444"
        icon  = "✓" if ok else "✗"
        return f'<span style="color:{color};font-weight:700">{icon} {value}</span>'

    # Text diff rows
    diff_rows = ""
    for d in results.get("text_diffs", []):
        color = "#ef4444" if d["type"] == "removed" else "#f59e0b" if d["type"] == "changed" else "#22c55e"
        diff_rows += f"""
        <tr>
            <td style="color:{color};font-weight:600">{d['type'].upper()}</td>
            <td style="font-family:monospace;font-size:13px">{_esc(d['text'])}</td>
        </tr>"""

    if not diff_rows:
        diff_rows = '<tr><td colspan="2" style="color:#22c55e">No text differences detected</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Document Comparison Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f8fafc; color: #1e293b; padding: 32px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 24px;
           box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  h1 {{ font-size: 26px; font-weight: 700; }}
  h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #334155; }}
  .badge {{ display:inline-block; padding: 8px 20px; border-radius: 8px;
            font-size:22px; font-weight:800; color:{ok_col};
            background:{ok_col}22; border:2px solid {ok_col}; }}
  .meta {{ color: #64748b; font-size: 13px; margin-top: 6px; }}
  .grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }}
  .metric {{ background: #f1f5f9; border-radius: 10px; padding: 16px; text-align:center; }}
  .metric-label {{ font-size:12px; color:#64748b; text-transform:uppercase; letter-spacing:.06em; }}
  .metric-value {{ font-size:16px; font-weight:700; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#f1f5f9; padding:10px 14px; text-align:left; font-size:13px; color:#64748b; }}
  td {{ padding:10px 14px; border-bottom:1px solid #f1f5f9; vertical-align:top; }}
  .footer-note {{ color:#94a3b8; font-size:12px; text-align:center; margin-top:32px; }}
</style>
</head>
<body>

<div class="card">
  <h1>📄 Document Comparison Report</h1>
  <p class="meta">Generated: {now}</p>
  <p class="meta">Template: <strong>{_esc(tmpl_name)}</strong> &nbsp;|&nbsp; Generated: <strong>{_esc(gen_name)}</strong></p>
  <br>
  <div class="badge">{badge}</div>
  <p class="meta" style="margin-top:8px">Similarity score: <strong>{results.get('similarity_score', 'N/A')}%</strong></p>
</div>

<div class="card">
  <h2>Summary Metrics</h2>
  <div class="grid">
    <div class="metric">
      <div class="metric-label">Header</div>
      <div class="metric-value">{status_badge(results['header_match'])}</div>
    </div>
    <div class="metric">
      <div class="metric-label">Footer</div>
      <div class="metric-value">{status_badge(results['footer_match'])}</div>
    </div>
    <div class="metric">
      <div class="metric-label">Content Issues</div>
      <div class="metric-value">{results['content_issues']}</div>
    </div>
    <div class="metric">
      <div class="metric-label">Layout Issues</div>
      <div class="metric-value">{results['layout_issues']}</div>
    </div>
    <div class="metric">
      <div class="metric-label">Font/Style</div>
      <div class="metric-value">{status_badge(results['font_diff'], good_values=('Not detected',))}</div>
    </div>
  </div>
</div>

<div class="card">
  <h2>Text Differences</h2>
  <table>
    <thead><tr><th>Type</th><th>Content</th></tr></thead>
    <tbody>{diff_rows}</tbody>
  </table>
</div>

{_ai_section(results.get('ai_analysis'))}

<p class="footer-note">Smart Document Comparison Tool &mdash; Collectors Module &mdash; {now}</p>
</body>
</html>"""


def _ai_section(ai_text):
    if not ai_text:
        return ""
    return f"""
<div class="card">
  <h2>🤖 AI Analysis</h2>
  <p style="white-space:pre-wrap;line-height:1.7">{_esc(ai_text)}</p>
</div>"""


def _esc(s: str) -> str:
    """HTML-escape a string."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
