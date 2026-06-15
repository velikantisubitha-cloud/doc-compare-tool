"""
Smart Document Comparison Tool — Final v3
Collectors Module — Complete Deep Comparison
"""

import streamlit as st
import tempfile, os, json
from datetime import datetime

st.set_page_config(
    page_title="Smart Document Comparison Tool",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Module-level helpers ──────────────────────────────────────────────────────
def rgb_str(c):
    if not c: return "N/A"
    try: return f"rgb({c[0]},{c[1]},{c[2]})"
    except: return str(c)


def build_report(report, tmpl_name, gen_name):
    from deep_comparator import SEVERITY_CRITICAL, SEVERITY_MAJOR, SEVERITY_MINOR
    sc  = report.count_by_severity()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok  = report.overall_result == "PASS"
    ok_col = "#22c55e" if ok else "#ef4444"

    json_out = json.dumps({
        "generated_at":      now,
        "template":          tmpl_name,
        "generated":         gen_name,
        "overall_result":    report.overall_result,
        "overall_score":     report.overall_score,
        "text_similarity":   report.text_similarity,
        "visual_similarity": report.visual_similarity,
        "section_scores":    report.section_scores,
        "issue_counts":      sc,
        "issues": [
            {"category": i.category, "check": i.check, "severity": i.severity,
             "page": i.page, "line": i.line, "col": i.col, "zone": i.zone,
             "template_val": i.template_val, "generated_val": i.generated_val,
             "detail": i.detail}
            for i in report.issues
        ]
    }, indent=2)

    rows = ""
    for i in report.issues:
        bg  = "#fef2f2" if i.severity==SEVERITY_CRITICAL else "#fff7ed" if i.severity==SEVERITY_MAJOR else "#f0f9ff"
        bdr = "#ef4444" if i.severity==SEVERITY_CRITICAL else "#f97316" if i.severity==SEVERITY_MAJOR else "#38bdf8"
        rows += f"""<tr style="background:{bg};border-left:3px solid {bdr}">
          <td style="padding:8px;font-weight:700;color:{bdr}">{i.severity}</td>
          <td style="padding:8px">{i.category}</td>
          <td style="padding:8px">{i.check}</td>
          <td style="padding:8px">p{i.page} L{i.line} C{i.col} [{i.zone}]</td>
          <td style="padding:8px;font-family:monospace;font-size:12px">{i.template_val}</td>
          <td style="padding:8px;font-family:monospace;font-size:12px">{i.generated_val}</td>
          <td style="padding:8px;font-size:12px;color:#64748b">{i.detail}</td>
        </tr>"""
    if not rows:
        rows = "<tr><td colspan='7' style='padding:16px;color:#22c55e;font-weight:600'>No issues — perfect match</td></tr>"

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Comparison Report — {now}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;color:#1e293b;padding:32px;margin:0}}
.card{{background:#fff;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
h1{{font-size:22px;font-weight:800;margin-bottom:4px}} h2{{font-size:15px;font-weight:700;color:#334155;margin-bottom:14px}}
.badge{{display:inline-block;padding:10px 24px;border-radius:8px;font-size:18px;font-weight:800;color:{ok_col};background:{ok_col}22;border:2px solid {ok_col}}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.metric{{background:#f1f5f9;border-radius:10px;padding:14px;text-align:center}}
.mv{{font-size:20px;font-weight:800}} .ml{{font-size:11px;color:#64748b;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#f1f5f9;padding:10px 12px;text-align:left;color:#64748b;font-size:12px}}
td{{padding:8px 12px;border-bottom:1px solid #f1f5f9;vertical-align:top}}
</style></head><body>
<div class="card">
  <h1>📄 Deep Document Comparison Report</h1>
  <p style="color:#64748b;font-size:13px">Generated: {now}<br>
     Template: <strong>{tmpl_name}</strong> &nbsp;|&nbsp; Generated: <strong>{gen_name}</strong></p>
  <br><div class="badge">{"✅ PASS — Documents match" if ok else "❌ FAIL — Differences found"}</div>
</div>
<div class="card">
  <h2>Scores</h2>
  <div class="grid">
    <div class="metric"><div class="ml">Overall Score</div><div class="mv">{report.overall_score}%</div></div>
    <div class="metric"><div class="ml">Text Similarity</div><div class="mv">{report.text_similarity:.2f}%</div></div>
    <div class="metric"><div class="ml">Visual Similarity</div><div class="mv">{report.visual_similarity:.2f}%</div></div>
    <div class="metric"><div class="ml">Total Issues</div><div class="mv">{len(report.issues)}</div></div>
    <div class="metric"><div class="ml">Critical</div><div class="mv" style="color:#dc2626">{sc[SEVERITY_CRITICAL]}</div></div>
    <div class="metric"><div class="ml">Major</div><div class="mv" style="color:#f97316">{sc[SEVERITY_MAJOR]}</div></div>
    <div class="metric"><div class="ml">Minor</div><div class="mv" style="color:#0ea5e9">{sc[SEVERITY_MINOR]}</div></div>
    <div class="metric"><div class="ml">Header Score</div><div class="mv">{report.section_scores.get("header",0)}%</div></div>
  </div>
</div>
<div class="card">
  <h2>All Issues ({len(report.issues)})</h2>
  <table><thead><tr><th>Severity</th><th>Category</th><th>Check</th><th>Location</th><th>Template</th><th>Generated</th><th>Detail</th></tr></thead>
  <tbody>{rows}</tbody></table>
</div>
</body></html>"""
    return {"html": html, "json": json_out}


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.app-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #0f172a 100%);
    border-radius: 16px; padding: 40px 48px; margin-bottom: 24px;
}
.app-title { color:#f8fafc !important; font-size:30px !important; font-weight:800 !important; margin:0 !important; }
.app-sub   { color:#94a3b8; font-size:14px; margin-top:8px; }
.badge-pill {
    display:inline-block; background:rgba(59,130,246,0.2); color:#93c5fd;
    font-size:11px; font-weight:700; letter-spacing:.1em; padding:3px 12px;
    border-radius:20px; border:1px solid rgba(93,165,246,0.3); margin-bottom:12px;
}

.checks-grid {
    background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px;
    padding:20px 24px; margin-bottom:24px;
}
.checks-grid-title {
    font-size:12px; font-weight:700; color:#64748b; text-transform:uppercase;
    letter-spacing:.1em; margin-bottom:14px;
}
.checks-inner {
    display:grid; grid-template-columns:repeat(3,1fr); gap:5px 20px;
}
.check-item { font-size:13px; color:#334155; padding:3px 0; }

.upload-card {
    border-radius:12px; padding:16px 20px; margin-bottom:4px;
}
.upload-card-t { background:#eff6ff; border:2px dashed #93c5fd; }
.upload-card-g { background:#f0fdf4; border:2px dashed #86efac; }
.upload-card-title { font-size:15px; font-weight:700; color:#1e293b; margin-bottom:3px; }
.upload-card-desc  { font-size:12px; color:#64748b; }

.file-accepted {
    display:inline-block; background:#dcfce7; color:#16a34a;
    border:1px solid #bbf7d0; border-radius:20px;
    font-size:12px; font-weight:600; padding:4px 14px; margin-top:6px;
}

.result-pass { background:#f0fdf4; border:2px solid #86efac; border-radius:12px; padding:18px 24px; font-size:20px; font-weight:800; color:#15803d; margin-bottom:20px; }
.result-fail { background:#fef2f2; border:2px solid #fca5a5; border-radius:12px; padding:18px 24px; font-size:20px; font-weight:800; color:#dc2626; margin-bottom:20px; }

.mcard { border-radius:10px; padding:14px; text-align:center; border:1px solid #e2e8f0; }
.mok   { background:#f0fdf4; border-color:#bbf7d0; }
.mwarn { background:#fef9f0; border-color:#fed7aa; }
.mfail { background:#fef2f2; border-color:#fecaca; }
.mlbl  { font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
.mval  { font-size:16px; font-weight:800; color:#1e293b; }
.msub  { font-size:10px; color:#94a3b8; margin-top:2px; }

.issue-row { border-radius:8px; padding:12px 16px; margin-bottom:8px; }
.i-crit { background:#fef2f2; border-left:4px solid #ef4444; }
.i-major{ background:#fff7ed; border-left:4px solid #f97316; }
.i-minor{ background:#f0f9ff; border-left:4px solid #38bdf8; }
.i-sev  { font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; margin-bottom:3px; }
.i-loc  { font-size:11px; color:#64748b; margin-bottom:5px; }
.i-vals { font-family:'JetBrains Mono',monospace; font-size:12px; color:#334155;
          background:#fff; border-radius:6px; padding:8px 10px;
          border:1px solid #e2e8f0; line-height:1.8; }

.chk-row { display:flex; align-items:center; gap:12px; padding:9px 14px;
           border-radius:8px; margin-bottom:4px; background:#f8fafc; font-size:13px; }
.chk-name { font-weight:600; color:#1e293b; flex:1; }
.chk-vals { font-family:'JetBrains Mono',monospace; font-size:11px; color:#64748b; }

.img-lbl { font-size:11px; font-weight:700; color:#64748b; text-align:center;
           text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px;
           padding:3px; background:#f1f5f9; border-radius:4px; }

.ai-box  { background:#eff6ff; border:1px solid #bae6fd; border-radius:12px; overflow:hidden; margin-top:8px; }
.ai-head { background:#1e3a5f; color:#e2e8f0; font-weight:700; font-size:13px; padding:10px 18px; }
.ai-body { padding:16px 18px; font-size:14px; line-height:1.75; white-space:pre-wrap; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="badge-pill">COLLECTORS MODULE — COMPLETE DEEP COMPARISON v3</div>
  <div class="app-title">📄 Smart Document Comparison Tool</div>
  <div class="app-sub">
    Full accuracy validation &nbsp;·&nbsp;
    Content &nbsp;·&nbsp; Font &nbsp;·&nbsp; Size &nbsp;·&nbsp; Color &nbsp;·&nbsp;
    Position &nbsp;·&nbsp; Alignment &nbsp;·&nbsp; Spacing &nbsp;·&nbsp;
    Images &nbsp;·&nbsp; Tables &nbsp;·&nbsp; Watermarks &nbsp;·&nbsp; Form Fields
  </div>
</div>
""", unsafe_allow_html=True)

# ── What gets compared ────────────────────────────────────────────────────────
st.markdown("""
<div class="checks-grid">
  <div class="checks-grid-title">✅ Everything This Tool Compares</div>
  <div class="checks-inner">
    <div class="check-item">📄 Page count and page size</div>
    <div class="check-item">📐 Margins — top, bottom, left, right</div>
    <div class="check-item">🔤 Every word — exact text, character-level</div>
    <div class="check-item">🖋️ Font name — Arial vs Times etc.</div>
    <div class="check-item">📏 Font size in pt — tolerance 0.5pt</div>
    <div class="check-item">🎨 Font color RGB — tolerance 10/channel</div>
    <div class="check-item">𝗕 Bold / Italic / Underline / Strikethrough</div>
    <div class="check-item">📍 Word X Y position — tolerance 3px</div>
    <div class="check-item">↔️ Text alignment — Left/Center/Right/Justify</div>
    <div class="check-item">📏 Line spacing in pt</div>
    <div class="check-item">📏 Paragraph spacing before and after</div>
    <div class="check-item">🔡 Letter spacing / kerning in pt</div>
    <div class="check-item">🖌️ Background highlight color</div>
    <div class="check-item">🖼️ Embedded images — pixel similarity</div>
    <div class="check-item">▭ Table cell borders — color, width, style</div>
    <div class="check-item">💧 Watermarks — text and image</div>
    <div class="check-item">📋 PDF form fields — name, type, value</div>
    <div class="check-item">▭ Borders, lines, rectangles</div>
    <div class="check-item">🔄 Page rotation</div>
    <div class="check-item">🖼️ Visual pixel diff — OpenCV per page</div>
    <div class="check-item">🔬 Character-level Myers diff</div>
    <div class="check-item">🏷️ Header zone — all checks applied</div>
    <div class="check-item">🏷️ Footer zone — all checks applied</div>
    <div class="check-item">🏆 Overall match score 0 to 100%</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Upload ────────────────────────────────────────────────────────────────────
st.markdown("### Step 1 — Upload Documents")

TYPES = ["pdf","docx","txt","csv","json","xml","html","md","log","yaml","png","jpg","jpeg"]

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div class="upload-card upload-card-t">
      <div class="upload-card-title">📋 Template Letter</div>
      <div class="upload-card-desc">Reference / expected format</div>
    </div>""", unsafe_allow_html=True)
    template_file = st.file_uploader(
        " ", type=TYPES, key="tmpl_v3",
        label_visibility="hidden"
    )
    if template_file:
        st.markdown(f'<div class="file-accepted">✓ &nbsp;{template_file.name}</div>',
                    unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="upload-card upload-card-g">
      <div class="upload-card-title">📄 Generated Letter</div>
      <div class="upload-card-desc">Actual output to validate</div>
    </div>""", unsafe_allow_html=True)
    generated_file = st.file_uploader(
        " ", type=TYPES, key="gen_v3",
        label_visibility="hidden"
    )
    if generated_file:
        st.markdown(f'<div class="file-accepted">✓ &nbsp;{generated_file.name}</div>',
                    unsafe_allow_html=True)

# ── Run ───────────────────────────────────────────────────────────────────────
st.markdown("### Step 2 — Run Deep Comparison")

both = template_file is not None and generated_file is not None
if not both:
    st.info("⬆️ Upload both files above to enable comparison.")

run = st.button("⚡  Run Full Deep Comparison", disabled=not both, type="primary")

if run and both:
    from extractor       import extract
    from deep_comparator import compare, SEVERITY_CRITICAL, SEVERITY_MAJOR, SEVERITY_MINOR

    with tempfile.TemporaryDirectory() as tmp:
        tp = os.path.join(tmp, template_file.name)
        gp = os.path.join(tmp, generated_file.name)
        with open(tp,"wb") as f: f.write(template_file.read())
        with open(gp,"wb") as f: f.write(generated_file.read())

        prog = st.progress(0, text="🔍 Extracting template metadata…")
        tmpl_data = extract(tp)
        prog.progress(30, text="🔍 Extracting generated metadata…")
        gen_data  = extract(gp)
        prog.progress(60, text="⚙️  Running all comparison checks…")
        report    = compare(tmpl_data, gen_data)
        prog.progress(100, text="✅ Done!")
        prog.empty()

    for e in tmpl_data.errors + gen_data.errors:
        st.warning(f"⚠️ {e}")

    st.markdown("### Step 3 — Results")

    if report.overall_result == "PASS":
        st.markdown('<div class="result-pass">✅ &nbsp; Overall Result: PASS — Documents Match</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="result-fail">❌ &nbsp; Overall Result: FAIL — Differences Detected</div>', unsafe_allow_html=True)

    # ── Score cards ───────────────────────────────────────────────────────────
    sc = report.count_by_severity()

    def mcard(col, lbl, val, cls, sub=""):
        col.markdown(f"""
        <div class="mcard {cls}">
          <div class="mlbl">{lbl}</div>
          <div class="mval">{val}</div>
          {f'<div class="msub">{sub}</div>' if sub else ''}
        </div>""", unsafe_allow_html=True)

    m = st.columns(7, gap="small")
    mcard(m[0],"Overall Score",   f"{report.overall_score}%",
          "mok" if report.overall_score>=95 else "mwarn" if report.overall_score>=75 else "mfail","100=perfect")
    mcard(m[1],"Text Similarity", f"{report.text_similarity:.2f}%",
          "mok" if report.text_similarity>=99 else "mwarn")
    mcard(m[2],"Visual Sim.",     f"{report.visual_similarity:.2f}%",
          "mok" if report.visual_similarity>=98 else "mwarn")
    mcard(m[3],"🔴 Critical",     str(sc[SEVERITY_CRITICAL]),
          "mfail" if sc[SEVERITY_CRITICAL]>0 else "mok","content/text")
    mcard(m[4],"🟠 Major",        str(sc[SEVERITY_MAJOR]),
          "mwarn" if sc[SEVERITY_MAJOR]>0 else "mok","font/position")
    mcard(m[5],"🔵 Minor",        str(sc[SEVERITY_MINOR]),
          "mwarn" if sc[SEVERITY_MINOR]>0 else "mok","spacing/style")
    mcard(m[6],"Total Issues",    str(len(report.issues)), "mcard")

    st.markdown("")
    st.markdown("#### Section Accuracy")
    sc2 = st.columns(3, gap="small")
    for zcol,(zone,score) in zip(sc2, report.section_scores.items()):
        cls  = "mok" if score>=95 else "mwarn" if score>=75 else "mfail"
        icon = "✅" if score>=95 else "⚠️" if score>=75 else "❌"
        mcard(zcol, f"{zone.upper()} ZONE", f"{icon} {score}%", cls)

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1,tab2,tab3,tab4,tab5 = st.tabs([
        "🚨 All Issues","✅ Check Summary","🖼️ Visual Diff","📊 Metadata","🤖 AI Analysis"
    ])

    # TAB 1 — All Issues
    with tab1:
        if not report.issues:
            st.success("✅ No issues — documents are identical across all checks.")
        else:
            st.markdown(f"**{len(report.issues)} issue(s)** — grouped by category")
            st.markdown("")
            by_cat = report.issues_by_category()
            order  = ["Header","Footer","Body","Content","Font","Color","Position",
                      "Alignment","Spacing","Image","Table","Watermark","FormField",
                      "Border","Layout","Page"]
            for cat in order + [c for c in by_cat if c not in order]:
                cat_issues = by_cat.get(cat,[])
                if not cat_issues: continue
                auto = cat in ("Header","Footer","Content","Body","Image","Watermark","FormField")
                with st.expander(f"  {cat}   —   {len(cat_issues)} issue(s)", expanded=auto):
                    for iss in cat_issues:
                        sc_cls = {"CRITICAL":"i-crit","MAJOR":"i-major","MINOR":"i-minor"}.get(iss.severity,"i-minor")
                        sc_col = {"CRITICAL":"#dc2626","MAJOR":"#f97316","MINOR":"#0ea5e9"}.get(iss.severity,"#64748b")
                        st.markdown(f"""
                        <div class="issue-row {sc_cls}">
                          <div class="i-sev" style="color:{sc_col}">{iss.severity} — {iss.check}</div>
                          <div class="i-loc">Page {iss.page} · Line {iss.line} · Col {iss.col} · Zone: {iss.zone.upper()}</div>
                          <div class="i-vals">
                            <b>Template &nbsp;:</b> {iss.template_val}<br>
                            <b>Generated:</b> {iss.generated_val}<br>
                            <b>Detail &nbsp;&nbsp;:</b> {iss.detail}
                          </div>
                        </div>""", unsafe_allow_html=True)

    # TAB 2 — Check Summary
    with tab2:
        st.markdown("#### All Checks — Pass / Fail")
        all_chks = [
            ("Page Count",          report.pages_tmpl==report.pages_gen,          f"{report.pages_tmpl}pg", f"{report.pages_gen}pg"),
            ("Text Similarity",     report.text_similarity>=99.9,                 f"{report.text_similarity:.4f}%","100% expected"),
            ("Visual Similarity",   report.visual_similarity>=98,                 f"{report.visual_similarity:.4f}%","98% expected"),
            ("Header Accuracy",     report.section_scores.get("header",0)>=95,    f"{report.section_scores.get('header',0)}%","95% pass"),
            ("Footer Accuracy",     report.section_scores.get("footer",0)>=95,    f"{report.section_scores.get('footer',0)}%","95% pass"),
            ("Body Accuracy",       report.section_scores.get("body",0)>=95,      f"{report.section_scores.get('body',0)}%","95% pass"),
            ("Critical Issues",     sc[SEVERITY_CRITICAL]==0,                     str(sc[SEVERITY_CRITICAL]),"0 required"),
            ("Major Issues",        sc[SEVERITY_MAJOR]==0,                        str(sc[SEVERITY_MAJOR]),"0 required"),
            ("Minor Issues",        sc[SEVERITY_MINOR]==0,                        str(sc[SEVERITY_MINOR]),"0 required"),
            ("Font Issues",         not any(i.check in ("Font Name","Font Size") for i in report.issues),"None","None"),
            ("Color Issues",        not any(i.check=="Font Color" for i in report.issues),"None","None"),
            ("Position Issues",     not any("Position" in i.check for i in report.issues),"None","None"),
            ("Alignment Issues",    not any(i.check=="Text Alignment" for i in report.issues),"None","None"),
            ("Line Spacing Issues", not any(i.check=="Line Spacing" for i in report.issues),"None","None"),
            ("Para Spacing Issues", not any("Paragraph Space" in i.check for i in report.issues),"None","None"),
            ("Letter Spacing",      not any(i.check=="Letter Spacing" for i in report.issues),"None","None"),
            ("Highlight Color",     not any(i.check=="Highlight Color" for i in report.issues),"None","None"),
            ("Image Issues",        not any(i.category=="Image" for i in report.issues),"None","None"),
            ("Table Issues",        not any(i.category=="Table" for i in report.issues),"None","None"),
            ("Watermark Issues",    not any(i.category=="Watermark" for i in report.issues),"None","None"),
            ("Form Field Issues",   not any(i.category=="FormField" for i in report.issues),"None","None"),
            ("Border Issues",       not any(i.category=="Border" for i in report.issues),"None","None"),
        ]
        for name, passed, tv, gv in all_chks:
            st.markdown(f"""
            <div class="chk-row">
              <span style="font-size:18px;width:24px;flex-shrink:0">{"✅" if passed else "❌"}</span>
              <span class="chk-name">{name}</span>
              <span class="chk-vals">Template: {tv} &nbsp;→&nbsp; Generated: {gv}</span>
            </div>""", unsafe_allow_html=True)

    # TAB 3 — Visual Diff
    with tab3:
        st.markdown("#### Page-by-Page Visual Comparison")
        diff_imgs = report.diff_images
        if diff_imgs:
            total = len(diff_imgs)
            cmp   = sum(1 for p in diff_imgs if p.get("status")=="compared")
            miss  = sum(1 for p in diff_imgs if p.get("status")=="missing")
            extra = sum(1 for p in diff_imgs if p.get("status")=="extra")
            parts = [f"**Total: {total}**",f"✅ Compared: {cmp}"]
            if miss:  parts.append(f"⚠️ Missing: {miss}")
            if extra: parts.append(f"ℹ️ Extra: {extra}")
            st.markdown(" &nbsp;|&nbsp; ".join(parts))
            st.markdown("")
            for pg in diff_imgs:
                st.markdown(f"**Page {pg['page']}** — Similarity: `{pg['page_score']:.4f}%` | Diff regions: `{pg['region_count']}`")
                if pg.get("note"): st.warning(pg["note"])
                c1,c2,c3 = st.columns(3)
                with c1:
                    st.markdown('<div class="img-lbl">Template</div>', unsafe_allow_html=True)
                    st.image(pg["template_img"], use_container_width=True)
                with c2:
                    st.markdown('<div class="img-lbl">Generated</div>', unsafe_allow_html=True)
                    st.image(pg["generated_img"], use_container_width=True)
                with c3:
                    st.markdown('<div class="img-lbl">Differences (red boxes)</div>', unsafe_allow_html=True)
                    st.image(pg["diff_img"], use_container_width=True)
                st.divider()
        else:
            st.info("Visual comparison not available. Install PyMuPDF for PDF rendering.")

    # TAB 4 — Metadata
    with tab4:
        st.markdown("#### Document Metadata")
        m1,m2 = st.columns(2)
        with m1:
            st.markdown("**📋 Template**")
            st.json({
                "file": template_file.name, "type": tmpl_data.file_type,
                "pages": len(tmpl_data.pages), "words": len(tmpl_data.words),
                "drawings": len(tmpl_data.drawings), "images": len(tmpl_data.images),
                "watermarks": len(tmpl_data.watermarks), "form_fields": len(tmpl_data.form_fields),
                "table_cells": len(tmpl_data.table_cells),
                "page_sizes": [{"page":p.page,"w":p.width,"h":p.height} for p in tmpl_data.pages],
                "margins":    [{"page":p.page,"top":p.margin_top,"bot":p.margin_bot,
                                "left":p.margin_left,"right":p.margin_right} for p in tmpl_data.pages],
            })
        with m2:
            st.markdown("**📄 Generated**")
            st.json({
                "file": generated_file.name, "type": gen_data.file_type,
                "pages": len(gen_data.pages), "words": len(gen_data.words),
                "drawings": len(gen_data.drawings), "images": len(gen_data.images),
                "watermarks": len(gen_data.watermarks), "form_fields": len(gen_data.form_fields),
                "table_cells": len(gen_data.table_cells),
                "page_sizes": [{"page":p.page,"w":p.width,"h":p.height} for p in gen_data.pages],
                "margins":    [{"page":p.page,"top":p.margin_top,"bot":p.margin_bot,
                                "left":p.margin_left,"right":p.margin_right} for p in gen_data.pages],
            })

        if tmpl_data.words:
            st.markdown("**Sample word tokens — first 10 from template**")
            import pandas as pd
            rows = []
            for w in tmpl_data.words[:10]:
                rows.append({
                    "word":w.text,"page":w.page,"line":w.line,"col":w.col,
                    "zone":w.zone,"font":w.font_name,"size_pt":w.font_size,
                    "color":rgb_str(w.font_color),"bold":w.bold,"italic":w.italic,
                    "align":w.alignment,"letter_sp":w.letter_spacing,
                    "highlight":rgb_str(w.highlight_color),
                    "x0":w.bbox.x0,"y0":w.bbox.y0,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

        if tmpl_data.form_fields:
            st.markdown("**Form Fields — Template**")
            ff_rows = [{"name":f.name,"type":f.field_type,"value":f.value,
                        "page":f.page,"required":f.required,"font_size":f.font_size}
                       for f in tmpl_data.form_fields]
            st.dataframe(pd.DataFrame(ff_rows), use_container_width=True)

        if tmpl_data.watermarks:
            st.markdown("**Watermarks — Template**")
            wm_rows = [{"page":w.page,"kind":w.kind,"text":w.text,
                        "opacity":w.opacity,"color":rgb_str(w.color)}
                       for w in tmpl_data.watermarks]
            st.dataframe(pd.DataFrame(wm_rows), use_container_width=True)

    # TAB 5 — AI Analysis
    with tab5:
        st.markdown("#### AI-Powered Analysis")
        st.caption("Get a plain-English explanation of all findings with actionable fix recommendations.")
        st.markdown("")
        if st.button("🤖  Generate AI Analysis", key="ai_v3"):
            with st.spinner("Asking Claude to analyse all findings…"):
                from ai_analyzer import analyze_with_claude
                payload = {
                    "overall_result":    report.overall_result,
                    "overall_score":     report.overall_score,
                    "text_similarity":   report.text_similarity,
                    "visual_similarity": report.visual_similarity,
                    "header_score":      report.section_scores.get("header",0),
                    "footer_score":      report.section_scores.get("footer",0),
                    "body_score":        report.section_scores.get("body",0),
                    "critical_issues":   sc[SEVERITY_CRITICAL],
                    "major_issues":      sc[SEVERITY_MAJOR],
                    "minor_issues":      sc[SEVERITY_MINOR],
                    "content_issues":    sc[SEVERITY_CRITICAL],
                    "layout_issues":     sum(1 for i in report.issues if i.category in ("Layout","Border","Position","Alignment","Spacing")),
                    "font_diff":         "Detected" if any(i.check in ("Font Name","Font Size","Bold","Italic") for i in report.issues) else "Not detected",
                    "header_match":      "Match" if report.section_scores.get("header",0)>=95 else "Mismatch",
                    "footer_match":      "Match" if report.section_scores.get("footer",0)>=95 else "Mismatch",
                    "text_diffs":        [{"type":i.severity.lower(),"text":f"{i.check}: {i.detail}"} for i in report.issues[:15]],
                    "similarity_score":  report.overall_score,
                }
                ai_text = analyze_with_claude(payload)
            st.markdown(f"""
            <div class="ai-box">
              <div class="ai-head">🤖 &nbsp; Claude Analysis &amp; Recommendations</div>
              <div class="ai-body">{ai_text}</div>
            </div>""", unsafe_allow_html=True)

    # ── Downloads ─────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📥 Download Reports")
    rep = build_report(report, template_file.name, generated_file.name)
    d1, d2, _ = st.columns([1,1,2])
    with d1:
        st.download_button("⬇ HTML Report", data=rep["html"],
            file_name="comparison_report.html", mime="text/html",
            use_container_width=True)
    with d2:
        st.download_button("⬇ JSON Report", data=rep["json"],
            file_name="comparison_report.json", mime="application/json",
            use_container_width=True)
