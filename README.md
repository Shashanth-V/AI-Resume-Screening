# RecruitAI — AI Resume Screening with Blockchain Certificate Verification

A full-stack web application that combines **AI-powered resume screening** (TF-IDF + Cosine Similarity) with **blockchain-based certificate verification** (SHA-256 + Ethereum Smart Contracts).

Recruiters upload PDF resumes, define a job description, and the system ranks candidates by relevance. Certificates can be stored on and verified against a local Ethereum blockchain (Ganache), with per-candidate linking so you know whose certificate was verified.
---

## Screenshots

| Auth Page | Resume Screening | Certificate Verification | Dashboard |
|-----------|-----------------|--------------------------|-----------|
| Split-screen login/register | Drag-drop upload + TF-IDF ranking | Store & Verify with blockchain | Cumulative stats + filtered table |

---

## Features

- **AI Resume Ranking** — TF-IDF vectorization + cosine similarity scores resumes 0–100% against a job description
- **Cumulative Results** — Upload 5 resumes now, 5 later — all 10 are ranked together
- **Individual File Removal** — Remove any uploaded file before analysis (not possible with native FileList)
- **Blockchain Certificate Storage** — SHA-256 hash of certificates stored immutably on Ethereum (Ganache)
- **Candidate-Linked Verification** — Certificates are tied to specific candidates, preventing cross-candidate false positives
- **3 Verification Outcomes** — Verified (green), Mismatch (amber), Not Found (red)
- **Recruiter Dashboard** — Animated counters, sparkline charts, filterable candidate table with cert status
- **Auth System** — SQLite-backed register/login/logout with session management
- **CSV Export** — Download ranking results as CSV
- **Dark Theme UI** — Glassmorphism, animated background orbs, SVG score rings, confetti celebration
- **Responsive** — Works on desktop, tablet, and mobile

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.10+, Flask, SQLite3, werkzeug |
| **AI/NLP** | scikit-learn (TF-IDF + Cosine Similarity), NLTK (stopwords), PyPDF2 |
| **Blockchain** | Solidity ^0.8.0, Web3.py, Ganache (local Ethereum) |
| **Frontend** | HTML5, CSS3 (custom dark theme), JavaScript (ES6+), Canvas API |
| **Fonts** | Cabinet Grotesk, General Sans, Clash Display, Satoshi (via Fontshare) |
| **Icons** | Font Awesome 6.5.1 |

---

## Project Structure

```
MINIPROJECT/
├── app.py                     # Flask backend — all routes, auth, resume analysis, cert handling
├── deploy_contract.py         # One-time script to compile & deploy smart contract to Ganache
├── requirements.txt           # Python dependencies
├── users.db                   # SQLite database (auto-created on first run)
│
├── templates/
│   ├── auth.html              # Login / Register page (split-screen design)
│   └── index.html             # Main 3-tab SPA (Resume Screening, Certificates, Dashboard)
│
├── static/
│   ├── style.css              # Dark theme CSS (glassmorphism, animations, responsive)
│   └── app.js                 # Frontend logic (upload, analysis, certs, dashboard, confetti)
│
├── blockchain/
│   ├── __init__.py            # Package init
│   └── web3_connect.py        # Web3.py interface to Ganache
│
├── contracts/
│   └── CertificateVerify.sol  # Solidity smart contract
│
└── uploads/                   # Uploaded resume PDFs (auto-created)
```

---

## Prerequisites

- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **Ganache** — [Download](https://trufflesuite.com/ganache/) (for blockchain features)
- **Git** (optional) — for cloning the repo

---

## Setup & Run

### 1. Clone the repository

```bash
git clone <repo-url>
cd MINIPROJECT
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install py-solc-x
```

> `py-solc-x` is needed only for deploying the smart contract (step 5).

### 4. Run the app (without blockchain)

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

> Resume screening works fully without Ganache. The Certificates tab will show "Blockchain Offline" but AI features are unaffected.

### 5. Set up blockchain (optional but recommended)

**a)** Open **Ganache** → click **Quickstart (Ethereum)**  
You should see 10 accounts with 100 ETH each and RPC server at `HTTP://127.0.0.1:7545`.

**b)** Deploy the smart contract:

```bash
python deploy_contract.py
```

Output:
```
[1/4] Connecting to Ganache...
       Connected! Chain ID: 1337, Accounts: 10
[2/4] Compiling CertificateVerify.sol...
       Compiled successfully!
[3/4] Deploying to Ganache...
       Deployed at: 0x40C7e31f3e7249506bAdbAA2B6396f921f64b0B4
       Tx hash:     879fbcab...
       Gas used:    452412
[4/4] Updating blockchain/web3_connect.py...
       CONTRACT_ADDRESS updated!
```

