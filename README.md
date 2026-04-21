# RecruitAI

AI Resume Screening + Certificate Verification with Blockchain and WhatsApp automation.

RecruitAI helps recruiters:
- Rank resumes against a job description using TF-IDF and cosine similarity.
- Extract candidate details and certificate claims from resumes.
- Request certificates on WhatsApp automatically (Twilio webhook flow).
- Verify certificates with OCR + issuer checks.
- Store verification records on blockchain (Ganache + Solidity) with local fallback.

## Key Features

- Authentication with role support (viewer, recruiter, hr_admin, admin)
- Resume scoring with hybrid signals:
       - TF-IDF score
       - lightweight semantic overlap score
- Candidate extraction from resume text (name, phone, certificate claims)
- WhatsApp automation:
       - send certificate request message
       - receive candidate replies via webhook
       - process attachments in background thread pipeline
- Certificate verification pipeline:
       - download media
       - OCR/text extraction
       - issuer/source validation
       - trust scoring and claim matching
- Blockchain integration:
       - store hash-only and rich certificate metadata
       - verify by hash
       - fetch candidate-linked certificate ledger
- Dashboard + audit logs + analysis history + delete endpoints

## Tech Stack

- Backend: Python, Flask, SQLite
- NLP/AI: scikit-learn, NLTK, PyPDF2
- Certificate processing: pytesseract, Pillow, BeautifulSoup, requests
- Messaging: Twilio WhatsApp API
- Blockchain: Solidity, Web3.py, Ganache
- Frontend: HTML, CSS, JavaScript

## Project Structure

AI-Resume-Screening/
- app.py
- resume_matcher.py
- cert_verifier.py
- whatsapp_handler.py
- worker.py
- deploy_contract.py
- requirements.txt
- candidate_registry.json
- cert_store.json
- status.json
- blockchain/
       - web3_connect.py
- contracts/
       - CertificateVerify.sol
- templates/
       - auth.html
       - index.html
- static/
       - app.js
       - style.css
- uploads/

## Prerequisites

- Python 3.10 or later
- Git
- Ganache (optional, for blockchain features)
- Tesseract OCR installed on system (recommended for image-based certificates)
- Twilio account (optional, for WhatsApp flow)

## Setup

1. Move into project folder.

```powershell
cd D:\AI-Resume-MP\AI-Resume-Screening
```

2. Create and activate virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies.

```powershell
pip install -r requirements.txt
pip install py-solc-x
```

4. Create .env file (for Twilio and optional blockchain URL).

Example:

```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
GANACHE_URL=http://127.0.0.1:7545
```

5. Run the app.

```powershell
python app.py
```

App URL: http://127.0.0.1:5000

## Optional: Deploy Smart Contract to Ganache

1. Start Ganache on http://127.0.0.1:7545
2. Deploy contract:

```powershell
python deploy_contract.py
```

This automatically updates the contract address in blockchain/web3_connect.py.

If Ganache resets, deploy again.

## WhatsApp Webhook Setup (Twilio)

For local development, expose Flask with ngrok and set Twilio sandbox webhook.

1. Start app:

```powershell
python app.py
```

2. In another terminal, run ngrok:

```powershell
ngrok http 5000
```

3. In Twilio WhatsApp Sandbox settings:
- Set incoming message webhook URL to:
       https://your-ngrok-domain/whatsapp-webhook
- Method: POST

## Main API Routes

- Auth and profile:
       - GET /auth
       - POST /register
       - POST /login
       - POST /logout
       - GET /me
- Resume analysis:
       - POST /upload-resume
       - GET /analysis-history
       - DELETE /delete-resume/<id>
       - DELETE /delete-resumes/rejected
       - DELETE /delete-resumes/all
- Certificate and blockchain:
       - POST /verify-certificate
       - POST /store-certificate
       - GET /blockchain-status
       - GET /ledger-data
- WhatsApp and pipeline:
       - POST /send-whatsapp
       - POST /shortlist-notify
       - POST /whatsapp-webhook
       - GET /check-cert-status
- Cross-check and extraction:
       - POST /extract-certs-from-resume
       - POST /cross-check
- Audit:
       - POST /candidate-action
       - GET /audit-summary

## Troubleshooting

- Import errors:
       - Reinstall dependencies in active venv.
- Blockchain offline:
       - Start Ganache and redeploy contract.
- Twilio send failed:
       - Verify TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and sandbox enrollment.
- Webhook not received:
       - Ensure ngrok is running and Twilio webhook points to /whatsapp-webhook.
- OCR weak results:
       - Install Tesseract and use clearer certificate images/PDFs.

## Notes

- Blockchain is optional. If unavailable, local fallback storage is used for processed cert records.
- This project is suitable for academic/demo use and can be extended for production with stronger auth, queueing, and persistence strategies.
