"""Extract structured data from email content using Gemini. One call with JSON schema output."""

import json
import os
import base64
from typing import Optional

import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["NEW_FOLIO_PURCHASE", "ADDITIONAL_PURCHASE", "SIP_REGISTRATION", "SIP_INSTALMENT", "REDEMPTION", "CHANGE_OF_BANK"]},
        "folio": {"type": "string"},
        "PAN": {"type": "string"},
        "amount": {"type": "string"},
        "mode": {"type": "string"},
        "relation": {"type": "string"},
        "account_last_4": {"type": "string"},
        "scheme": {"type": "string"},
        "plan": {"type": "string", "enum": ["REGULAR", "DIRECT"]},
        "ARN": {"type": "string"},
        "EUIN": {"type": "string"},
        "documents_attached": {"type": "array", "items": {"type": "string"}},
        "ticked_boxes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["type", "folio", "PAN", "amount", "mode", "scheme", "plan"]
}


def build_extraction_prompt(email_text: str, attachment_texts: list) -> str:
    att_summary = "\n".join(
        f"[Attachment {i+1}: {a.get('file_name','')}] {a.get('text','')[:500]}"
        for i, a in enumerate(attachment_texts) if a.get("text")
    )
    return f"""Extract structured data from this email request and any attachment text below.
Return ONLY valid JSON matching the schema.

EMAIL:
{email_text}

ATTACHMENT TEXT:
{att_summary or "None"}

Rules:
- type: classify the request type from the email intent
- folio: extract folio number (8 digits/2 digits format), normalise by removing spaces, / and -
- PAN: extract PAN if mentioned
- amount: extract the amount in INR (digits only)
- mode: payment mode (NEFT, RTGS, UPI, IMPS, CHEQUE, NACH)
- relation: relationship of payer to first holder if payer is not first holder
- account_last_4: last 4 digits of paying account
- scheme: scheme name
- plan: REGULAR or DIRECT
- ARN: distributor ARN if mentioned
- EUIN: distributor EUIN if mentioned
- documents_attached: list document names from attachments
- ticked_boxes: list any ticked/checked boxes mentioned in forms

Return JSON."""


def extract(email_text: str, attachment_texts: list = None) -> dict:
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not set", "type": "UNKNOWN", "folio": "", "PAN": "", "amount": "", "mode": "", "scheme": "", "plan": ""}

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = build_extraction_prompt(email_text, attachment_texts or [])
        response = model.generate_content(prompt)

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": f"Failed to parse Gemini response: {text[:200]}", "type": "UNKNOWN"}
    except Exception as e:
        return {"error": f"Gemini API error: {str(e)}", "type": "UNKNOWN", "folio": "", "PAN": "", "amount": "", "mode": "", "scheme": "", "plan": ""}