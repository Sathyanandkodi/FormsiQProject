# -*- coding: utf-8 -*-
"""
Streamlit application for extracting 1003 mortgage application fields
from call transcripts. Supports a dummy regex-based extractor and
an AI-based extractor using OpenAI's API.
"""

import os  # For environment variables and file path handling
import re  # For regular expression matching
import json  # For JSON serialization/deserialization
import pandas as pd  # For CSV read/write and DataFrame operations
import streamlit as st  # For building the web application UI
from openai import OpenAI  # OpenAI client library for AI-based extraction
from typing import List, Dict  # For type annotations

# — Streamlit page configuration —
# Sets the page title, layout, and sidebar state
st.set_page_config(
    page_title="FormsiQ Field Extractor",
    layout="centered",
    initial_sidebar_state="expanded"
)

# — OpenAI client setup —
# Reads the API key from environment or Streamlit secrets
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))
)
# Display which model is in use (for debugging/visibility)
st.write(f"🔑 Using OpenAI model: gpt‑4o‑mini")  


def extract_fields_dummy(transcript: str) -> Dict[str, List[Dict]]:
    """
    Dummy extractor: Uses regex patterns to find key fields from the transcript.
    Returns a dict with a "fields" list of field objects.
    Each field object contains 'field_name', 'field_value', and 'confidence_score'.
    """
    fields: List[Dict] = []  # List to accumulate extracted field objects

    # 1) Borrower Name extraction
    name = None
    # Look for 'Borrower: Name' pattern
    m = re.search(r"Borrower\s*:\s*(.+)", transcript, re.IGNORECASE)
    if m:
        raw = m.group(1).strip().rstrip('.')
        # Try to refine name from common phrases
        m2 = (re.search(r"my name is\s+([A-Za-z ]+)", raw, re.IGNORECASE)
              or re.search(r"name'?s\s+([A-Za-z ]+)", raw, re.IGNORECASE))
        name = m2.group(1).strip() if m2 else raw.split(",")[0].strip()
    else:
        # Fallback: direct "my name is" anywhere in transcript
        m2 = re.search(r"my name is\s+([A-Za-z ]+)", transcript, re.IGNORECASE)
        if m2:
            name = m2.group(1).strip()
    if name:
        fields.append({
            "field_name": "Borrower Name",
            "field_value": name,
            "confidence_score": 0.50
        })

    # 2) Property Address extraction
    # Matches phrases like "home at ... ."
    m = re.search(r"(?:home at|it['’]?s)\s*(.+?)\.", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Property Address",
            "field_value": m.group(1).strip(),
            "confidence_score": 0.50
        })

    # 3) Loan Amount extraction
    # Searches for patterns like "loan for $X", "purchase price is $X", or "outstanding balance $X"
    m = (re.search(r"loan for\s*\$?([\d,]+)", transcript, re.IGNORECASE)
         or re.search(r"purchase price is\s*\$?([\d,]+)", transcript, re.IGNORECASE)
         or re.search(r"outstanding balance.*?\$?([\d,]+)", transcript, re.IGNORECASE))
    if m:
        fields.append({
            "field_name": "Loan Amount",
            "field_value": f"${m.group(1).strip()}",
            "confidence_score": 0.50
        })

    # 4) Loan Term extraction (e.g., "30-year fixed rate")
    m = re.search(r"(\d+)-year fixed rate", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Loan Term",
            "field_value": f"{m.group(1)}-year",
            "confidence_score": 0.50
        })

    # 5) Interest Rate extraction (e.g., "rate is 3.5%")
    m = re.search(r"rate is\s*([\d.]+%)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Interest Rate",
            "field_value": m.group(1),
            "confidence_score": 0.75
        })

    # 6) SSN extraction
    m = re.search(r"SSN\s*(?:is)?\s*([\d-]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "SSN",
            "field_value": m.group(1),
            "confidence_score": 0.90
        })

    # 7) Date of Birth extraction
    m = re.search(r"DOB\s*(?:is)?\s*([\d/]+)", transcript, re.IGNORECASE)
    if m:
        fields.append({
            "field_name": "Date of Birth",
            "field_value": m.group(1),
            "confidence_score": 0.95
        })

    # 8) Income extraction (annual or gross monthly)
    m = (re.search(r"annual income.*?\$?([\d,]+)", transcript, re.IGNORECASE)
         or re.search(r"gross monthly income.*?\$?([\d,]+)", transcript, re.IGNORECASE))
    if m:
        fields.append({
            "field_name": "Income",
            "field_value": f"${m.group(1).strip()}",
            "confidence_score": 0.75
        })

    # Return all extracted fields
    return {"fields": fields}


