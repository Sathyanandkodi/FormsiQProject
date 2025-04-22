python
import os
import re
import json
import pandas as pd
import streamlit as st
from openai import OpenAI
from typing import List, Dict, Optional, Tuple

# — Streamlit page config —
st.set_page_config(
    page_title="FormsiQ Field Extractor",
    layout="centered",
    initial_sidebar_state="expanded"
)

# — OpenAI Setup —
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", "")))
st.write(f"🔑 Using OpenAI model: gpt‑4o‑mini")

# — Required 1003 fields list —
REQUIRED_FIELDS = [
    "Borrower Name", "Property Address", "Loan Amount", "Loan Term",
    "Interest Rate", "SSN", "Date of Birth", "Income"
]

# — Transcript validation (negative cases) —
def validate_transcript(transcript: str) -> Tuple[bool, str]:
    txt = transcript.strip()
    if not txt or len(txt) < 30:
        return False, "Transcript too short or empty"
    keywords = ["loan", "borrower", "ssn", "dob", "$", "income"]
    if not any(k in txt.lower() for k in keywords):
        return False, "No mortgage-related data found"
    return True, ""

# — Normalize to include missing fields with zero confidence —
def normalize_fields(fields: List[Dict]) -> List[Dict]:
    present = {f['field_name'] for f in fields}
    for field in REQUIRED_FIELDS:
        if field not in present:
            fields.append({
                'field_name': field,
                'field_value': None,
                'confidence_score': 0.0
            })
    return fields

# — Dummy extractor —
def extract_fields_dummy(transcript: str) -> Dict[str, List[Dict]]:
    fields: List[Dict] = []
    # Borrower Name
    m = re.search(r"Borrower\s*:\s*(.+)", transcript, re.IGNORECASE)
    if m:
        name = m.group(1).strip().rstrip('.')
        fields.append({'field_name': 'Borrower Name', 'field_value': name, 'confidence_score': 0.5})
    # Property Address
    m = re.search(r"(?:home at|it['’]?s)\s*(.+?)\.", transcript, re.IGNORECASE)
    if m:
        addr = m.group(1).strip()
        fields.append({'field_name': 'Property Address', 'field_value': addr, 'confidence_score': 0.5})
    # Loan Amount
    m = (re.search(r"loan for\s*\$?([\d,]+)", transcript, re.IGNORECASE)
         or re.search(r"purchase price is\s*\$?([\d,]+)", transcript, re.IGNORECASE)
         or re.search(r"outstanding balance.*?\$?([\d,]+)", transcript, re.IGNORECASE))
    if m:
        amount = f"${m.group(1).strip()}"
        fields.append({'field_name': 'Loan Amount', 'field_value': amount, 'confidence_score': 0.5})
    # Loan Term
    m = re.search(r"(\d+)-year fixed rate", transcript, re.IGNORECASE)
    if m:
        term = f"{m.group(1)}-year"
        fields.append({'field_name': 'Loan Term', 'field_value': term, 'confidence_score': 0.5})
    # Interest Rate
    m = re.search(r"rate is\s*([\d.]+%)", transcript, re.IGNORECASE)
    if m:
        fields.append({'field_name': 'Interest Rate', 'field_value': m.group(1), 'confidence_score': 0.75})
    # SSN
    m = re.search(r"SSN\s*(?:is)?\s*([\d-]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({'field_name': 'SSN', 'field_value': m.group(1), 'confidence_score': 0.9})
    # Date of Birth
    m = re.search(r"DOB\s*(?:is)?\s*([\d/]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({'field_name': 'Date of Birth', 'field_value': m.group(1), 'confidence_score': 0.95})
    # Income
    m = re.search(r"(?:annual|gross monthly) income.*?\$?([\d,]+)", transcript, re.IGNORECASE)
    if m:
        inc = f"${m.group(1).strip()}"
        fields.append({'field_name': 'Income', 'field_value': inc, 'confidence_score': 0.75})
    # Ensure all fields present
    normalize_fields(fields)
    return {'fields': fields}

# — AI extractor —
def extract_fields_via_openai(transcript: str) -> Dict:
    system_prompt = (
        "You are a data extraction assistant. Extract all 1003 mortgage form fields "
        "(Borrower Name, Property Address, Loan Amount, Loan Term, Interest Rate, "
        "SSN, Date of Birth, Income) from the transcript. "
        "If a field is missing, include it with null value and confidence_score 0.0. "
        "Be robust to varied phrasing and edge-case addresses. Respond only with JSON."
    )
    user_prompt = f"Transcript:\n\"\"\"\n{transcript}\n\"\"\""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            temperature=0.0,
            max_tokens=700
        )
        result = json.loads(resp.choices[0].message.content)
        result['fields'] = normalize_fields(result.get('fields', []))
        return result
    except Exception as e:
        return {'error': str(e)}

# — Session state init —
if "transcript_input" not in st.session_state:
    st.session_state.transcript_input = ""
if "example_choice" not in st.session_state:
    st.session_state.example_choice = ""

# — Sidebar —
st.sidebar.header("Configuration")
use_ai = st.sidebar.radio("Extractor to use:", ("Dummy extractor", "AI extractor"))
st.sidebar.markdown("---")
st.sidebar.header("🚀 Mock Transcripts")
examples = {
    "Full Example": "...",
    "Missing Income": "...",
    "Alternate Phrasing": "...",
    "Unusual Address": "...",
    "Invalid Data": "Hello world",
}
st.sidebar.selectbox("Choose an example", [""] + list(examples.keys()), key="example_choice")
if st.sidebar.button("Load example"):
    choice = st.session_state.example_choice
    st.session_state.transcript_input = examples.get(choice, "")

# — Main UI —
st.title("📝 FormsiQ 1003‑Form Field Extractor Model")
st.markdown("Paste or upload transcripts, then click **Extract Fields**.")

# Input banner
st.markdown(
    "<div style='padding:10px; background:#f9f9f9; border-left:4px solid #2C7BE5;'>"
    "<strong>Input:</strong> Paste a transcript or upload a CSV with a transcript column.</div>",
    unsafe_allow_html=True
)

# CSV upload or text area
uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])
transcripts: List[str] = []
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        if 'transcript' in df:
            transcripts = df['transcript'].dropna().astype(str).tolist()
            st.success(f"Loaded {len(transcripts)} transcripts")
        else:
            st.error("CSV must contain 'transcript' column")
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
else:
    text = st.text_area("Call Transcript", height=250, key="transcript_input")
    if text.strip(): transcripts = [text.strip()]

# Extraction button
if st.button("Extract Fields"):
    if not transcripts:
        st.error("Provide at least one transcript.")
    for idx, tx in enumerate(transcripts, start=1):
        st.markdown(f"---\n**Transcript #{idx}:**")
        valid, msg = validate_transcript(tx)
        if not valid:
            st.error(f"Invalid transcript: {msg}")
            continue
        with st.spinner("Processing…"):
            if use_ai == "AI extractor":
                result = extract_fields_via_openai(tx)
                if 'error' in result and any(e in result['error'].lower() for e in ('quota','429','rate')):
                    st.error("AI service unavailable. Switch to Dummy.")
                    continue
            else:
                result = extract_fields_dummy(tx)
        if 'error' in result:
            st.error(f"Error: {result['error']}")
        else:
            st.subheader("JSON Output")
            st.json(result)

# Styling
st.markdown(
    """
      <style>
        .stTextArea textarea { font-family: monospace; }
        .stButton>button { background-color: #2C7BE5; color: white; }
      </style>
    """,
    unsafe_allow_html=True
)
