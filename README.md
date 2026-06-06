# 🛡️ FactGuard AI — Automated PDF Fact-Checker

> Upload any PDF. Extract claims. Cross-reference live web data. Flag inaccuracies instantly.

## Live Demo
🔗 **[https://factguard-ai.streamlit.app](https://factguard-ai.streamlit.app)**  
*(Deploy to Streamlit Cloud — instructions below)*

---

## What It Does

FactGuard AI is an agentic fact-checking system that:

1. **Extracts** — Claude identifies all verifiable claims (stats, dates, financial figures, technical specs) from an uploaded PDF
2. **Verifies** — Each claim is cross-referenced using live web search via Claude's `web_search` tool
3. **Reports** — Every claim is flagged as:
   - ✅ **Verified** — Matches current authoritative data
   - ⚠️ **Inaccurate** — Outdated or partially wrong (shows correct data)
   - ❌ **False** — Factually incorrect with no basis
   - 🔘 **Unverifiable** — Cannot confirm with available sources

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit |
| LLM + Fact-check | Anthropic Claude Sonnet 4 |
| Live Web Search | Claude `web_search_20250305` tool |
| PDF Parsing | `pdfplumber` |
| Deployment | Streamlit Cloud |

---

## Local Setup

```bash
git clone https://github.com/yourusername/factguard-ai
cd factguard-ai
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

streamlit run app.py
```

---

## Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo → select `app.py`
4. Under **Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   ```
5. Deploy! Your app will be live at `https://your-app-name.streamlit.app`

> **Note**: Update `app.py` line `client = Anthropic()` to `client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])` for Streamlit Cloud deployment.

---

## Architecture

```
PDF Upload → pdfplumber text extraction
         → Claude: claim extraction (JSON)
         → For each claim:
             → Claude + web_search_20250305 tool
             → Verdict: Verified / Inaccurate / False / Unverifiable
         → Dashboard: summary stats + per-claim cards
         → Download: JSON report
```

---

## Evaluation: "Trap Document" Test

The system is specifically designed to catch:
- **Outdated statistics** (e.g., "X had Y users in 2020" when current is higher)
- **Hallucinated figures** (e.g., made-up research citations)
- **False product claims** (e.g., incorrect specs or pricing)
- **Fabricated dates** (e.g., wrong product launch years)

Each claim includes a **"Correct Data"** field showing the real fact when something is flagged.

---

## Files

```
factcheck_app/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md           # This file
```
