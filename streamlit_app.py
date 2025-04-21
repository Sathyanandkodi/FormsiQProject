import re
from typing import List, Dict

def extract_fields_dummy(transcript: str) -> Dict:
    """
    Improved dummy extractor:
    - Finds the borrower’s full name by looking for the first "Borrower:" line 
      *after* the agent asks for it.
    - Finds the loan amount by looking for common phrasings and a dollar‐amount.
    Returns {"fields": [ { field_name, field_value, confidence_score }, … ]}.
    """
    fields: List[Dict] = []
    lines = transcript.splitlines()

    # 1) Borrower Name: look for agent question then next Borrower: line
    name = None
    for idx, line in enumerate(lines):
        if re.search(r"full name", line, re.IGNORECASE):
            # scan forward for the next Borrower: line
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
            "confidence_score": 0.5
        })

    # 2) Loan Amount: look for "loan for $XXX" or "purchase price is $XXX"
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
            "confidence_score": 0.5
        })

    return {"fields": fields}
