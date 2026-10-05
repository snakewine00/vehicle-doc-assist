from pathlib import Path

from PIL import Image
import pytesseract

TESSERACT_CMD = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if TESSERACT_CMD.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)


def extract_text_from_image(image_path: str | Path) -> str:
    """
    Extract text from an image using Tesseract OCR.

    We intentionally keep the image in color because the current vehicle-document
    samples perform better without forced grayscale conversion.
    """
    image = Image.open(image_path)

    # A moderate 2x upscale helps OCR on small text without over-processing.
    image = image.resize((image.width * 2, image.height * 2))

    try:
        text = pytesseract.image_to_string(image, config="--psm 11")
    except Exception as exc:
        raise RuntimeError(
            f"Tesseract OCR failed for {Path(image_path).name}: {exc}"
        ) from exc

    return text.strip()