def extract_fields_via_openai(transcript: str) -> Dict:
    """
    AI-based extractor: Sends the transcript to OpenAI's GPT model
    with a system prompt to extract all 1003 fields. Returns parsed JSON.
    """
    # Define the system prompt to guide the model's behavior
    system_prompt = (
        "You are a data extraction assistant. "
        "Extract all fields from the 1003 mortgage application form "
        "(Borrower Name, Loan Amount, Property Address, Loan Term, Interest Rate, "
        "SSN, Date of Birth, Income, etc.) from the call transcript. "
        "For each field, output an object with 'field_name', 'field_value', and "
        "'confidence_score' (0–1). Respond ONLY with JSON: { \"fields\": [ ... ] }."
    )
    # Prepare the user message with the actual transcript
    user_prompt = f"Transcript:\n\"\"\"\n{transcript}\n\"\"\""
    try:
        # Call the OpenAI chat completion API
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=700,
        )
        # Parse and return the JSON content from the response
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        # Return error message if the API call fails
        return {"error": str(e)}


# — Initialize session state for transcript input and example selection —
if "transcript_input" not in st.session_state:
    st.session_state.transcript_input = ""
if "example_choice" not in st.session_state:
    st.session_state.example_choice = ""

# — Sidebar configuration for extractor choice and mock transcripts —
st.sidebar.header("Configuration")
use_ai = st.sidebar.radio(
    "Extractor to use:",
    ("Dummy extractor", "AI extractor")
)

st.sidebar.markdown("---")
st.sidebar.header("🚀 Mock Transcripts")

# Load pre-saved example transcripts for quick testing
with open("mock_transcripts.json") as f:
    examples = json.load(f)

st.sidebar.selectbox(
    "Choose an example",
    [""] + list(examples.keys()),
    key="example_choice"
)
if st.sidebar.button("Load example"):
    choice = st.session_state.example_choice
    if choice in examples:
        st.session_state.transcript_input = examples[choice]

# — Main application UI —
st.title("📝FormsiQ 1003‑Form Field Extractor Model")
st.markdown("Paste or upload transcripts, then click **Extract Fields**.")

# Informational banner for input options
st.markdown(
    """
<div style="padding:10px; background-color:#f9f9f9; border-left:4px solid #2C7BE5; margin-bottom:15px;">
<strong>Input:</strong> Either paste a single transcript below or upload a CSV
(with a column named <code>transcript</code>) to process multiple records.
</div>
""", unsafe_allow_html=True
)

# File uploader for batch processing via CSV
uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])
transcripts: List[str] = []

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        if "transcript" in df.columns:
            st.success(f"Loaded {len(df)} transcripts from {uploaded_file.name}")
            transcripts = df["transcript"].dropna().astype(str).tolist()
        else:
            st.error("CSV must contain a 'transcript' column.")
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
else:
    # Single transcript textarea if no CSV is uploaded
    transcript = st.text_area(
        "Call Transcript",
        value=st.session_state.transcript_input,
        height=250,
        key="transcript_input",
        placeholder="Paste your call transcript here…"
    )
    if transcript.strip():
        transcripts = [transcript.strip()]

# — Extract Fields button and processing —
if st.button("Extract Fields"):
    if not transcripts:
        st.error("Please provide at least one transcript (paste or CSV upload).")
    else:
        for idx, tx in enumerate(transcripts, start=1):
            st.markdown(f"---\n**Transcript #{idx}:**")
            # Show a preview of the transcript (read-only)
            st.text_area(f"Preview #{idx}", tx, height=120, disabled=True, key=f"tx_{idx}")
            with st.spinner(f"Processing transcript #{idx}…"):
                # Choose between dummy or AI extractor
                if use_ai == "AI extractor":
                    result = extract_fields_via_openai(tx)
                    # Handle case where AI extractor returns no fields
                    if isinstance(result, dict) and "fields" in result and not result["fields"]:
                        st.info("There is no data relevant to 1003 form from the provided transcript. Please check again.")
                        continue
                    # Handle API rate limit or quota errors
                    if "error" in result and any(code in result["error"].lower() for code in ("quota", "429", "rate limit")):
                        st.error(
                            "🚫 AI extractor is currently overloaded or out of quota.\n"
                            "Please switch to **Dummy extractor** in the sidebar and run again."
                        )
                        continue
                else:
                    # Use simpler regex-based extractor
                    result = extract_fields_dummy(tx)

            # Display errors or JSON results
            if "error" in result:
                st.error(f"Error: {result['error']}")
            else:
                st.subheader("JSON Output")
                st.json(result)

# — Custom CSS styling for text areas and buttons —
st.markdown(
    """
<style>
    .stTextArea textarea { font-family: monospace; }
    .stButton>button { background-color: #2C7BE5; color: white; }
</style>
""", unsafe_allow_html=True
)
