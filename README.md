# VehicleDoc AI

A Telegram-based AI assistant for vehicle documents. It can process uploaded PDFs and images, extract document details, and answer follow-up questions about the uploaded document in chat.

## What it does

- Accepts PDF, JPG, PNG, WEBP, BMP, and TIFF uploads
- Extracts document text using PyMuPDF + OCR fallback
- Identifies document types such as:
  - driving licence
  - RC / registration certificate
  - insurance
  - PUC
  - warranty
- Extracts structured fields like:
  - name
  - vehicle number
  - licence number
  - policy number
  - insurer
  - issue and expiry dates
  - engine and chassis numbers
- Answers questions such as:
  - “What is the licence number?”
  - “Who is the owner?”
  - “When does it expire?”
  - “Summarize this document”
- Keeps separate memory for each Telegram user

## Current workflow

```text
Telegram user
  ↓
PDF / image upload
  ↓
Download to local uploads folder
  ↓
OCR / PDF text extraction
  ↓
AI document extraction with Groq
  ↓
Structured JSON validation
  ↓
Telegram summary + chat Q&A
```

## Project structure

```text
vehicle_doc_ai/
├── .env
├── .env.example
├── README.md
├── backend/
│   ├── bot.py
│   ├── requirements.txt
│   ├── tests/
│   │   └── test_chat_qna.py
│   └── services/
│       ├── __init__.py
│       ├── ai_extractor.py
│       ├── classifier.py
│       ├── document_processor.py
│       ├── extractor.py
│       └── ocr.py
└── data/
    └── uploads/
```

## 1. Create the virtual environment

Windows CMD:

```cmd
D:
cd \vehicle_doc_ai\backend
python -m venv venv
venv\Scripts\activate
```

## 2. Install requirements

```cmd
python -m pip install -r requirements.txt
```

## 3. Install Tesseract OCR

Install Tesseract for Windows and ensure the executable is available at:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

If your installation path differs, update the Tesseract executable path in the OCR service.

## 4. Configure environment variables

Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
```

You can also copy the example file if available:

```cmd
copy .env.example .env
```

Do not commit `.env` to version control.

## 5. Run the bot

From the backend folder:

```cmd
venv\Scripts\activate
python bot.py
```

Then start a chat with your Telegram bot and send:

```text
/start
```

You can then upload a PDF or image and ask questions in the same chat.

## 6. Sample questions

- What is the vehicle number?
- What is the licence number?
- Who is the owner?
- When does it expire?
- Summarize the document
- Is this a driving licence?

## Notes

- The AI layer uses Groq as the active LLM provider.
- The app keeps uploaded document context separated per Telegram user.
- Local fallback extraction remains available if the API is unavailable or the key is missing.
- OCR and AI outputs should still be checked before relying on them for legal or identity-critical decisions.

## Important

This project is designed for document assistance and extraction, not for replacing official identity verification or legal document validation.
