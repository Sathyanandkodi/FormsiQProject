import os
import re
import json
import pandas as pd
import streamlit as st
from openai import OpenAI
from openai.error import RateLimitError, AuthenticationError, APIError
from typing import List, Dict

# — Streamlit page config —
st.set_page_config(
    page_title="FormsiQ Field Extractor",
    layout="centered",
    initial_sidebar_state="expanded"
)

# — OpenAI client —
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", "")))
st.write("🔑 Using OpenAI model: **gpt-4o-mini**")

# — Dummy extractor: covers core 1003 fields —
def extract_fields_dummy(tx: str) -> Dict[str, List[Dict]]:
    fields: List[Dict] = []

    def add_field(name, value, score):
        fields.append({"field_name": name, "field_value": value, "confidence_score": score})

    # Borrower Name
    m = re.search(r"Borrower\s*:\s*(.+)", tx, re.IGNORECASE) \
        or re.search(r"my name is\s+([A-Za-z ]+)", tx, re.IGNORECASE)
    if m:
        add_field("Borrower Name", m.group(1).strip().rstrip("."), 0.50)

    # Property Address
    m = re.search(r"(?:home at|address is|located at)\s*(.+?)\.", tx, re.IGNORECASE)
    if m:
        add_field("Property Address", m.group(1).strip(), 0.50)

    # Purchase Price & Loan Amount
    m_pp = re.search(r"purchase price\s*(?:is)?\s*\$?([\d,]+)", tx, re.IGNORECASE)
    m_la = re.search(r"loan for\s*\$?([\d,]+)", tx, re.IGNORECASE)
    if m_pp:
        add_field("Purchase Price", f"${m_pp.group(1)}", 0.50)
    if m_la:
        add_field("Loan Amount", f"${m_la.group(1)}", 0.50)

    # Loan Term
    m = re.search(r"(\d+)-year", tx, re.IGNORECASE)
    if m:
        add_field("Loan Term", f"{m.group(1)}-year", 0.50)

    # Interest Rate
    m = re.search(r"rate\s*(?:is)?\s*([\d.]+%)", tx, re.IGNORECASE)
    if m:
        add_field("Interest Rate", m.group(1), 0.75)

    # SSN
    m = re.search(r"SSN\s*(?:is)?\s*([\d-]{9,11})", tx, re.IGNORECASE)
    if m:
        add_field("SSN", m.group(1), 0.90)

    # Date of Birth
    m = re.search(r"DOB\s*(?:is)?\s*([\d/]{6,10})", tx, re.IGNORECASE)
    if m:
        add_field("Date of Birth", m.group(1), 0.95)

    # Income (annual or monthly)
    m = re.search(r"annual income\s*\$?([\d,]+)", tx, re.IGNORECASE) \
        or re.search(r"gross monthly income\s*\$?([\d,]+)", tx, re.IGNORECASE)
    if m:
        add_field("Income", f"${m.group(1)}", 0.75)

    return {"fields": fields}


# — AI extractor with error codes —
def extract_fields_via_openai(tx: str) -> Dict:
    prompt_system = (
        "You are a data extraction assistant. Extract fields from the 1003 mortgage form "
        "— Borrower Name, Purchase Price, Loan Amount, Property Address, Loan Term, "
        "Interest Rate, SSN, Date of Birth, Income. Output only valid JSON: "
        '{"fields":[{"field_name":..,"field_value":..,"confidence_score":..},…]}'
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user",   "content": f"Transcript:\\n\"\"\"\n{tx}\n\"\"\""}
            ],
            temperature=0.0,
            max_tokens=800,
        )
        return json.loads(resp.choices[0].message.content)

    except RateLimitError:
        return {"error_code": 429, "error_message": "OpenAI rate limit exceeded."}
    except AuthenticationError:
        return {"error_code": 401, "error_message": "Authentication failed—invalid API key."}
    except APIError:
        return {"error_code": 502, "error_message": "OpenAI service error, please retry later."}
    except Exception as e:
        return {"error_code": 0, "error_message": f"Unexpected error: {e}"}


# — Session init —
if "txt" not in st.session_state:
    st.session_state.txt = ""
if "example" not in st.session_state:
    st.session_state.example = ""


# — Sidebar UI —
st.sidebar.header("Configuration")
mode = st.sidebar.radio("Extractor mode:", ["Dummy extractor", "AI extractor"])

st.sidebar.markdown("---")
st.sidebar.header("Mock Transcripts")
examples = {
    "Full Example": """Agent: Good morning… Borrower: William Martinez …""",
    "Missing income": """Agent: Hi… Borrower: Emily Davis …""",
}
st.sidebar.selectbox("Select example", [""] + list(examples.keys()), key="example")
if st.sidebar.button("Load example"):
    sel = st.session_state.example
    if sel:
        st.session_state.txt = examples[sel]


# — Main UI —
st.title("📝 FormsiQ 1003‑Form Field Extractor")
st.markdown("Paste a transcript or upload a CSV (`transcript` column), then click **Extract Fields**.")

# Instructional banner
st.markdown("""
<div style="padding:10px;background:#f9f9f9;border-left:4px solid #2C7BE5;margin-bottom:15px">
<strong>Input:</strong> Paste into the box below <em>or</em> upload a CSV file 
(with a column named <code>transcript</code>) for batch processing.
</div>
""", unsafe_allow_html=True)

# CSV uploader
uploaded = st.file_uploader("Upload CSV", type=["csv"])
batches: List[str] = []
if uploaded:
    try:
        df = pd.read_csv(uploaded)
        if "transcript" in df.columns:
            batches = df["transcript"].dropna().tolist()
            st.success(f"Loaded {len(batches)} transcripts from `{uploaded.name}`")
        else:
            st.error("CSV must have a `transcript` column.")
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")
else:
    txt = st.text_area(
        "Call Transcript",
        value=st.session_state.txt,
        height=250,
        placeholder="Paste your call transcript here…"
    )
    if txt:
        batches = [txt.strip()]


# Extraction trigger
if st.button("Extract Fields"):
    if not batches:
        st.error("Invalid input format. Provide at least one transcript.")
    for i, tx in enumerate(batches, 1):
        st.markdown(f"---\n**Transcript #{i}**")
        st.text_area(f"Preview #{i}", tx, height=120, disabled=True)
        with st.spinner(f"Processing #{i}…"):
            if mode == "AI extractor":
                res = extract_fields_via_openai(tx)
                # AI errors → friendly guidance
                if "error_code" in res:
                    st.error(f"{res['error_message']} (Code {res['error_code']}). "
                             "Switch to Dummy extractor or retry later.")
                    continue
            else:
                res = extract_fields_dummy(tx)

        # Post‑check: missing core fields?
        fields = res.get("fields", [])
        names = {f["field_name"] for f in fields}
        if not fields:
            st.warning(
                "No fields detected. Ensure your transcript includes lines like:\n"
                "> Borrower: John Doe\n> Loan Amount: $250,000"
            )
            continue
        missing = {"Borrower Name", "Loan Amount"} - names
        if missing:
            st.warning(f"Missing required fields: {', '.join(missing)}. "
                       "Please include them and try again.")
        # Final JSON output
        st.subheader("Extracted JSON")
        st.json(res)

# — CSS tweaks —
st.markdown("""
<style>
.stTextArea textarea { font-family: monospace; }
.stButton>button { background-color: #2C7BE5; color: white; }
</style>
""", unsafe_allow_html=True)
