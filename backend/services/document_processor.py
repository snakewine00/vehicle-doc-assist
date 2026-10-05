from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from services.ocr import extract_text_from_image


def _ocr_pdf_fallback(pdf: fitz.Document) -> str:
    """
    For scanned PDFs or pages with almost no text, convert the pages to images
    and run OCR as a fallback. This is practical for document capture workflows.
    """
    page_text_parts: list[str] = []

    for page in pdf:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        text = pytesseract.image_to_string(image, config="--psm 11")
        if text.strip():
            page_text_parts.append(text.strip())

    return "\n".join(page_text_parts).strip()


def process_pdf(file_path: str | Path) -> str:
    """
    Extract text from a PDF using PyMuPDF. If the PDF is mostly image-based or
    contains very little extractable text, use OCR as a fallback.
    """
    pdf = fitz.open(file_path)
    text_parts: list[str] = []

    try:
        for page in pdf:
            page_text = page.get_text("text") or ""
            text_parts.append(page_text.strip())

        combined_text = "\n".join(part for part in text_parts if part).strip()

        if len(combined_text) < 80:
            fallback_text = _ocr_pdf_fallback(pdf)
            if fallback_text:
                combined_text = fallback_text

    finally:
        pdf.close()

    return combined_text.strip()


def process_document(file_path: str | Path) -> dict:
    """
    Decide how to process a downloaded document based on extension.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == ".pdf":
        text = process_pdf(path)
        source_type = "pdf"
    elif extension in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}:
        text = extract_text_from_image(path)
        source_type = "image"
    else:
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")

    return {
        "file_name": path.name,
        "file_type": source_type,
        "text": text,
        "text_length": len(text or ""),
    }
