import os
import re
import json
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
    fields: List[Dict] = []
    lines = transcript.splitlines()

    # Borrower Name logic
    name = None
    for idx, line in enumerate(lines):
        if re.search(r"full name", line, re.IGNORECASE):
            for sub in lines[idx+1:]:
                m = re.match(r"Borrower\s*:\s*(.+)", sub, re.IGNORECASE)
                if m:
                    name = m.group(1).strip()
                    break
            break
    if name:
        fields.append({
            "field_name": "Borrower Name",
            "field_value": name,
            "confidence_score": 0.50
        })

    # Loan Amount logic
    m = re.search(r"loan for\s*\$?([\d,]+)", transcript, re.IGNORECASE) \
        or re.search(r"purchase price is\s*\$?([\d,]+)", transcript, re.IGNORECASE)
    if m:
        amt = m.group(1).strip()
        fields.append({
            "field_name": "Loan Amount",
            "field_value": f"${amt}",
            "confidence_score": 0.50
        })

    return {"fields": fields}

def extract_fields_via_openai(transcript: str) -> Dict:
    system_prompt = (
        "You are a data extraction assistant. "
        "Extract all fields from the 1003 mortgage application form "
        "(Borrower Name, Loan Amount, Property Address, Loan Term, Interest Rate, etc.) "
        "from the call transcript. "
        "For each field, output an object with 'field_name', 'field_value', and "
        "'confidence_score' (0–1). "
        "Respond ONLY with JSON: { \"fields\": [ ... ] }."
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
            max_tokens=600,
        )
        text = resp.choices[0].message.content
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}

# — Session state initialization —
if "transcript_input" not in st.session_state:
    st.session_state.transcript_input = ""
if "example_choice" not in st.session_state:
    st.session_state.example_choice = ""

# — Sidebar —
st.sidebar.header("Configuration")
use_ai = st.sidebar.radio(
    "Extractor to use:",
    options=["Dummy extractor", "AI extractor"]
)

st.sidebar.markdown("---")
st.sidebar.header("🚀 Mock Transcripts")
examples = {
    "Standard Positive": """Agent: Hello, I’m Sam. Can I get your full name?
Borrower: Alice Johnson
Agent: What loan amount are you seeking?
Borrower: I need a loan for $415,000""",
    "Michael Case": """Agent: Good morning! Thank you for calling Evergreen Mortgage Solutions. My name is Lisa Carter. How can I help you today?
Borrower: Michael Anthony Reynolds.
Agent: The purchase price is $325,000, and I’d like a loan for $300,000.""",
    "Missing Amount": """Agent: Hi there, please provide your full name.
Borrower: Robert King"""
}
st.sidebar.selectbox(
    "Choose an example",
    options=[""] + list(examples.keys()),
    key="example_choice"
)
if st.sidebar.button("Load into transcript"):
    choice = st.session_state.example_choice
    if choice in examples:
        st.session_state.transcript_input = examples[choice]

# — Main UI — 
st.title("📝 FormsiQ 1003‑Form Field Extractor Robot")
st.markdown(
    "Paste the transcript and click **Extract Fields**. "
    f"Using **{use_ai}**."
)

transcript = st.text_area(
    "Call Transcript",
    height=250,
    key="transcript_input",
    placeholder="Paste your call transcript here…"
)

if st.button("Extract Fields"):
    if not transcript.strip():
        st.error("Please provide a transcript.")
    else:
        with st.spinner("Extracting…"):
            result = (
                extract_fields_via_openai(transcript)
                if use_ai == "AI extractor"
                else extract_fields_dummy(transcript)
            )

        if "error" in result:
            st.error(f"Error: {result['error']}")
        else:
            # —— NEW: JSON Output Viewer —— 
            st.subheader("JSON Output")
            st.json(result)

# — CSS styling —
st.markdown("""
<style>
    .stTextArea textarea { font-family: monospace; background-color: #f9f9f9; }
    .stButton>button { background-color: #2C7BE5; color: white; }
</style>
""", unsafe_allow_html=True)
