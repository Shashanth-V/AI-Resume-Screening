"""
app.py — Flask backend for AI Resume Screening with Blockchain Certificate Verification.
Provides authentication (register / login / logout), resume analysis
(TF-IDF + cosine similarity), certificate storage & verification
via a blockchain smart contract (Web3 / Ganache), WhatsApp-based
certificate request pipeline, OCR verification, and resume-vs-cert cross-check.
"""

import os
import re
import hashlib
import sqlite3
import secrets
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

import nltk
# Auto-download NLTK stopwords if not present
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)

from nltk.corpus import stopwords

# Project modules
from blockchain import web3_connect
import whatsapp_handler
import cert_verifier
import resume_matcher
import worker
import json as json_mod

# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATABASE = os.path.join(BASE_DIR, "users.db")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

STOP_WORDS = set(stopwords.words("english"))
ALLOWED_EXTENSIONS = {"pdf"}

# Shared candidate registry (phone → candidate mapping for webhook)
CANDIDATE_REGISTRY = os.path.join(BASE_DIR, "candidate_registry.json")
_reg_lock = __import__('threading').Lock()

def _read_registry() -> dict:
    if not os.path.exists(CANDIDATE_REGISTRY):
        return {}
    try:
        with open(CANDIDATE_REGISTRY, "r") as f:
            return json_mod.load(f)
    except Exception:
        return {}

def _write_registry(data: dict):
    with _reg_lock:
        with open(CANDIDATE_REGISTRY, "w") as f:
            json_mod.dump(data, f, indent=2, default=str)

def _register_candidate(phone: str, candidate_name: str, cert_claims: list):
    reg = _read_registry()
    reg[phone] = {
        "candidate_name": candidate_name,
        "cert_claims": cert_claims,
    }
    _write_registry(reg)

def _lookup_candidate(phone: str) -> dict:
    return _read_registry().get(phone, {})


# ──────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────

def get_db():
    """Open a per-request SQLite connection."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the users table if it doesn't exist."""
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()


init_db()


# ──────────────────────────────────────────────
# Auth decorator
# ──────────────────────────────────────────────

def login_required(f):
    """Redirect to auth page if user is not logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth_page"))
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_storage):
    """Read all pages of a PDF and return the raw text."""
    reader = PdfReader(file_storage)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + " "
    return text.strip()


def clean_text(raw: str) -> str:
    """Lowercase, strip special characters, and remove English stopwords."""
    text = raw.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    tokens = [t for t in tokens if t not in STOP_WORDS]
    return " ".join(tokens)


def sha256_hash(file_bytes: bytes) -> str:
    """Return the hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


# ──────────────────────────────────────────────
# Auth routes
# ──────────────────────────────────────────────

@app.route("/auth")
def auth_page():
    """Render login / register page. Redirect to dashboard if already logged in."""
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("auth.html")


