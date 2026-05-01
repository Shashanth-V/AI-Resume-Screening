# RecruitAI — AI Resume Screening with Blockchain Certificate Verification

**Group No. 5 | REVA University**

A full-stack web application that combines AI-powered resume screening with blockchain-based certificate verification and WhatsApp automation for candidate certificate collection.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Directory Structure](#4-directory-structure)
5. [Key Features](#5-key-features)
6. [Database Design](#6-database-design)
7. [API Endpoints Reference](#7-api-endpoints-reference)
8. [Smart Contract](#8-smart-contract)
9. [How to Run](#9-how-to-run)
10. [WhatsApp Webhook Setup](#10-whatsapp-webhook-setup)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Project Overview

RecruitAI helps recruiters:

- **Rank resumes** against job descriptions using hybrid AI scoring (TF-IDF + semantic overlap + skill matching)
- **Extract candidate details** (name, phone, certification claims) from resumes automatically
- **Request certificates via WhatsApp** using Twilio webhook integration
- **Verify certificates** using OCR + issuer validation pipeline
- **Store verification records** on blockchain (Ganache + Solidity) with local fallback
- **Cross-check** resume claims against blockchain-verified certificates

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                    │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────┐  │
│  │  auth.html   │  │    index.html     │  │ app.js   │  │
│  │ (Login/Reg) │  │ (Dashboard SPA)  │  │ + style │  │
│  └──────┬───────┘  └────────┬──────────┘  └────┬─────┘  │
└─────────┼──────────────────┼───────────────────┼─────────┘
          │  HTTP/JSON       │  HTTP/JSON        │
          ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK BACKEND (app.py)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Auth      │  │ Resume     │  │ Certificate       │  │
│  │ Routes   │  │ Analysis  │  │ Routes          │  │
│  └────┬────┘  └─────┬────┘  └─────────┬─────────┘  │
│       │               │                  │             │
│       ▼               ▼                  ▼             │
│  ┌─────────────┐  ┌──────────────────────────────┐ │
│  │ SQLite DB   │  │ Background Worker            │ │
│  │ (users.db)  │  │ (whatsapp+cert pipeline)    │ │
│  └─────────────┘  └──────────────────────────────┘ │
└───────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                 BLOCKCHAIN LAYER                               │
│  ┌────────────────────────┐  ┌─────────────────────────────┐   │
│  │  Ganache (local)     │  │  web3_connect.py        │   │
│  │  localhost:7545     │  │  (Python ↔ Ethereum) │   │
│  └─────────┬──────────┘  └─────────────────────────────┘   │
└───────────┼─────────────────────────────────────────────────────┘
            │ JSON-RPC
            ▼
┌────────────────────────────┐
│ CertificateVerify.sol    │
│ Smart Contract          │
└────────────────────────┘
```

### Data Flow — Resume Screening

1. User uploads PDFs + job description via browser
2. app.js builds FormData, sends POST to `/upload-resume`
3. Flask extracts text from each PDF using PyPDF2
4. Text is cleaned (lowercase, remove stopwords, strip symbols)
5. **Hybrid scoring**:
   - TF-IDF vectorizer creates term-frequency vectors
   - Cosine similarity computes JD vs resume match
   - Semantic overlap score (token intersection)
   - Skill match score against 150+ known tech skills
6. Results ranked by composite score
7. **Auto-extraction**: Candidate name, phone, cert claims
8. **WhatsApp automation**: Sends certificate request to candidates
### Data Flow — Certificate Verification

1. Candidate replies to WhatsApp with certificate image/PDF
2. Webhook triggers background worker thread
3. Worker downloads media, runs OCR/text extraction
4. Certificate metadata parsed (issuer, title, date, credential ID)
5. **Issuer verification**: Checks Coursera/Udemy/LinkedIn/ Credly APIs
6. Hash stored on blockchain (or local fallback)
7. Verification result sent back to candidate via WhatsApp

---

## 3. Technology Stack

### Backend
- **Python 3.10+** — Core runtime
- **Flask** — Web framework, session management, routing
- **SQLite3** — User authentication database
- **Werkzeug.security** — Password hashing (PBKDF2:SHA256)
- **PyPDF2** — PDF text extraction
- **scikit-learn** — TF-IDF Vectorizer + cosine similarity
- **NLTK** — English stopwords removal
- **Web3.py** — Ethereum blockchain interaction
- **hashlib** — SHA-256 hashing for certificates

### Certificate Processing
- **pytesseract** — OCR for image-based certificates
- **Pillow** — Image processing
- **BeautifulSoup** — HTML parsing for issuer verification
- **requests** — HTTP client for verification APIs

### Messaging
- **Twilio WhatsApp API** — Outbound requests + inbound webhook

### Blockchain
- **Solidity ^0.8.0** — Smart contract language
- **Ganache** — Local Ethereum blockchain
- **web3.py** — Python ↔ Ethereum bridge
- **solc-x** — Solidity compiler

### Frontend
- **HTML5 / CSS3 / JavaScript ES6+** — SPA frontend
- **Custom CSS** — Hand-crafted dark theme with glassmorphism
- **Font Awesome 6.5.1** — Icons
- **Fontshare CDN** — Typography (Cabinet Grotesk, General Sans)

---

## 4. Directory Structure

```
AI-Resume-Screening/
│
├── app.py                          # Flask backend (all routes + logic)
├── resume_matcher.py               # Resume parsing, claims extraction, cross-check
├── cert_verifier.py               # OCR, metadata extraction, issuer verification
├── whatsapp_handler.py           # Twilio WhatsApp integration
├── worker.py                   # Background certificate processing pipeline
├── deploy_contract.py         # Smart contract deployment script
├── requirements.txt           # Python dependencies
├── users.db                   # SQLite database (auto-created)
├── candidate_registry.json   # Phone → candidate mapping (webhook)
├── cert_store.json           # Local certificate fallback storage
├── status.json               # Pipeline status per candidate
│
├── templates/
│   ├── auth.html             # Login/Register page
│   └── index.html           # Main 3-tab SPA dashboard
│
├── static/
│   ├── style.css            # Complete dark-theme CSS
│   └── app.js              # Complete JS for dashboard
│
├── blockchain/
│   ├── __init__.py        # Package init
│   └── web3_connect.py    # Web3.py ↔ Ganache interface
│
├── contracts/
│   └── CertificateVerify.sol   # Solidity smart contract
│
└── uploads/
    ├── resumes/              # Uploaded resume PDFs
    └── certificates/        # Downloaded WhatsApp certificates
```

---

## 5. Key Features

### 5.1 AI Resume Screening — Hybrid Scoring

The resume analysis uses three complementary signals:

| Signal | Method | Weight |
|--------|--------|-------|
| TF-IDF + Cosine Similarity | sklearn TfidfVectorizer + pairwise cosine_similarity | Primary |
| Semantic Overlap | Normalized token intersection (Jaccard-like) | Secondary |
| Skill Match | 150+ known tech skills matched against JD | Tertiary |

Scores are combined with a presentation-friendly boost for faculty demos.

### 5.2 Candidate Extraction

Auto-extracts from resume text:
- **Candidate name** — Multi-strategy extraction (labels, ALL-CAPS, line after "Personal")
- **Phone numbers** — Regex for Indian/US/UK formats
- **Certification claims** — NLP extraction from Certifications section

### 5.3 WhatsApp Automation

- **Certificate request** — Auto-sent when phone number found in resume
- **Inbound webhook** — Receives certificate attachments
- **Background pipeline** — Async processing in separate thread
- **Summary results** — Single message with all verification results

### 5.4 Certificate Verification Pipeline

1. **Download** — Media from Twilio
2. **OCR/Text** — pytesseract or PyPDF2 extraction
3. **Metadata parsing** — Issuer, title, date, credential ID via regex
4. **Issuer verification** — API check for Coursera/Udemy/LinkedIn/Credly
5. **Blockchain store** — Rich metadata + SHA-256 hash
6. **Local fallback** — cert_store.json when blockchain offline

### 5.5 Blockchain Integration

- Stores **hash + rich metadata** on Ethereum (Ganache)
- Verifies by hash lookup
- Fetches candidate-linked certificate ledger
- Optional: DEMO_MODE env var to bypass issuer API checks

### 5.6 Dashboard & Analytics

- **Cumulative ranking** — All candidates across multiple analyses
- **Stat cards** — Resumes analyzed, top match, certs verified
- **Audit logs** — User-scoped action history
- **Sparklines** — Visual trends
- **CSV export** — Download results

### 5.7 Authentication

- **Session-based auth** using Flask sessions
- **Role support**: viewer, recruiter, hr_admin, admin
- **Password hashing**: PBKDF2:SHA256
- Protected routes with `@login_required` and `@roles_required` decorators

---

## 6. Database Design

### SQLite: `users.db`

#### Table: users
| Column     | Type     | Constraints                |
|------------|----------|--------------------------|
| id         | INTEGER  | PRIMARY KEY AUTOINCREMENT |
| fullname   | TEXT     | NOT NULL               |
| email      | TEXT     | NOT NULL UNIQUE         |
| password   | TEXT     | NOT NULL (hashed)      |
| role       | TEXT     | DEFAULT 'recruiter'     |
| created_at | TIMESTAMP | DEFAULT CURRENT       |

#### Table: resumes
| Column        | Type     | Constraints                           |
|--------------|----------|-------------------------------------|
| id           | INTEGER | PRIMARY KEY AUTOINCREMENT              |
| user_id      | INTEGER | NOT NULL, FOREIGN KEY(user_id)    |
| job_description | TEXT  |                                |
| filename    | TEXT    | NOT NULL                      |
| candidate_name | TEXT  |                                |
| phone       | TEXT   |                                |
| score       | REAL   |                                |
| tfidf_score | REAL   |                                |
| semantic_score | REAL |                                |
| cert_claims | TEXT   | (JSON array)                     |
| cert_status | TEXT   | DEFAULT 'pending'               |
| trust_score | REAL   | DEFAULT 0                     |
| wa_status   | TEXT   | WhatsApp delivery status         |
| wa_error    | TEXT   | WhatsApp error message        |
| created_at  | TIMESTAMP | DEFAULT CURRENT               |

#### Table: audit_logs
| Column     | Type     | Constraints              |
|------------|----------|------------------------|
| id         | INTEGER | PRIMARY KEY AUTOINCREMENT |
| user_id    | INTEGER | FOREIGN KEY(users)     |
| action     | TEXT    | NOT NULL           |
| target     | TEXT    |                    |
| details    | TEXT    | (JSON object)       |
| created_at | TIMESTAMP | DEFAULT CURRENT   |

---

## 7. API Endpoints Reference

### Authentication
| Endpoint     | Method | Auth  | Description                |
|--------------|--------|-------|--------------------------|
| `/auth`      | GET    | No    | Render login/register page |
| `/register`  | POST   | No    | Create new account        |
| `/login`     | POST   | No    | Authenticate user       |
| `/logout`    | POST   | No    | Clear session         |
| `/me`       | GET    | Yes   | Get current user      |

### Resume Analysis
| Endpoint           | Method | Auth  | Description                      |
|-------------------|--------|-------|--------------------------------|
| `/upload-resume`     | POST   | Yes    | Analyze resumes (FormData)        |
| `/analysis-history` | GET    | Yes    | Get analysis history            |
| `/delete-resume/<id>` | DELETE | Yes   | Delete single resume          |
| `/delete-resumes/rejected` | DELETE | Yes  | Delete rejected resumes   |
| `/delete-resumes/all` | DELETE | Yes   | Delete ALL resumes        |

### Certificate & Blockchain
| Endpoint              | Method | Auth  | Description                    |
|----------------------|--------|-------|------------------------------|
| `/verify-certificate`   | POST   | Yes   | Verify certificate hash          |
| `/store-certificate`   | POST   | Yes   | Store cert hash on chain      |
| `/blockchain-status`   | GET    | Yes   | Check Ganache connectivity |
| `/ledger-data`       | GET    | Yes   | Get certificate ledger    |
| `/extract-certs-from-resume` | POST | Yes | Extract cert claims   |
| `/cross-check`      | POST   | Yes   | Resume vs blockchain   |

### WhatsApp & Pipeline
| Endpoint             | Method | Auth  | Description                   |
|---------------------|--------|-------|-------------------------------|
| `/send-whatsapp`     | POST   | Yes   | Send certificate request       |
| `/shortlist-notify`  | POST   | Yes   | Notify shortlisted candidates|
| `/whatsapp-webhook` | POST   | No    | Twilio inbound webhook       |
| `/check-cert-status`  | GET    | Yes   | Poll pipeline status         |

### Audit & Actions
| Endpoint         | Method | Auth  | Description            |
|------------------|--------|-------|----------------------|
| `/candidate-action` | POST | Yes   | Track recruiter action |
| `/audit-summary`  | GET   | Yes   | Get audit summary  |
| `/test-whatsapp`  | GET   | No    | Test WhatsApp sends |

---

## 8. Smart Contract

### `contracts/CertificateVerify.sol`

A Solidity smart contract for storing and verifying certificate metadata on-chain.

#### Key Functions

```solidity
// Legacy simple store (backward compat)
function addCertificate(string memory hash) public onlyOwner

// Rich store with metadata
function storeCertificate(
    string memory phone,
    string memory fileHash,
    string memory candidateName,
    string memory certTitle,
    string memory issuerName,
    string memory issueDate,
    bool   isAuthentic,
    string memory credentialId
) public onlyAuthorized

// Verify by hash
function verifyCertificate(string memory hash) public view returns (bool)

// Read certificate metadata
function getCertificate(string memory fileHash) public view returns (...)

// Candidate ledger
function getCandidateCertCount(string memory phone) public view returns (uint256)
function getCandidateCertHash(string memory phone, uint256 index) public view returns (string memory)
```

#### Deployment

```powershell
python deploy_contract.py
```

This automatically updates `CONTRACT_ADDRESS` in `blockchain/web3_connect.py`.

---

## 9. How to Run

### Prerequisites

- Python 3.10 or later
- Ganache (optional, for blockchain features)
- Tesseract OCR (optional, for image certificates)
- Twilio account (optional, for WhatsApp flow)

### Steps

1. **Navigate to project folder**

```powershell
cd D:\Projects\AI-Resume-MP\AI-Resume-Screening
```

2. **Create and activate virtual environment**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. **Install dependencies**

```powershell
pip install -r requirements.txt
pip install py-solc-x
```

4. **(Optional) Create `.env` file**

```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
GANACHE_URL=http://127.0.0.1:7545
DEMO_MODE=false
```

5. **Run the application**

```powershell
python app.py
```

6. **Open in browser**

```
http://127.0.0.1:5000
```

### Deploy Smart Contract (Optional)

1. Start Ganache on `http://127.0.0.1:7545`
2. Run deployment script:

```powershell
python deploy_contract.py
```

3. Restart the Flask app

---

## 10. WhatsApp Webhook Setup

For local development with Twilio WhatsApp:

1. **Start the app**

```powershell
python app.py
```

2. **Start ngrok** (in another terminal)

```powershell
ngrok http 5000
```

3. **Configure Twilio Sandbox**
   - In Twilio Console → WhatsApp Sandbox Settings
   - Set incoming webhook to:
     ```
     https://your-ngrok-domain/whatsapp-webhook
     ```
   - Method: POST

4. **Test** — Send a WhatsApp message to your Twilio sandbox number

---

## 11. Troubleshooting

### Import Errors
- Reinstall dependencies in active venv

### Blockchain Offline
- Start Ganache and redeploy contract

### Twilio Send Failed
- Verify TWILIO credentials in `.env`
- Ensure sandbox enrollment

### Webhook Not Received
- Ensure ngrok is running
- Check Twilio webhook URL

### OCR Weak Results
- Install Tesseract on system
- Use clearer certificate images/PDFs

### DEMO_MODE
- Set `DEMO_MODE=true` in `.env` to bypass strict issuer verification
- Useful for live college demos

---

## Notes

- **Blockchain is optional** — Local fallback (`cert_store.json`) works when Ganache is unavailable
- **WhatsApp is optional** — Manual certificate upload also supported
- This project is suitable for academic/demo use
- Can be extended for production with stronger auth, queueing, and persistence

---

**End of Documentation**
