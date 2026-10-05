import re
from typing import Optional


DATE_PATTERN = r"\b\d{2}[-/]\d{2}[-/]\d{4}\b"


def first_match(patterns: list[str], text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_date_after_label(
    labels: list[str],
    text: str
) -> Optional[str]:
    label_pattern = "|".join(
        re.escape(label) for label in labels
    )

    pattern = rf"(?:{label_pattern})\s*[:\-]?\s*({DATE_PATTERN})"

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(1)

    return None


def extract_driving_licence(text: str) -> dict:
    """
    Extract common driving-licence fields.

    This is a baseline parser, not a replacement for a validated
    government-document verification system.
    """

    clean = re.sub(r"[ \t]+", " ", text)

    licence_number = first_match(
        [
            r"\b([A-Z]{2}\s?\d{2}\s?\d{6,})\b",
            r"\b([A-Z]{2}\d{10,})\b",
        ],
        clean
    )

    dob = extract_date_after_label(
        [
            "date of birth",
            "date of berth",
            "dob",
        ],
        clean
    )

    issue_date = extract_date_after_label(
        [
            "date of issue",
            "issue date",
            "issued on",
        ],
        clean
    )

    expiry_date = extract_date_after_label(
        [
            "valid till",
            "valid upto",
            "valid up to",
            "validity",
        ],
        clean
    )

    name = first_match(
        [
            r"(?:name)\s*[:\-]?\s*([A-Z][A-Z .]{2,})",
        ],
        text
    )

    # Common fallback for OCR layouts where the label itself is lost.
    if not name:
        possible_names = re.findall(
            r"\b[A-Z]{3,}(?:\s+[A-Z]{2,}){1,3}\b",
            text
        )

        for candidate in possible_names:
            candidate = candidate.strip()

            if candidate in {
                "UNION OF INDIA",
                "DRIVING LICENCE",
                "DRIVING LICENSE",
            }:
                continue

            if len(candidate.split()) >= 2:
                name = candidate
                break

    parent_name = first_match(
        [
            r"(?:son|daughter|wife)\s+of\s+([A-Z][A-Z .]{2,})",
            r"(?:son/daughter/wife)\s+of\s+([A-Z][A-Z .]{2,})",
        ],
        text
    )

    return {
        "document_type": "driving_licence",
        "licence_number": licence_number,
        "name": name,
        "date_of_birth": dob,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "parent_name": parent_name,
    }


def extract_generic(text: str, document_type: str) -> dict:
    return {
        "document_type": document_type,
        "raw_text": text,
    }


def extract_fields(text: str, document_type: str) -> dict:
    if document_type == "driving_licence":
        return extract_driving_licence(text)

    return extract_generic(text, document_type)
