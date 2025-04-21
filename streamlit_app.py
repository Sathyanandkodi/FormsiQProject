import os
import re
import json
import pandas as pd
import streamlit as st
from openai import OpenAI
from typing import List, Dict

# — Streamlit page config —
st.set_page_config(
    page_title="FormsiQ Field Extractor",
    layout="centered",
    initial_sidebar_state="expanded"
)

# — OpenAI Setup — 
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", "")))

def extract_fields_dummy(transcript: str) -> Dict[str, List[Dict]]:
    """
    Enhanced dummy extractor for key 1003 fields.
    """
    fields: List[Dict] = []

    # 1) Borrower Name
    m = re.search(r"Borrower\s*:\s*(.+)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Borrower Name",
            "field_value": m.group(1).strip(),
            "confidence_score": 0.50
        })

    # 2) Property Address
    m = re.search(r"home at\s*(.+?)\.", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Property Address",
            "field_value": m.group(1).strip(),
            "confidence_score": 0.50
        })

    # 3) Loan Amount
    m = re.search(r"loan for\s*\$?([\d,]+)", transcript, re.IGNORECASE) \
        or re.search(r"purchase price is\s*\$?([\d,]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Loan Amount",
            "field_value": f"${m.group(1).strip()}",
            "confidence_score": 0.50
        })

    # 4) Loan Term
    m = re.search(r"(\d+)-year fixed rate", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Loan Term",
            "field_value": f"{m.group(1)}-year",
            "confidence_score": 0.50
        })

    # 5) Interest Rate
    m = re.search(r"rate is\s*([\d.]+%)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Interest Rate",
            "field_value": m.group(1),
            "confidence_score": 0.75
        })

    # 6) SSN
    m = re.search(r"SSN is\s*([\d-]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "SSN",
            "field_value": m.group(1),
            "confidence_score": 0.90
        })

    # 7) Date of Birth
    m = re.search(r"DOB is\s*([\d/]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Date of Birth",
            "field_value": m.group(1),
            "confidence_score": 0.95
        })

    # 8) Gross Monthly Income
    m = re.search(r"gross monthly income.*?([\$\d,]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Gross Monthly Income",
            "field_value": m.group(1),
            "confidence_score": 0.75
        })

    return {"fields": fields}


def extract_fields_via_openai(transcript: str) -> Dict:
    """
    AI extractor: calls OpenAI to get full 1003 field extraction.
    """
    system_prompt = (
        "You are a data extraction assistant. "
        "Extract all fields from the 1003 mortgage application form "
        "(Borrower Name, Loan Amount, Property Address, Loan Term, Interest Rate, "
        "SSN, Date of Birth, Gross Monthly Income, etc.) from the call transcript. "
        "For each field, output an object with 'field_name', 'field_value', and "
        "'confidence_score' (0–1). Respond ONLY with JSON: { \"fields\": [ ... ] }."
    )
    user_prompt = f"Transcript:\n\"\"\"\n{transcript}\n\"\"\""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=700,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}


# — Session state init —
if "transcript_input" not in st.session_state:
    st.session_state.transcript_input = ""
if "example_choice" not in st.session_state:
    st.session_state.example_choice = ""


# — Sidebar: configuration & mock transcripts — 
st.sidebar.header("Configuration")
use_ai = st.sidebar.radio(
    "Extractor to use:",
    ("Dummy extractor", "AI extractor")
)

st.sidebar.markdown("---")
st.sidebar.header("🚀 Mock Transcripts")
examples = {
    "Full Example": """Agent: Good morning, thank you for calling MortgageCo. Can I have your full name please?
Borrower: William Martinez
Agent: What property are you looking to finance?
Borrower: It's a home at 321 Cedar Blvd, Boston, MA.
Agent: And what's the purchase price or loan amount you need?
Borrower: The purchase price is $790,000, and I'd like a loan for $740,000.
Agent: What term are you considering?
Borrower: I prefer a 15-year fixed rate.
Agent: Our current rate is 4.96%.
Borrower: Sounds good.
Agent: Can you confirm your SSN and date of birth?
Borrower: My SSN is 905-95-2209 and my DOB is 8/25/1967.
Agent: Finally, your gross monthly income?
Borrower: $6000.
Agent: Thank you, I'll send next steps via email.""",

    "Missing income": """Agent: Hi, full name?
Borrower: Emily Davis
Agent: Purchase price?
Borrower: $500,000
Agent: Loan amount?
Borrower: $450,000
Agent: Term?
Borrower: 30-year fixed rate.
Agent: Rate?
Borrower: 3.85%.
Agent: SSN and DOB?
Borrower: 321-54-9876, DOB is 7/14/1990.""",
}
st.sidebar.selectbox(
    "Choose an example",
    [""] + list(examples.keys()),
    key="example_choice"
)
if st.sidebar.button("Load example"):
    choice = st.session_state.example_choice
    if choice in examples:
        st.session_state.transcript_input = examples[choice]


# — Main UI — 
st.title("📝 FormsiQ 1003‑Form Field Extractor")
st.markdown(
    "Paste or load a transcript and click Extract Fields."
)

# CSS reminder banner
st.markdown("""
<div style="padding:10px; background-color:#f9f9f9; border-left:4px solid #2C7BE5; margin-bottom:15px;">
<strong>Input:</strong> Paste a single transcript in the text box <em>or</em> upload a CSV file 
(with a column named <code>transcript</code>) to process multiple records.
</div>
""", unsafe_allow_html=True)

# CSV upload
uploaded_file = st.file_uploader("Upload CSV file here", type=["csv"])
transcripts: List[str] = []

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        if "transcript" in df.columns:
            transcripts = df["transcript"].dropna().astype(str).tolist()
        else:
            st.error("CSV must contain a 'transcript' column.")
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
else:
    # fallback to single transcript textarea
    transcripts = []
    transcript = st.text_area(
        "Call Transcript text box",
        value=st.session_state.transcript_input,
        height=250,
        key="transcript_input",
        placeholder="Paste your call transcript here…"
    )
    if transcript.strip():
        transcripts = [transcript.strip()]

if st.button("Extract Fields"):
    if not transcripts:
        st.error("Please provide at least one transcript (via paste or CSV).")
    else:
        for idx, tx in enumerate(transcripts, start=1):
            st.markdown(f"---\n**Transcript #{idx}:**")
            st.text_area(f"Preview #{idx}", tx, height=120, disabled=True, key=f"tx_{idx}")
            with st.spinner(f"Processing transcript #{idx}…"):
                if use_ai == "AI extractor":
                    result = extract_fields_via_openai(tx)
                    # fallback on quota/429
                    if "error" in result and any(code in result["error"].lower() for code in ("quota", "429")):
                        st.warning(
                            "🚫 OpenAI quota exceeded. Falling back to Dummy extractor."
                        )
                        result = extract_fields_dummy(tx)
                else:
                    result = extract_fields_dummy(tx)

            if "error" in result:
                st.error(f"Error: {result['error']}")
            else:
                st.subheader("JSON Output")
                st.json(result)


# — Simple CSS styling — 
st.markdown("""
<style>
    .stTextArea textarea { font-family: monospace; }
    .stButton>button { background-color: #2C7BE5; color: white; }
</style>
""", unsafe_allow_html=True)
