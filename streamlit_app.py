# app.py
import re
import streamlit as st
from typing import List, Dict

def extract_fields_dummy(transcript: str) -> Dict:
    """
    Dummy extractor: uses simple regex to pull out
    “Borrower Name” and “Loan Amount” if present.
    Returns the same JSON structure as the final API.
    """
    fields: List[Dict] = []

    # Look for lines like "Borrower Name: John Doe"
    m_name = re.search(r"Borrower Name\s*[:\-]\s*(.+)", transcript, re.IGNORECASE)
    if m_name:
        fields.append({
            "field_name": "Borrower Name",
            "field_value": m_name.group(1).strip(),
            "confidence_score": 0.5  # dummy confidence
        })

    # Look for lines like "Loan Amount: $250,000"
    m_amount = re.search(r"Loan Amount\s*[:\-]\s*(.+)", transcript, re.IGNORECASE)
    if m_amount:
        fields.append({
            "field_name": "Loan Amount",
            "field_value": m_amount.group(1).strip(),
            "confidence_score": 0.5
        })

    return {"fields": fields}

# — Streamlit UI —
st.set_page_config(page_title="Dummy FormsiQ Tester", layout="centered")
st.title("🔍 Dummy FormsiQ Tester")

st.markdown("Paste a mock mortgage‑call transcript below and hit **Extract Fields** to see a stubbed result.")

transcript = st.text_area("Call Transcript", height=250)

if st.button("Extract Fields"):
    if not transcript.strip():
        st.error("Transcript is empty – please paste something to test.")
    else:
        result = extract_fields_dummy(transcript)
        fields = result.get("fields", [])
        if not fields:
            st.warning("No fields found. Try adding lines like `Borrower Name: Alice` or `Loan Amount: $300,000`.")
        else:
            st.success("Found fields:")
            for f in fields:
                st.markdown(f"- **{f['field_name']}:** {f['field_value']} _(Confidence: {f['confidence_score']})_")
