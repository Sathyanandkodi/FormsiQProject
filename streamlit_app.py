# streamlit_app.py
import re
import streamlit as st
from typing import List, Dict

# — Streamlit page config (must come before other st.* calls) —
st.set_page_config(
    page_title="FormsiQ Mortgage Extractor",
    layout="centered",
    initial_sidebar_state="expanded"
)

def extract_fields_dummy(transcript: str) -> Dict[str, List[Dict]]:
    """
    Improved dummy extractor:
    - Finds Borrower Name by spotting the agent's "full name" prompt
      then grabbing the next "Borrower: ..." line.
    - Finds Loan Amount by matching "loan for $XXX" or "purchase price is $XXX".
    Returns a dict: { "fields": [ { field_name, field_value, confidence_score }, ... ] }
    """
    fields: List[Dict] = []
    lines = transcript.splitlines()

    # 1) Borrower Name
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

    # 2) Loan Amount
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

# — Initialize transcript_input in session_state if needed —
if "transcript_input" not in st.session_state:
    st.session_state.transcript_input = ""

# — Sidebar: Mock transcripts and loader callback — 
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

def load_example_callback():
    choice = st.session_state.example_choice
    if choice in examples:
        st.session_state.transcript_input = examples[choice]

# selectbox to choose example
st.sidebar.selectbox(
    "Choose an example",
    options=[""] + list(examples.keys()),
    key="example_choice"
)
# button to load it
st.sidebar.button(
    "Load into transcript",
    on_click=load_example_callback
)

# — Main UI — 
st.title("🔎 FormsiQ 1003‑Form Field Extractor")
st.markdown(
    "Paste a mortgage‑call transcript below and click **Extract Fields** to see the dummy extractor in action."
)

# bind textarea to session_state
transcript = st.text_area(
    "Call Transcript",
    height=250,
    key="transcript_input"
)

if st.button("Extract Fields"):
    if not transcript.strip():
        st.error("Transcript is empty—please paste something to test.")
    else:
        result = extract_fields_dummy(transcript)
        fields = result.get("fields", [])
        if not fields:
            st.warning(
                "No fields found. Try using a transcript with:\n"
                "- an agent prompt asking for 'full name' followed by `Borrower: ...`\n"
                "- a phrase like 'loan for $300,000' or 'purchase price is $350,000'."
            )
        else:
            st.success("Found fields:")
            for f in fields:
                st.markdown(
                    f"**{f['field_name']}:** {f['field_value']} "
                    f"_(Confidence: {f['confidence_score']:.2f})_"
                )

# — Simple CSS styling — 
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
