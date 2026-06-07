import streamlit as st
import pdfplumber
import json
import re
import time
import os
from google import genai
from google.genai import types

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FactGuard AI · Claim Verification",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
}

.stApp {
    background: #060D1A;
}

/* Hide default streamlit elements */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

.hero-title {
    font-size: 3rem;
    font-weight: 700;
    background: linear-gradient(135deg, #00C9A7, #1E90FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}
.hero-sub {
    color: #8A9BB0;
    font-size: 1.1rem;
    margin-bottom: 2rem;
}
.claim-card {
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin: 0.75rem 0;
    border-left: 4px solid;
    font-size: 0.95rem;
}
.claim-verified {
    background: rgba(46, 204, 113, 0.08);
    border-color: #2ECC71;
    color: #D4F5E2;
}
.claim-inaccurate {
    background: rgba(245, 166, 35, 0.08);
    border-color: #F5A623;
    color: #FFF0CC;
}
.claim-false {
    background: rgba(231, 76, 60, 0.08);
    border-color: #E74C3C;
    color: #FFD5D0;
}
.claim-unverifiable {
    background: rgba(138, 155, 176, 0.08);
    border-color: #8A9BB0;
    color: #C5CDD8;
}
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-bottom: 0.4rem;
}
.badge-verified   { background: #2ECC71; color: #06200F; }
.badge-inaccurate { background: #F5A623; color: #2A1A00; }
.badge-false      { background: #E74C3C; color: #2D0000; }
.badge-unverifiable { background: #8A9BB0; color: #0A1628; }

.stat-box {
    background: #0D1E30;
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
    border: 1px solid #1A3A5C;
}
.stat-num {
    font-size: 2.2rem;
    font-weight: 700;
    line-height: 1;
}
.stat-lbl {
    font-size: 0.8rem;
    color: #8A9BB0;
    margin-top: 0.2rem;
}

.claim-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88rem;
    color: inherit;
    background: rgba(255,255,255,0.04);
    padding: 0.5rem 0.7rem;
    border-radius: 6px;
    margin: 0.4rem 0;
}
.verdict-text {
    font-size: 0.9rem;
    margin-top: 0.5rem;
}
.source-chip {
    display: inline-block;
    background: rgba(30, 144, 255, 0.15);
    border: 1px solid rgba(30, 144, 255, 0.3);
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    color: #7EB8FF;
    margin: 2px 3px;
}
</style>
""", unsafe_allow_html=True)

# ─── Anthropic Client ─────────────────────────────────────────────────────────
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

# ─── Helper: Extract Text from PDF ──────────────────────────────────────────
def extract_pdf_text(uploaded_file) -> str:
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    return text.strip()

# ─── Helper: Extract Claims via Claude ──────────────────────────────────────
def extract_claims(text: str) -> list[dict]:
    prompt = f"""You are a fact-checking expert. Extract ALL verifiable factual claims from the following text.

Focus on: statistics, percentages, dates, monetary figures, technical specs, rankings, named research findings, product claims.

Return ONLY a JSON array. Each object must have:
- "claim": the exact claim as a string
- "context": 1-sentence context of where it appears

Example:
[
  {{"claim": "Global smartphone users reached 6.8 billion in 2023", "context": "Used to support mobile-first strategy argument"}},
  {{"claim": "GPT-4 has 1.76 trillion parameters", "context": "Cited as evidence of LLM scale"}}
]

Text to analyze:
{text[:6000]}

Return ONLY the JSON array, no markdown, no explanation."""

    response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
    )

    raw = response.text.strip() 
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ─── Helper: Verify Single Claim via Claude + Web Search ─────────────────────
def verify_claim(claim: str, context: str) -> dict:
    prompt = f"""You are a rigorous fact-checker with access to web search. Verify the following claim using current, reliable sources.

CLAIM: "{claim}"
CONTEXT: {context}

Steps:
1. Search your knowledge + web data to assess accuracy
2. Find the most current authoritative data on this topic
3. Compare claim vs actual data

Return ONLY a JSON object with these exact fields:
{{
  "status": "Verified" | "Inaccurate" | "False" | "Unverifiable",
  "verdict": "1-2 sentence explanation of finding",
  "real_fact": "The correct, current data (if claim is wrong or outdated). Empty string if verified.",
  "confidence": "High" | "Medium" | "Low",
  "sources": ["source name 1", "source name 2"]
}}

Status definitions:
- Verified: Claim matches current data
- Inaccurate: Claim is outdated or partially wrong (real numbers differ)
- False: Claim is factually wrong with no basis
- Unverifiable: Cannot confirm or deny with available data

Return ONLY the JSON object."""

response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )

    result_text = response.text.strip()
    result_text = re.sub(r"^```json\s*", "", result_text)
    result_text = re.sub(r"\s*```$", "", result_text)
    
    # Extract text from response (may include tool_use blocks)
    result_text = ""
    for block in response.content:
        if block.type == "text":
            result_text += block.text

    # If model used tools but didn't give final text, do a follow-up
    if not result_text.strip():
        # Build follow-up with tool results
        messages = [{"role": "user", "content": prompt}]
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Search completed."
                })
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            follow_up = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                messages=messages
            )
            for block in follow_up.content:
                if hasattr(block, "text"):
                    result_text += block.text

    result_text = result_text.strip()
    result_text = re.sub(r"^```json\s*", "", result_text)
    result_text = re.sub(r"\s*```$", "", result_text)

    try:
        return json.loads(result_text)
    except Exception:
        # Fallback
        return {
            "status": "Unverifiable",
            "verdict": "Could not parse verification result.",
            "real_fact": "",
            "confidence": "Low",
            "sources": []
        }


# ─── UI: Header ──────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 2rem 0 1rem 0;">
  <div class="hero-title">🛡️ FactGuard AI</div>
  <div class="hero-sub">Upload a PDF · Extract claims · Cross-reference live web data · Flag inaccuracies instantly</div>
</div>
""", unsafe_allow_html=True)

# ─── Upload Zone ─────────────────────────────────────────────────────────────
col_upload, col_info = st.columns([2, 1])

with col_upload:
    uploaded_file = st.file_uploader(
        "Drop your PDF here",
        type=["pdf"],
        help="Marketing decks, research reports, press releases — any PDF with factual claims"
    )

with col_info:
    st.markdown("""
    <div style="background:#0D1E30; border-radius:12px; padding:1.2rem; border:1px solid #1A3A5C; margin-top:0.5rem;">
      <div style="color:#00C9A7; font-weight:700; margin-bottom:0.5rem;">How It Works</div>
      <div style="color:#8A9BB0; font-size:0.88rem; line-height:1.6;">
        <b style="color:#D6EAF8;">1. Extract</b> — Claude identifies all stats, dates & figures<br>
        <b style="color:#D6EAF8;">2. Search</b> — Live web search cross-references each claim<br>
        <b style="color:#D6EAF8;">3. Flag</b> — Every claim gets Verified / Inaccurate / False
      </div>
    </div>
    """, unsafe_allow_html=True)

# ─── Main Logic ───────────────────────────────────────────────────────────────
if uploaded_file:
    st.divider()

    with st.spinner("📄 Extracting text from PDF..."):
        pdf_text = extract_pdf_text(uploaded_file)

    if not pdf_text:
        st.error("Could not extract text from this PDF. Please try a text-based (non-scanned) PDF.")
        st.stop()

    with st.expander("📋 View extracted PDF text", expanded=False):
        st.text_area("", pdf_text[:3000] + ("..." if len(pdf_text) > 3000 else ""), height=200)

    with st.spinner("🔍 Identifying verifiable claims..."):
        try:
            claims = extract_claims(pdf_text)
        except Exception as e:
            st.error(f"Claim extraction failed: {e}")
            st.stop()

    if not claims:
        st.warning("No verifiable factual claims found in this document.")
        st.stop()

    st.success(f"Found **{len(claims)} verifiable claims**. Starting live verification...")

    # Progress
    progress_bar = st.progress(0)
    status_text = st.empty()

    results = []
    for i, claim_obj in enumerate(claims):
        claim = claim_obj.get("claim", "")
        context = claim_obj.get("context", "")
        status_text.markdown(f"<span style='color:#8A9BB0'>Verifying claim {i+1}/{len(claims)}: *{claim[:80]}...*</span>", unsafe_allow_html=True)
        result = verify_claim(claim, context)
        result["claim"] = claim
        result["context"] = context
        results.append(result)
        progress_bar.progress((i + 1) / len(claims))
        time.sleep(0.3)

    status_text.empty()
    progress_bar.empty()

    # ─── Summary Stats ────────────────────────────────────────────────────────
    st.markdown("### 📊 Verification Summary")

    counts = {
        "Verified": sum(1 for r in results if r["status"] == "Verified"),
        "Inaccurate": sum(1 for r in results if r["status"] == "Inaccurate"),
        "False": sum(1 for r in results if r["status"] == "False"),
        "Unverifiable": sum(1 for r in results if r["status"] == "Unverifiable"),
    }
    colors = {"Verified": "#2ECC71", "Inaccurate": "#F5A623", "False": "#E74C3C", "Unverifiable": "#8A9BB0"}

    cols = st.columns(4)
    for col, (label, count) in zip(cols, counts.items()):
        col.markdown(f"""
        <div class="stat-box">
          <div class="stat-num" style="color:{colors[label]}">{count}</div>
          <div class="stat-lbl">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    # Accuracy score
    total = len(results)
    truth_score = round((counts["Verified"] / total) * 100) if total else 0
    st.markdown(f"""
    <div style="background:#0D1E30; border-radius:10px; padding:1rem 1.5rem; margin:1rem 0; border:1px solid #1A3A5C; display:flex; align-items:center; gap:1rem;">
      <div style="font-size:2rem; font-weight:700; color:{'#2ECC71' if truth_score >= 70 else '#F5A623' if truth_score >= 40 else '#E74C3C'}">{truth_score}%</div>
      <div>
        <div style="color:#D6EAF8; font-weight:600;">Document Truth Score</div>
        <div style="color:#8A9BB0; font-size:0.85rem;">{counts['Inaccurate'] + counts['False']} claim(s) flagged as inaccurate or false out of {total} analyzed</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ─── Detailed Results ─────────────────────────────────────────────────────
    st.markdown("### 🔎 Claim-by-Claim Results")

    # Filter
    filter_col, _ = st.columns([1, 2])
    with filter_col:
        filter_status = st.selectbox("Filter by status", ["All", "Verified", "Inaccurate", "False", "Unverifiable"])

    filtered = results if filter_status == "All" else [r for r in results if r["status"] == filter_status]

    for r in filtered:
        status = r.get("status", "Unverifiable")
        css_class = f"claim-{status.lower()}"
        badge_class = f"badge-{status.lower()}"

        sources_html = " ".join(f'<span class="source-chip">{s}</span>' for s in r.get("sources", []))
        real_fact_html = f'<div style="margin-top:0.6rem; color:#FFD580;"><b>✦ Correct data:</b> {r["real_fact"]}</div>' if r.get("real_fact") else ""
        confidence = r.get("confidence", "")
        conf_color = "#2ECC71" if confidence == "High" else "#F5A623" if confidence == "Medium" else "#E74C3C"

        st.markdown(f"""
        <div class="claim-card {css_class}">
          <span class="badge {badge_class}">{status.upper()}</span>
          <span style="font-size:0.75rem; color:{conf_color}; margin-left:8px;">● {confidence} confidence</span>
          <div class="claim-text">"{r['claim']}"</div>
          <div class="verdict-text"><b>Verdict:</b> {r.get('verdict', '')}</div>
          {real_fact_html}
          <div style="margin-top:0.6rem;">{sources_html}</div>
        </div>
        """, unsafe_allow_html=True)

    # ─── Download JSON Report ─────────────────────────────────────────────────
    st.divider()
    report = {
        "file": uploaded_file.name,
        "total_claims": total,
        "summary": counts,
        "truth_score_pct": truth_score,
        "results": results
    }
    st.download_button(
        "⬇️  Download Full JSON Report",
        data=json.dumps(report, indent=2),
        file_name="factguard_report.json",
        mime="application/json"
    )

else:
    # Empty state
    st.markdown("""
    <div style="text-align:center; padding:3rem; color:#8A9BB0;">
      <div style="font-size:4rem; margin-bottom:1rem;">📄</div>
      <div style="font-size:1.1rem;">Upload a PDF to begin fact-checking</div>
      <div style="font-size:0.85rem; margin-top:0.5rem;">Supports: marketing decks, research reports, press releases, white papers</div>
    </div>
    """, unsafe_allow_html=True)