The script automatically updates the contract address in the code.

**c)** Restart Flask:

```bash
python app.py
```

The Certificates tab will now show **"Ganache Connected"** with a green dot.

> **Note:** If you close and reopen Ganache (it resets), run `python deploy_contract.py` again.

---

## Usage Guide

### Register & Login

1. Open http://127.0.0.1:5000
2. Click **"Create Account"** → fill in name, email, password → submit
3. You're automatically logged in and redirected to the dashboard

### Resume Screening

1. Go to the **Resume Screening** tab
2. Paste a job description in the left panel (or use quick-add skill tags)
3. Drag & drop PDF resumes into the upload zone (or click to browse) — max 10 files
4. Remove individual files with the ❌ button if needed
5. Click **"Analyze Resumes"**
6. Results appear as ranked cards with animated score rings
7. Upload more resumes later — they accumulate with previous results

### Certificate Verification

1. Go to the **Certificates** tab
2. Select a candidate from the dropdown (populated from analyzed resumes)
3. **Store:** Upload the candidate's certificate → click "Store on Blockchain" → hash is stored permanently
4. **Verify:** Upload a certificate → click "Verify Now" → system checks:
   - Is the hash on the blockchain? (authenticity)
   - Does it match the hash stored for THIS candidate? (ownership)
5. Three possible outcomes:
   - **✅ Verified** — hash matches this candidate's stored certificate
   - **⚠️ Mismatch** — hash exists on blockchain but belongs to someone else
   - **❌ Not Found** — hash not on blockchain at all

### Dashboard

1. Go to the **Dashboard** tab
2. See cumulative stats: resumes analyzed, top score, certs verified, pending
3. Filter candidates by minimum score or certificate status (Verified / Pending)
4. Click **Export CSV** to download results
5. Click the shield icon on any row to jump to the cert tab with that candidate pre-selected

---

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth` | GET | No | Login/register page |
| `/register` | POST | No | Create account (JSON: fullname, email, password) |
| `/login` | POST | No | Authenticate (JSON: email, password) |
| `/logout` | POST | No | Clear session |
| `/me` | GET | Yes | Current user info |
| `/` | GET | Yes | Main dashboard SPA |
| `/upload-resume` | POST | Yes | Analyze resumes (FormData: job_description + resumes[]) |
| `/store-certificate` | POST | Yes | Store cert hash on blockchain (FormData: certificate + candidate) |
| `/verify-certificate` | POST | Yes | Verify cert hash (FormData: certificate + candidate) |
| `/blockchain-status` | GET | Yes | Check Ganache connectivity |
| `/dashboard-data` | GET | Yes | Session-persisted results & stats |

---

## How It Works

### Resume Ranking Algorithm

1. Job description + resume texts are cleaned (lowercase, stopwords removed)
2. **TF-IDF Vectorizer** converts text to numerical term-frequency vectors
3. **Cosine Similarity** measures the angle between the JD vector and each resume vector
4. Scores range from 0% (no overlap) to 100% (perfect match)
5. Results are sorted descending and accumulated across multiple uploads

### Blockchain Certificate Verification

1. A certificate file (PDF/image) is uploaded
2. Server computes the **SHA-256 hash** of the raw file bytes (64-char hex string)
3. **Store:** Hash is written to the Ethereum blockchain via `addCertificate()` smart contract function
4. **Verify:** Hash is checked against blockchain via `verifyCertificate()` read-only call
5. A per-candidate mapping ensures certificates can't be falsely attributed to the wrong person
6. Even a 1-pixel change in a certificate produces a completely different hash — tamper-proof

### Smart Contract

```solidity
contract CertificateVerify {
    mapping(string => bool) private certificates;
    function addCertificate(string memory hash) public onlyOwner { ... }
    function verifyCertificate(string memory hash) public view returns (bool) { ... }
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in your active venv |
| Blockchain shows "Offline" | Make sure Ganache is open, then run `python deploy_contract.py` |
| `PUSH0` / `invalid opcode` error on deploy | Already fixed — `deploy_contract.py` uses `evmVersion: "london"` |
| `Certificate already exists` error | That cert was already stored. Use **Verify** instead of Store. |
| Double file picker opens | Fixed in latest code — if it happens, clear browser cache |
| NLTK stopwords download hangs | The app auto-downloads on first run. Check your internet connection. |
| `py-solc-x` not found | Install it separately: `pip install py-solc-x` |

---

## License

This project is built for academic purposes as part of a university mini-project at REVA University.

---

**Built with ❤️ by Group No. 5 — Aryan · Jagan · Anurag**
