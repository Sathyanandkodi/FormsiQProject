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

# — OpenAI setup — 
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", "")))

def extract_fields_dummy(transcript: str) -> Dict[str, List[Dict]]:
    """
    Your existing dummy extractor.
    """
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
    amt = None
    m = re.search(r"loan for\s*\$?([\d,]+)", transcript, re.IGNORECASE)
    if not m:
        m = re.search(r"purchase price is\s*\$?([\d,]+)", transcript, re.IGNORECASE)
    if m:
        amt = m.group(1).strip()
    if amt:
        fields.append({
            "field_name": "Loan Amount",
            "field_value": f"${amt}",
            "confidence_score": 0.50
        })

    return {"fields": fields}

def extract_fields_via_openai(transcript: str) -> Dict:
    """
    Calls OpenAI’s chat API via the `client` to extract 1003‑Form fields.
    """
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

# — Sidebar: extractor choice & mock data loader — 
st.sidebar.header("Configuration")

use_ai = st.sidebar.radio(
    "Extractor to use:",
    options=["Dummy extractor", "AI extractor"],
    help="Choose Dummy for offline testing or AI to call OpenAI."
)

st.sidebar.markdown("---")
st.sidebar.header("🚀 Mock Transcripts")
examples = {
    "Standard Positive": """Agent: Hello, I’m Sam. Can I get your full name?
Borrower: Alice Johnson
Agent: What loan amount are you seeking?
Borrower: I need a loan for $415,000""",
    "Michael Case": """Agent: Good morning! Thank you for calling Evergreen Mortgage Solutions. My name is Lisa Carter. How can I help you today?
Agent: Wonderful—let’s get started. Can I have your full name, please?
Borrower: Michael Anthony Reynolds.
Agent: And what’s the purchase price or loan amount you’re seeking?
Borrower: The purchase price is $325,000, and I’d like a loan for $300,000.""",
    "Missing Amount": """Agent: Hi there, please provide your full name.
Borrower: Robert King
Agent: Great—thanks Robert. What else can I help you with today?"""
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
st.title("📝 FormsiQ 1003‑Form Field Extractor")
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
            if use_ai == "AI extractor":
                result = extract_fields_via_openai(transcript)
            else:
                result = extract_fields_dummy(transcript)

        if "error" in result:
            st.error(f"Error: {result['error']}")
        else:
            fields = result.get("fields", [])
            if not fields:
                st.warning("No fields extracted.")
            else:
                st.success("Extraction complete:")
                for f in fields:
                    st.markdown(
                        f"**{f['field_name']}:** {f['field_value']} "
                        f"_(Confidence: {f['confidence_score']:.2f})_"
                    )

# — CSS styling —
st.markdown("""
<style>
    .stTextArea textarea {
        font-family: monospace;
        background-color: #f9f9f9;
    }
    .stButton>button {
        background-color: #2C7BE5;
        color: white;
    }
</style>
""", unsafe_allow_html=True)
