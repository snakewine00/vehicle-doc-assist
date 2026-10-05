import json
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from services.ai_extractor import extract_document_data, generate_chat_response
from services.document_processor import process_document

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

load_dotenv(PROJECT_ROOT / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def ensure_upload_directory() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_user_memory(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Keep document/chat memory isolated per Telegram user."""
    user_data = getattr(context, "user_data", None)
    if user_data is None:
        return {}
    return user_data.setdefault("vehicle_doc_memory", {})


def format_result(result: dict) -> str:
    """
    Turn the extracted JSON into a user-friendly Telegram message.
    """
    document_type = result.get("document_type") or "unknown"
    lines = [
        "✅ Document processed",
        "",
        f"📄 Type: {document_type.replace('_', ' ').title()}",
    ]

    field_labels = {
        "vehicle_number": "🚘 Vehicle Number",
        "licence_number": "🪪 Licence Number",
        "policy_number": "📋 Policy Number",
        "name": "👤 Name",
        "date_of_birth": "🎂 Date of Birth",
        "issue_date": "📅 Issue Date",
        "expiry_date": "⏳ Expiry Date",
        "parent_name": "👨 Parent / Spouse",
        "insurer": "🏢 Insurer",
        "engine_number": "⚙️ Engine Number",
        "chassis_number": "🧱 Chassis Number",
        "puc_number": "🚦 PUC Number",
    }

    found_field = False
    for key, label in field_labels.items():
        value = result.get(key)
        if value:
            lines.append(f"{label}: {value}")
            found_field = True

    if not found_field:
        if document_type == "unknown":
            lines.append("⚠️ I couldn't confidently extract information from this document.")
        else:
            lines.append("No additional structured fields were confidently extracted.")

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to VehicleDoc AI! 🚗\n\n"
        "Send me a vehicle document as a PDF or image.\n\n"
        "I can extract text and structured details from common vehicle documents."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 How to use VehicleDoc AI as a chatbot\n\n"
        "1. Send a PDF or image.\n"
        "2. I extract the document details and keep them in context.\n"
        "3. Ask me anything about the document or your vehicle paperwork.\n"
        "4. You can also chat normally even without uploading a file.\n\n"
        "Examples:\n"
        "• What is the licence number?\n"
        "• Who is the owner?\n"
        "• When does it expire?\n"
        "• Summarize this document\n"
        "• Can you explain this document in simple terms?"
    )


def _looks_like_question(message_text: str) -> bool:
    normalized = (message_text or "").strip().lower()
    if not normalized:
        return False
    if "?" in normalized:
        return True

    starters = (
        "what", "who", "when", "where", "which", "why", "how", "is", "are",
        "can", "could", "do", "does", "tell", "show", "give", "find", "identify"
    )
    return normalized.startswith(starters) or "tell me" in normalized or "show me" in normalized


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    user_memory = get_user_memory(context)
    last_document_text = user_memory.get("last_document_text")
    last_extracted = user_memory.get("last_document_result")

    if last_document_text:
        answer = generate_chat_response(text, last_document_text, last_extracted)
        await update.message.reply_text(answer)
        return

    answer = generate_chat_response(text)
    await update.message.reply_text(answer)


async def process_saved_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_path: Path,
):
    try:
        await update.message.reply_text("⏳ Processing your document...")

        processed = process_document(file_path)
        text = (processed.get("text") or "").strip()

        if not text:
            await update.message.reply_text(
                "⚠️ I couldn't extract readable text from this document."
            )
            return

        extracted = extract_document_data(text, file_name=processed.get("file_name"))

        if not isinstance(extracted, dict):
            extracted = {
                "document_type": "unknown",
                "confidence": 0.0,
            }

        confidence = extracted.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None

        if confidence is not None and confidence < 0.3:
            await update.message.reply_text(
                "⚠️ I couldn't confidently extract information from this document."
            )
            return

        await update.message.reply_text(format_result(extracted))

        print("\n========== OCR / EXTRACTED TEXT ==========")
        print(text)
        print("===========================================\n")
        print("AI extraction:")
        print(json.dumps(extracted, indent=2, ensure_ascii=False))

        user_memory = get_user_memory(context)
        user_memory["last_document_text"] = text
        user_memory["last_document_result"] = extracted

    except Exception as error:
        print("Processing error:", error)
        await update.message.reply_text(
            "❌ Something went wrong while processing the document.\n\n"
            "Please try again with a clearer PDF or image."
        )


async def handle_documents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document is None:
        return

    original_name = document.file_name or "document.pdf"
    extension = Path(original_name).suffix.lower()

    if extension not in {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}:
        await update.message.reply_text(
            "⚠️ Unsupported file type. Please upload a PDF or image."
        )
        return

    ensure_upload_directory()

    try:
        telegram_file = await context.bot.get_file(document.file_id)
        safe_name = Path(original_name).name
        file_path = UPLOAD_DIR / safe_name
        await telegram_file.download_to_drive(file_path)
    except Exception as error:
        print("Telegram download failed:", error)
        await update.message.reply_text(
            "⚠️ I couldn't download the document from Telegram. Please try again."
        )
        return

    await update.message.reply_text(f"📥 Received: {safe_name}")
    await process_saved_file(update, context, file_path)


async def handle_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image = update.message.photo[-1] if update.message.photo else None
    if image is None:
        return

    ensure_upload_directory()

    try:
        telegram_file = await context.bot.get_file(image.file_id)
        file_name = f"{image.file_unique_id}.jpg"
        file_path = UPLOAD_DIR / file_name
        await telegram_file.download_to_drive(file_path)
    except Exception as error:
        print("Telegram image download failed:", error)
        await update.message.reply_text(
            "⚠️ I couldn't download the image. Please try again."
        )
        return

    await update.message.reply_text(f"📥 Received image: {file_name}")
    await process_saved_file(update, context, file_path)


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in the project .env file.")

    if not GROQ_API_KEY:
        print("Warning: GROQ_API_KEY is not set. The bot will continue with local fallback extraction.")

    ensure_upload_directory()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_documents))
    app.add_handler(MessageHandler(filters.PHOTO, handle_images))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("VehicleDoc AI bot is running...")
    print(f"Upload directory: {UPLOAD_DIR}")
    app.run_polling()


if __name__ == "__main__":
    main()
