import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from services.classifier import classify_document
from services.extractor import extract_fields

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ALLOWED_DOCUMENT_TYPES = {
    "driving_licence",
    "rc",
    "insurance",
    "puc",
    "warranty",
    "unknown",
}

DEFAULT_EXTRACTION = {
    "document_type": None,
    "vehicle_number": None,
    "licence_number": None,
    "policy_number": None,
    "name": None,
    "date_of_birth": None,
    "issue_date": None,
    "expiry_date": None,
    "parent_name": None,
    "insurer": None,
    "engine_number": None,
    "chassis_number": None,
    "puc_number": None,
    "confidence": None,
}


def _field_lookup(extracted: dict | None, field_names: list[str]) -> str | None:
    if not isinstance(extracted, dict):
        return None

    for field_name in field_names:
        value = extracted.get(field_name)
        if value:
            return str(value)
    return None


def _normalise_string(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None

    return value


def _fallback_extraction(raw_text: str, inferred_type: str | None = None) -> dict:
    """
    Local fallback when the Groq request fails or the API key is not configured.
    This keeps the app alive and preserves the original keyword/regex workflow.
    """
    text = (raw_text or "").strip()

    if not text:
        return {
            **DEFAULT_EXTRACTION,
            "document_type": "unknown",
            "confidence": 0.0,
        }

    classification = classify_document(text)
    detected_type = inferred_type or classification.get("document_type", "unknown")
    extracted = extract_fields(text, detected_type)

    merged = {**DEFAULT_EXTRACTION, **extracted}
    merged["document_type"] = detected_type if detected_type in ALLOWED_DOCUMENT_TYPES else "unknown"
    merged["confidence"] = classification.get("confidence")

    return merged


def validate_extraction_payload(payload: Any) -> dict:
    """
    Validate the model output and coerce it to the expected schema.
    """
    if not isinstance(payload, dict):
        raise ValueError("Groq response is not a JSON object.")

    cleaned = {**DEFAULT_EXTRACTION}

    for key in DEFAULT_EXTRACTION:
        if key in payload:
            cleaned[key] = _normalise_string(payload.get(key))

    if cleaned.get("document_type") not in ALLOWED_DOCUMENT_TYPES:
        cleaned["document_type"] = "unknown"

    if cleaned.get("confidence") is not None:
        try:
            cleaned["confidence"] = float(cleaned["confidence"])
        except (TypeError, ValueError):
            cleaned["confidence"] = None

    return cleaned


def _answer_from_extracted_fields(question: str, extracted: dict | None = None) -> str | None:
    cleaned_question = (question or "").strip().lower()
    if not cleaned_question:
        return None

    extracted = extracted or {}
    if "document type" in cleaned_question or "type of document" in cleaned_question:
        doc_type = extracted.get("document_type")
        if doc_type:
            return f"This appears to be a {doc_type.replace('_', ' ')} document."
        return "I could not confidently identify the document type from this upload."

    field_map = {
        "vehicle number": ["vehicle_number", "registration_number", "reg_no"],
        "licence number": ["licence_number", "license_number"],
        "policy number": ["policy_number"],
        "name": ["name"],
        "owner": ["name"],
        "date of birth": ["date_of_birth"],
        "issue date": ["issue_date"],
        "expiry date": ["expiry_date"],
        "parent name": ["parent_name"],
        "insurer": ["insurer"],
        "engine number": ["engine_number"],
        "chassis number": ["chassis_number"],
        "puc number": ["puc_number"],
    }

    for label, field_names in field_map.items():
        if label in cleaned_question:
            value = _field_lookup(extracted, field_names)
            if value:
                return f"The {label} is {value}."
            return f"I couldn’t find the {label} in this document."

    return None


def answer_question_about_document(
    question: str,
    document_text: str,
    extracted_data: dict | None = None,
) -> str:
    """
    Answer a natural-language question using the extracted document fields and OCR text.
    """
    cleaned_question = (question or "").strip()
    cleaned_text = (document_text or "").strip()

    if not cleaned_question:
        return "Please ask a question about the uploaded document."

    if not cleaned_text:
        return "I don’t see any readable text in the uploaded document yet."

    fallback_answer = _answer_from_extracted_fields(cleaned_question, extracted_data)
    if fallback_answer is not None:
        return fallback_answer

    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        prompt = f"""
You are a vehicle document assistant. Answer only the user’s question using the supplied document text and extracted fields.

Rules:
- Use only the provided information.
- If the answer is missing, say: "I couldn’t find that information in this document."
- Keep the answer concise and in plain English.
- Do not invent values.

User question:
{cleaned_question}

Document text:
{cleaned_text}

Extracted fields:
{json.dumps(extracted_data or {}, indent=2, ensure_ascii=False)}
"""
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": "Answer concise questions about a vehicle document using the provided text only."},
                    {"role": "user", "content": prompt},
                ],
            )
            answer = response.choices[0].message.content.strip()
            if answer:
                return answer
        except Exception as exc:
            print(f"Groq answer generation failed: {exc}")

    return "I couldn’t find that information in this document."