@app.route("/register", methods=["POST"])
def register():
    """Create a new user account."""
    try:
        data = request.get_json()
        fullname = data.get("fullname", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not fullname or not email or not password:
            return jsonify({"error": "All fields are required."}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters."}), 400

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "An account with this email already exists."}), 409

        hashed = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (fullname, email, password) VALUES (?, ?, ?)",
            (fullname, email, hashed)
        )
        db.commit()

        # Auto-login after registration
        user = db.execute("SELECT id, fullname, email FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["fullname"]
        session["user_email"] = user["email"]

        return jsonify({"message": "Account created successfully!", "name": user["fullname"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/login", methods=["POST"])
def login():
    """Authenticate an existing user."""
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required."}), 400

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user or not check_password_hash(user["password"], password):
            return jsonify({"error": "Invalid email or password."}), 401

        session["user_id"] = user["id"]
        session["user_name"] = user["fullname"]
        session["user_email"] = user["email"]

        return jsonify({"message": "Login successful!", "name": user["fullname"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/logout", methods=["POST"])
def logout():
    """Clear the session and redirect to auth page."""
    session.clear()
    return jsonify({"message": "Logged out."})


@app.route("/me")
@login_required
def current_user():
    """Return the currently logged-in user's info."""
    return jsonify({
        "name": session.get("user_name"),
        "email": session.get("user_email")
    })


# ──────────────────────────────────────────────
# Main page
# ──────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    """Render the single-page dashboard frontend."""
    return render_template("index.html", user_name=session.get("user_name", ""))


# ──────────────────────────────────────────────
# Resume routes
# ──────────────────────────────────────────────

@app.route("/upload-resume", methods=["POST"])
@login_required
def upload_resume():
    """
    Accept multiple PDF resumes + a job description.
    Extract text, compute TF-IDF cosine similarity, and return ranked results.
    """
    try:
        job_description = request.form.get("job_description", "")
        files = request.files.getlist("resumes")

        if not job_description.strip():
            return jsonify({"error": "Job description is required."}), 400
        if not files or files[0].filename == "":
            return jsonify({"error": "At least one resume PDF is required."}), 400

        cleaned_jd = clean_text(job_description)
        corpus = [cleaned_jd]       # index 0 = job description
        filenames = []

        for f in files:
            if not allowed_file(f.filename):
                return jsonify({"error": f"Invalid file type: {f.filename}. Only PDF allowed."}), 400

            safe_name = secure_filename(f.filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
            f.save(save_path)

            with open(save_path, "rb") as saved:
                raw_text = extract_text_from_pdf(saved)
            cleaned = clean_text(raw_text)
            corpus.append(cleaned)
            filenames.append(safe_name)

        # TF-IDF vectorisation + cosine similarity
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(corpus)
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        results = []
        for name, score in zip(filenames, similarities):
            results.append({
                "filename": name,
                "score": round(float(score) * 100, 2)
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        for rank, item in enumerate(results, start=1):
            item["rank"] = rank

        # ── Auto-extract phone + cert claims from each resume ──
        auto_wa_results = []   # candidates contacted via WhatsApp
        for r in results:
            safe = secure_filename(r["filename"])
            path = os.path.join(app.config["UPLOAD_FOLDER"], safe)
            if not os.path.exists(path):
                continue
            with open(path, "rb") as pf:
                raw = extract_text_from_pdf(pf)
            # Extract candidate name
            r["candidate_name"] = resume_matcher.extract_candidate_name(raw) or r["filename"].rsplit(".", 1)[0]
            # Extract phone
            phones = resume_matcher.extract_phone_numbers(raw)
            r["phone"] = phones[0] if phones else ""
            # Extract cert claims
            claims = resume_matcher.extract_cert_claims(raw)
            r["cert_claims"] = claims
            # Auto-send WhatsApp if phone found
            if r["phone"]:
                phone_clean = whatsapp_handler.normalize_phone(r["phone"])
                r["phone"] = phone_clean
                _register_candidate(phone_clean, r["filename"], claims)
                try:
                    wa_result = whatsapp_handler.send_certificate_request(
                        phone_clean, r["filename"], claims
                    )
                    if wa_result.get("success"):
                        r["wa_status"] = "sent"
                        worker.update_stage(phone_clean, "whatsapp_sent",
                                            f"WhatsApp sent to {r['filename']}. Waiting for reply...")
                        auto_wa_results.append({"candidate": r["filename"], "phone": phone_clean})
                    else:
                        r["wa_status"] = "failed"
                except Exception:
                    r["wa_status"] = "failed"
            else:
                r["wa_status"] = "no_phone"

        # Accumulate results across analyses (don't overwrite)
        all_results = session.get("results", [])
        all_results.extend(results)
        # Re-rank: verified first, then by score
        all_results.sort(key=lambda x: (
            0 if x.get("cert_status") == "verified" else 1,
            -x["score"]
        ))
        for rank, item in enumerate(all_results, start=1):
            item["rank"] = rank
        session["results"] = all_results
        session["total_resumes"] = session.get("total_resumes", 0) + len(results)

        return jsonify({
            "results": results,
            "all_results": all_results,
            "auto_whatsapp": auto_wa_results,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# Certificate routes
# ──────────────────────────────────────────────

@app.route("/verify-certificate", methods=["POST"])
@login_required
def verify_certificate():
    """Check if a certificate's SHA-256 hash exists on the blockchain AND
    matches the hash that was stored for this specific candidate."""
    try:
        file = request.files.get("certificate")
        candidate = request.form.get("candidate", "").strip()
        if not file or file.filename == "":
            return jsonify({"error": "Certificate file is required."}), 400
        if not candidate:
            return jsonify({"error": "Select a candidate first."}), 400

        file_bytes = file.read()
        cert_hash = sha256_hash(file_bytes)

        # 1. Check blockchain
        result = web3_connect.verify_certificate(cert_hash)
        result["hash"] = cert_hash
        result["candidate"] = candidate

        # 2. Cross-check: does this hash match what was stored for THIS candidate?
        stored_hashes = session.get("candidate_certs", {})
        stored_hash_for_candidate = stored_hashes.get(candidate)

        if result.get("status") == "Verified":
            if stored_hash_for_candidate and stored_hash_for_candidate == cert_hash:
                # Hash is on blockchain AND matches this candidate's stored cert
                session["total_certs"] = session.get("total_certs", 0) + 1
                verified = session.get("verified_candidates", {})
                verified[candidate] = cert_hash
                session["verified_candidates"] = verified
                results = session.get("results", [])
                for r in results:
                    if r["filename"] == candidate:
                        r["cert_status"] = "verified"
                        r["cert_hash"] = cert_hash
                session["results"] = results
            elif stored_hash_for_candidate:
                # Hash exists on blockchain but belongs to a DIFFERENT candidate
                result["status"] = "Mismatch"
                result["message"] = ("This certificate is on the blockchain but "
                                     "does NOT match the certificate stored for "
                                     "this candidate. It may belong to someone else.")
            else:
                # Hash exists on blockchain but nothing was stored for this candidate yet
                result["status"] = "Mismatch"
                result["message"] = ("This certificate hash exists on the blockchain, "
                                     "but no certificate was stored for this candidate. "
                                     "Store the candidate's certificate first.")

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/store-certificate", methods=["POST"])
@login_required
def store_certificate():
    """Store a certificate's SHA-256 hash on the blockchain and link it
    to the selected candidate."""
    try:
        file = request.files.get("certificate")
        candidate = request.form.get("candidate", "").strip()
        if not file or file.filename == "":
            return jsonify({"error": "Certificate file is required."}), 400
        if not candidate:
            return jsonify({"error": "Select a candidate first."}), 400

        file_bytes = file.read()
        cert_hash = sha256_hash(file_bytes)

        result = web3_connect.store_certificate(cert_hash)
        result["hash"] = cert_hash
        result["candidate"] = candidate

        if candidate and not result.get("error"):
            # Save candidate → hash mapping for cross-check during verify
            stored_hashes = session.get("candidate_certs", {})
            stored_hashes[candidate] = cert_hash
            session["candidate_certs"] = stored_hashes
            # Mark candidate as stored in results
            results = session.get("results", [])
            for r in results:
                if r["filename"] == candidate:
                    r["cert_status"] = r.get("cert_status", "stored")
                    r["cert_hash"] = cert_hash
            session["results"] = results

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/blockchain-status")
@login_required
def blockchain_status():
    """Return whether the Ganache blockchain node is reachable."""
    try:
        connected = web3_connect.check_connection()
        return jsonify({"connected": connected})
    except Exception:
        return jsonify({"connected": False})


@app.route("/dashboard-data")
@login_required
def dashboard_data():
    """Return persisted session data for the recruiter dashboard.
    Re-ranks with verified candidates first, then by score."""
    results = session.get("results", [])

    # Check pipeline status for each candidate and auto-update verification
    for r in results:
        phone = r.get("phone", "")
        if phone and r.get("cert_status") != "verified":
            status = worker.get_status(phone)
            if status.get("stage") == "complete":
                certs = status.get("certs", [])
                authentic = [c for c in certs if c.get("is_authentic")]
                if authentic:
                    r["cert_status"] = "verified"
                    r["trust_score"] = max(c.get("confidence_score", 0) for c in authentic)
                    session["total_certs"] = session.get("total_certs", 0) + 1

    # Re-rank: verified first, then by score
    results.sort(key=lambda x: (
        0 if x.get("cert_status") == "verified" else 1,
        -x.get("score", 0)
    ))
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank
    session["results"] = results

    return jsonify({
        "results": results,
        "total_resumes": session.get("total_resumes", 0),
        "total_certs": session.get("total_certs", 0)
    })


# ──────────────────────────────────────────────
# WhatsApp routes
# ──────────────────────────────────────────────

@app.route("/send-whatsapp", methods=["POST"])
@login_required
def send_whatsapp():
    """Send a WhatsApp certificate-request message to a candidate."""
    try:
        data = request.get_json()
        phone = data.get("phone", "").strip()
        candidate_name = data.get("candidate_name", "").strip()
        cert_list = data.get("cert_list", [])

        if not phone:
            return jsonify({"error": "Phone number is required."}), 400

        phone_clean = whatsapp_handler.normalize_phone(phone)
        result = whatsapp_handler.send_certificate_request(phone_clean, candidate_name, cert_list)

        if result.get("success"):
            # Track WhatsApp requests in session
            wa_requests = session.get("whatsapp_requests", {})
            wa_requests[phone_clean] = {
                "candidate_name": candidate_name,
                "cert_list": cert_list,
                "sent": True,
            }
            session["whatsapp_requests"] = wa_requests

            # Initialize status
            worker.update_stage(phone_clean, "whatsapp_sent",
                                f"WhatsApp sent to {candidate_name}. Waiting for reply...")

            return jsonify({
                "message": f"WhatsApp sent to {phone_clean}!",
                "phone": phone_clean,
                "message_sid": result.get("message_sid", ""),
            })
        else:
            return jsonify({"error": result.get("error", "Failed to send.")}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/shortlist-notify", methods=["POST"])
@login_required
def shortlist_notify():
    """Notify shortlisted candidates via WhatsApp."""
    try:
        data = request.get_json()
        candidates = data.get("candidates", [])
        if not candidates:
            return jsonify({"error": "No candidates provided."}), 400

        notified = 0
        errors = []
        for c in candidates:
            phone = c.get("phone", "").strip()
            name = c.get("realname", "").strip() or c.get("filename", "").strip()
            if phone:
                result = whatsapp_handler.send_shortlist_notification(phone, name)
                if result.get("success"):
                    notified += 1
                else:
                    errors.append(f"{name}: {result.get('error', 'Unknown error')}")
            else:
                errors.append(f"{name}: No phone number")

        return jsonify({
            "notified": notified,
            "total": len(candidates),
            "errors": errors
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    """
    Twilio WhatsApp webhook — called when a candidate replies.
    Must respond within 5 seconds → processing runs in background thread.
    """
    try:
        parsed = whatsapp_handler.parse_webhook(request.form.to_dict())
        phone = parsed["phone"]

        # Look up candidate name from shared registry (file-based, not session)
        candidate_info = _lookup_candidate(phone)
        candidate_name = candidate_info.get("candidate_name", "")

        if parsed["num_media"] > 0 and parsed["media"]:
            # Launch background pipeline
            worker.start_pipeline_thread(
                phone=phone,
                media_list=parsed["media"],
                candidate_name=candidate_name,
            )

        # Twilio requires a TwiML response
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Message>Got it! Processing your certificates now...</Message></Response>',
            200,
            {"Content-Type": "text/xml"},
        )

    except Exception:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response></Response>',
            200,
            {"Content-Type": "text/xml"},
        )


@app.route("/check-cert-status")
@login_required
def check_cert_status():
    """Poll endpoint — returns current pipeline status for a phone number."""
    phone = request.args.get("phone", "").strip()
    if not phone:
        return jsonify({"stage": "idle", "message": "No phone provided.", "certs": []})

    phone_clean = whatsapp_handler.normalize_phone(phone)
    status = worker.get_status(phone_clean)
    return jsonify(status)


# ──────────────────────────────────────────────
# Certificate verification pipeline routes
# ──────────────────────────────────────────────

@app.route("/extract-certs-from-resume", methods=["POST"])
@login_required
def extract_certs_from_resume():
    """Extract certification claims from a previously uploaded resume (file upload or filename)."""
    try:
        # Support both file upload and JSON filename reference
        file = request.files.get("resume")
        if file:
            text = extract_text_from_pdf(file)
        else:
            data = request.get_json() or {}
            filename = data.get("filename", "").strip()
            if not filename:
                return jsonify({"error": "Filename or file is required."}), 400
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(filename))
            if not os.path.exists(file_path):
                return jsonify({"error": "Resume file not found."}), 404
            with open(file_path, "rb") as f:
                text = extract_text_from_pdf(f)

        claims = resume_matcher.extract_cert_claims(text)
        phones = resume_matcher.extract_phone_numbers(text)

        return jsonify({"claims": claims, "phones": phones})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cross-check", methods=["POST"])
@login_required
def cross_check():
    """Cross-check resume claims against blockchain-verified certificates."""
    try:
        data = request.get_json()
        phone = data.get("phone", "").strip()
        filename = data.get("filename", "").strip()

        if not phone or not filename:
            return jsonify({"error": "Phone and filename are required."}), 400

        phone_clean = whatsapp_handler.normalize_phone(phone)

        # Read resume text
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(filename))
        resume_text = ""
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    pt = page.extract_text()
                    if pt:
                        resume_text += pt + " "

        # Get blockchain certs
        blockchain_certs = web3_connect.get_candidate_certificates(phone_clean)

        # Also check local cert_store.json fallback
        local_certs = _get_local_certs(phone_clean)
        all_certs = blockchain_certs + local_certs

        # Cross-check
        result = resume_matcher.cross_check_resume_vs_blockchain(resume_text, all_certs)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _get_local_certs(phone: str) -> list:
    """Read certs from local cert_store.json fallback."""
    import json
    store_file = os.path.join(BASE_DIR, "cert_store.json")
    if not os.path.exists(store_file):
        return []
    try:
        with open(store_file, "r") as f:
            store = json.load(f)
        return store.get(phone, [])
    except Exception:
        return []


# ──────────────────────────────────────────────
# Certificate Ledger routes
# ──────────────────────────────────────────────

@app.route("/ledger-data")
@login_required
def ledger_data():
    """Return all certificate records for the ledger tab."""
    try:
        import json as json_mod
        records = []

        # From status.json (pipeline-processed certs)
        status_file = os.path.join(BASE_DIR, "status.json")
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                all_status = json_mod.load(f)
            for phone, data in all_status.items():
                candidate_name = ""
                wa_reqs = session.get("whatsapp_requests", {})
                if phone in wa_reqs:
                    candidate_name = wa_reqs[phone].get("candidate_name", "")
                for cert in data.get("certs", []):
                    records.append({
                        "candidate": candidate_name or cert.get("candidate_name", phone),
                        "cert_title": cert.get("cert_title", "Unknown"),
                        "issuer": cert.get("issuer", "Unknown"),
                        "issue_date": cert.get("issue_date", ""),
                        "tx_hash": cert.get("tx_hash", ""),
                        "verified_at": cert.get("verified_at", ""),
                        "is_authentic": cert.get("is_authentic", False),
                        "confidence": cert.get("confidence_score", 0),
                        "file_hash": cert.get("file_hash", ""),
                        "stored_on_chain": cert.get("stored_on_chain", False),
                    })

        # From session-based manual certs
        for r in session.get("results", []):
            if r.get("cert_hash"):
                records.append({
                    "candidate": r.get("filename", ""),
                    "cert_title": "Manual Certificate",
                    "issuer": "Manual Upload",
                    "issue_date": "",
                    "tx_hash": "",
                    "verified_at": "",
                    "is_authentic": r.get("cert_status") == "verified",
                    "confidence": 100 if r.get("cert_status") == "verified" else 0,
                    "file_hash": r.get("cert_hash", ""),
                    "stored_on_chain": True,
                })

        return jsonify({"records": records})

    except Exception as e:
        return jsonify({"records": [], "error": str(e)})


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
