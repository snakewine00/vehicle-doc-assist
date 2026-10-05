import re


DOCUMENT_KEYWORDS = {
    "driving_licence": [
        "driving licence",
        "driving license",
        "licence",
        "license",
        "transport department",
        "union of india",
    ],
    "insurance": [
        "insurance",
        "policy number",
        "premium",
        "insurer",
        "policy period",
        "third party",
        "own damage",
    ],
    "puc": [
        "pollution under control",
        "pollution",
        "puc",
        "emission",
        "validity",
        "certificate of pollution",
    ],
    "rc": [
        "registration certificate",
        "registration no",
        "registration number",
        "chassis number",
        "engine number",
        "vehicle class",
        "registered owner",
    ],
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def classify_document(text: str) -> dict:
    """
    Lightweight baseline classifier.

    This is deliberately deterministic. Later this function can be
    replaced or supplemented by an LLM classifier.
    """

    normalized = normalize_text(text)
    scores = {}

    for document_type, keywords in DOCUMENT_KEYWORDS.items():
        score = 0

        for keyword in keywords:
            if keyword in normalized:
                score += 1

        scores[document_type] = score

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        best_type = "unknown"

    return {
        "document_type": best_type,
        "confidence": best_score,
        "scores": scores,
    }