def generate_chat_response(
    user_message: str,
    document_text: str | None = None,
    extracted_data: dict | None = None,
) -> str:
    """
    General AI chat response that can optionally use the uploaded document as context.
    """
    cleaned_message = (user_message or "").strip()
    if not cleaned_message:
        return "Please send a message or question."

    if document_text:
        fallback_answer = _answer_from_extracted_fields(cleaned_message, extracted_data)
        if fallback_answer is not None:
            return fallback_answer

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        if document_text:
            return "I can use the uploaded document as context, but the AI service is not configured yet."
        return "AI chat is not configured yet. Add a GROQ_API_KEY to enable chat responses."

    context_block = ""
    if document_text:
        context_block = f"\nDocument text:\n{document_text}\n\nExtracted fields:\n{json.dumps(extracted_data or {}, ensure_ascii=False, indent=2)}"

    prompt = f"""
You are a helpful AI assistant for a vehicle document app.
Answer the user's message using the document context when it is available.
Keep the reply concise, useful, and grounded in the provided information.
If information is not available, say so clearly.

User message:
{cleaned_message}{context_block}
"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI chatbot and document assistant. Be concise and factual.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        answer = response.choices[0].message.content.strip()
        if answer:
            return answer
    except Exception as exc:
        print(f"Groq chat response failed: {exc}")

    if document_text:
        return answer_question_about_document(cleaned_message, document_text, extracted_data)

    return "I’m here to help. Please upload a document or ask a question about your vehicle paperwork."


def extract_document_data(raw_text: str, file_name: str | None = None) -> dict:
    """
    Send OCR/PDF text to Groq and parse a structured JSON extraction result.
    If the API fails, fall back to the local keyword/regex baselines.
    """
    text = (raw_text or "").strip()

    if not text:
        return {
            **DEFAULT_EXTRACTION,
            "document_type": "unknown",
            "confidence": 0.0,
        }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Groq API key missing; using local fallback extraction.")
        return _fallback_extraction(text)

    prompt = f"""
You are a vehicle document information extraction system.
Analyze the supplied OCR/document text and identify the document type and extract only information supported by the document.

Rules:
- Never invent information.
- If a field is missing, return null.
- Correct obvious OCR mistakes only when the intended value is clear from context.
- Preserve identifiers such as licence numbers, registration numbers, policy numbers and chassis numbers carefully.
- Return structured JSON only.
- Do not provide explanations outside the JSON.
- If the document cannot be confidently identified, use document_type = "unknown".
- Supported document_type values are: driving_licence, rc, insurance, puc, warranty, unknown.

Return this exact JSON schema with no extra commentary:
{{
  "document_type": null,
  "vehicle_number": null,
  "licence_number": null,
  "policy_number": null,
  "name": null,
  "date_of_birth": null,
  "issue_date": null,
  "expiry_date": null,
  "parent_name": null,
  "insurer": null,
  "engine_number": null,
  "chassis_number": null,
  "puc_number": null,
  "confidence": null
}}

OCR / document text:
{text}
"""

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a vehicle document information extraction system. "
                        "Return valid JSON only with the required schema."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        raw_content = response.choices[0].message.content
        payload = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
        validated = validate_extraction_payload(payload)

        if validated.get("document_type") in (None, "unknown"):
            validated["document_type"] = classify_document(text).get("document_type", "unknown")

        return validated

    except Exception as exc:
        print(f"Groq AI extraction failed for {file_name or 'document'}: {exc}")
        return _fallback_extraction(text)

