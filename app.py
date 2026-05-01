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
import time
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

VALID_ROLES = {"viewer", "recruiter", "hr_admin", "admin"}
REQUEST_TICKS = {}

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
    """Create users and resumes tables if they don't exist."""
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'recruiter',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_description TEXT,
            filename TEXT NOT NULL,
            candidate_name TEXT,
            phone TEXT,
            score REAL,
            tfidf_score REAL,
            semantic_score REAL,
            cert_claims TEXT,
            cert_status TEXT DEFAULT 'pending',
            trust_score REAL DEFAULT 0,
            wa_status TEXT,
            wa_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    _ensure_column(db, "users", "role", "TEXT DEFAULT 'recruiter'")
    _ensure_column(db, "resumes", "tfidf_score", "REAL")
    _ensure_column(db, "resumes", "semantic_score", "REAL")
    db.commit()
    db.close()


def _ensure_column(db_conn, table_name: str, col_name: str, col_def: str):
    """Run lightweight SQLite schema migration for missing columns."""
    cols = db_conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {c[1] for c in cols}
    if col_name not in existing:
        db_conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")


init_db()


def save_resume_analysis(user_id: int, job_description: str, filename: str, 
                         candidate_name: str, phone: str, score: float, 
                                                 cert_claims: list, wa_status: str = "", wa_error: str = "",
                                                 tfidf_score: float = 0.0, semantic_score: float = 0.0):
    """Save a single resume analysis to the database."""
    db = get_db()
    db.execute("""
        INSERT INTO resumes 
                (user_id, job_description, filename, candidate_name, phone, score, tfidf_score, semantic_score, cert_claims, wa_status, wa_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, job_description, filename, candidate_name, phone, score, 
                    tfidf_score, semantic_score, json_mod.dumps(cert_claims), wa_status, wa_error))
    db.commit()


def get_user_resumes(user_id: int):
    """Get all resume analyses for a user, ordered by creation date (newest first)."""
    db = get_db()
    rows = db.execute("""
        SELECT id, job_description, filename, candidate_name, phone, score, 
             tfidf_score, semantic_score, cert_claims, cert_status, trust_score, wa_status, wa_error, created_at
        FROM resumes
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,)).fetchall()
    
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "filename": row["filename"],
            "candidate_name": row["candidate_name"],
            "phone": row["phone"],
            "score": row["score"],
            "tfidf_score": row["tfidf_score"] if row["tfidf_score"] is not None else row["score"],
            "semantic_score": row["semantic_score"] if row["semantic_score"] is not None else row["score"],
            "cert_claims": json_mod.loads(row["cert_claims"]) if row["cert_claims"] else [],
            "cert_status": row["cert_status"],
            "trust_score": row["trust_score"],
            "wa_status": row["wa_status"],
            "wa_error": row["wa_error"],
            "created_at": row["created_at"],
            "job_description": row["job_description"]
        })
    return results


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


def roles_required(*allowed_roles):
    """Allow access only to users with one of the allowed roles."""
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth_page"))
            role = session.get("user_role", "recruiter")
            if role not in allowed_roles:
                return jsonify({"error": "Insufficient permissions for this action."}), 403
            return f(*args, **kwargs)
        return decorated
    return wrapper


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


def semantic_overlap_score(job_text: str, resume_text: str) -> float:
    """A lightweight semantic proxy using normalized token overlap."""
    jt = set(job_text.split())
    rt = set(resume_text.split())
    if not jt or not rt:
        return 0.0
    overlap = len(jt.intersection(rt)) / len(jt.union(rt))
    return round(overlap * 100, 2)


def skill_match_score(jd: str, resume: str) -> float:
    """
    Score resume based on matching tech skills against job description.
    Scoring: 90-100% for high overlap (≥90%), proportional scaling for partial matches.
    """
    known_skills = [
        # Languages
        "python", "java", "javascript", "typescript", "cpp", "c++", "c#", "csharp",
        "php", "ruby", "go", "rust", "kotlin", "swift", "scala", "r", "matlab",
        # Frontend
        "react", "vue", "angular", "html", "css", "webpack", "tailwind", "bootstrap",
        # Backend
        "node", "nodejs", "express", "django", "flask", "spring", "dotnet", ".net",
        "fastapi", "golang", "gin", "rails", "sinatra",
        # Databases
        "mongodb", "mysql", "postgresql", "oracle", "redis", "elasticsearch",
        "dynamodb", "cassandra", "firebase", "sql", "sqlite", "mariadb",
        # DevOps & Cloud
        "docker", "kubernetes", "aws", "azure", "gcp", "jenkins", "gitlab", "github",
        "terraform", "ansible", "ci/cd", "nginx", "apache", "linux",
        # Blockchain & Web3
        "blockchain", "ethereum", "solidity", "web3", "smart contract", "hardhat",
        "truffle", "ganache", "web3py",
        # Data & AI
        "machine learning", "ml", "ai", "tensorflow", "pytorch", "sklearn", "pandas",
        "numpy", "spark", "hadoop", "etl", "analytics", "data science",
        # Other Tools
        "git", "jira", "agile", "scrum", "rest", "api", "grpc", "graphql",
        "junit", "pytest", "jest", "mocha", "rspec", "testing", "tdd",
        "distributed systems", "microservices", "nosql", "orm", "deployment"
    ]
    
    jd_lower = jd.lower()
    resume_lower = resume.lower()
    
    jd_skills = [s for s in known_skills if s in jd_lower]
    resume_skills = [s for s in known_skills if s in resume_lower]
    
    if not jd_skills:
        return 50.0  # Neutral if no skills found in JD
    
    overlap = len(set(jd_skills) & set(resume_skills))
    overlap_ratio = overlap / len(jd_skills)
    
    # Scoring: 90-100% for high overlap (≥90%), proportional 0-90% for partial matches
    if overlap_ratio >= 0.9:
        # High overlap: scale 90-100
        score = 90 + (overlap_ratio - 0.9) * 100
    else:
        # Partial overlap: scale 0-90 proportionally
        score = overlap_ratio * 90
    
    return round(min(100, score), 2)


def log_audit(action: str, target: str = "", details: dict | None = None):
    """Write user-scoped action logs for traceability and review."""
    user_id = session.get("user_id")
    if not user_id:
        return
    db = get_db()
    db.execute(
        "INSERT INTO audit_logs (user_id, action, target, details) VALUES (?, ?, ?, ?)",
        (user_id, action, target, json_mod.dumps(details or {}))
    )
    db.commit()


@app.before_request
def lightweight_rate_guard():
    """Basic per-user/per-IP request throttling for write endpoints."""
    if request.method in {"GET", "OPTIONS", "HEAD"}:
        return None
    key = f"{session.get('user_id', 'anon')}:{request.remote_addr or 'local'}"
    now = time.time()
    bucket = REQUEST_TICKS.get(key, [])
    bucket = [t for t in bucket if now - t < 60]
    if len(bucket) >= 180:
        return jsonify({"error": "Rate limit reached. Try again shortly."}), 429
    bucket.append(now)
    REQUEST_TICKS[key] = bucket
    return None


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
        role = data.get("role", "recruiter")

        if not fullname or not email or not password:
            return jsonify({"error": "All fields are required."}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters."}), 400
        if role not in VALID_ROLES:
            role = "recruiter"

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "An account with this email already exists."}), 409

        hashed = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (fullname, email, hashed, role)
        )
        db.commit()

        # Auto-login after registration
        user = db.execute("SELECT id, fullname, email, role FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["fullname"]
        session["user_email"] = user["email"]
        session["user_role"] = user["role"] or "recruiter"

        log_audit("user_registered", user["email"], {"role": session["user_role"]})

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
        session["user_role"] = user["role"] or "recruiter"

        log_audit("user_login", user["email"], {"role": session["user_role"]})

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
        "email": session.get("user_email"),
        "role": session.get("user_role", "recruiter")
    })


# ──────────────────────────────────────────────
# Main page
# ──────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    """Render the single-page dashboard frontend."""
    return render_template(
        "index.html",
        user_name=session.get("user_name", ""),
        user_role=session.get("user_role", "recruiter")
    )


# ──────────────────────────────────────────────
# Resume routes
# ──────────────────────────────────────────────

@app.route("/upload-resume", methods=["POST"])
@login_required
@roles_required("recruiter", "hr_admin", "admin")
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
        cleaned_resumes = []

        for f in files:
            if not allowed_file(f.filename):
                return jsonify({"error": f"Invalid file type: {f.filename}. Only PDF allowed."}), 400

            safe_name = secure_filename(f.filename or "resume.pdf")
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
            f.save(save_path)

            with open(save_path, "rb") as saved:
                raw_text = extract_text_from_pdf(saved)
            cleaned = clean_text(raw_text)
            corpus.append(cleaned)
            filenames.append(safe_name)
            cleaned_resumes.append(cleaned)

        # TF-IDF vectorisation + cosine similarity
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(corpus)
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()  # type: ignore[index]

        results = []
        for idx, (name, score) in enumerate(zip(filenames, similarities)):
            tfidf_score = round(float(score) * 100, 2)
            semantic_score = semantic_overlap_score(cleaned_jd, cleaned_resumes[idx])
            skill_score = skill_match_score(cleaned_jd, cleaned_resumes[idx])
            # Weighted hybrid: 30% TF-IDF, 30% semantic, 40% skill matching
            hybrid_score = round((0.3 * tfidf_score) + (0.3 * semantic_score) + (0.4 * skill_score), 2)
            results.append({
                "filename": name,
                "score": hybrid_score,
                "tfidf_score": tfidf_score,
                "semantic_score": semantic_score,
                "skill_score": skill_score
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
                _register_candidate(phone_clean, r["candidate_name"], claims)
                try:
                    wa_result = whatsapp_handler.send_certificate_request(
                        phone_clean, r["candidate_name"], claims
                    )
                    if wa_result.get("success"):
                        r["wa_status"] = "sent"
                        worker.update_stage(phone_clean, "whatsapp_sent",
                                            f"WhatsApp sent to {r['filename']}. Waiting for reply...")
                        auto_wa_results.append({"candidate": r["filename"], "phone": phone_clean})
                    else:
                        r["wa_status"] = "failed"
                        r["wa_error"] = wa_result.get("error", "Unknown WhatsApp send error")
                except Exception:
                    r["wa_status"] = "failed"
                    r["wa_error"] = "Unexpected WhatsApp error"
            else:
                r["wa_status"] = "no_phone"

        # Save each analysis to database for persistence
        user_id = session.get("user_id")
        if user_id:
            for r in results:
                save_resume_analysis(
                    user_id=user_id,
                    job_description=job_description,
                    filename=r["filename"],
                    candidate_name=r.get("candidate_name", ""),
                    phone=r.get("phone", ""),
                    score=r.get("score", 0),
                    tfidf_score=r.get("tfidf_score", 0),
                    semantic_score=r.get("semantic_score", 0),
                    cert_claims=r.get("cert_claims", []),
                    wa_status=r.get("wa_status", ""),
                    wa_error=r.get("wa_error", "")
                )

        log_audit("resume_batch_analyzed", "resume_upload", {
            "count": len(results),
            "auto_whatsapp": len(auto_wa_results)
        })

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
@roles_required("recruiter", "hr_admin", "admin")
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
@roles_required("recruiter", "hr_admin", "admin")
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
    """Return persisted dashboard data for the recruiter.
    Loads from session first, then from database if session is empty.
    Re-ranks with verified candidates first, then by score."""
    
    user_id = session.get("user_id")
    results = session.get("results", [])
    
    # If session is empty, load from database (first login or new session)
    if not results and user_id:
        results = get_user_resumes(user_id)
        session["results"] = results
        # Restore total_resumes and total_certs from database
        session["total_resumes"] = len(results)
        verified_count = len([r for r in results if r.get("cert_status") == "verified"])
        session["total_certs"] = verified_count

    # Check pipeline status for each candidate and auto-update verification
    for r in results:
        phone = r.get("phone", "")
        if phone:
            status = worker.get_status(phone)
            if status.get("stage") == "complete":
                certs = status.get("certs", [])
                authentic = [c for c in certs if c.get("is_authentic")]
                if authentic:
                    r["cert_status"] = "verified"
                    r["trust_score"] = max(c.get("confidence_score", 0) for c in authentic)
                    # Update database with verified status
                    if r.get("id"):
                        db = get_db()
                        db.execute(
                            "UPDATE resumes SET cert_status = ?, trust_score = ? WHERE id = ?",
                            ("verified", r["trust_score"], r["id"])
                        )
                        db.commit()
                elif certs:
                    r["cert_status"] = "rejected"
                    r["trust_score"] = max(c.get("confidence_score", 0) for c in certs)
                    # Update database with rejected status
                    if r.get("id"):
                        db = get_db()
                        db.execute(
                            "UPDATE resumes SET cert_status = ?, trust_score = ? WHERE id = ?",
                            ("rejected", r["trust_score"], r["id"])
                        )
                        db.commit()

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

@app.route("/analysis-history")
@login_required
def analysis_history():
    """Get all resume analyses for the logged-in user."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401
        resumes = get_user_resumes(user_id)
        return jsonify({
            "resumes": resumes,
            "total": len(resumes)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/delete-resume/<int:resume_id>", methods=["DELETE"])
@login_required
@roles_required("hr_admin", "admin")
def delete_resume(resume_id):
    """Delete a single resume by ID (if it belongs to the logged-in user)."""
    try:
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"error": "User not authenticated"}), 401
        db = get_db()
        
        # Verify ownership (only delete if this resume belongs to current user)
        resume = db.execute(
            "SELECT user_id FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        
        if not resume:
            return jsonify({"error": "Resume not found"}), 404
        if resume["user_id"] != user_id:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Delete the resume
        db.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        db.commit()
        
        # Refresh session results
        session["results"] = get_user_resumes(user_id)
        log_audit("resume_deleted", str(resume_id), {"deleted": 1})
        
        return jsonify({"message": "Resume deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/delete-resumes/rejected", methods=["DELETE"])
@login_required
@roles_required("hr_admin", "admin")
def delete_rejected_resumes():
    """Delete all resumes with rejected certificate status for the logged-in user."""
    try:
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"error": "User not authenticated"}), 401
        db = get_db()
        
        # Delete all rejected resumes for this user
        db.execute(
            "DELETE FROM resumes WHERE user_id = ? AND cert_status = ?",
            (user_id, "rejected")
        )
        db.commit()
        
        deleted_count = db.total_changes
        
        # Refresh session results
        session["results"] = get_user_resumes(user_id)
        log_audit("resume_deleted_bulk_rejected", "rejected", {"deleted": deleted_count})
        
        return jsonify({"message": f"Deleted {deleted_count} rejected resume(s)"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/delete-resumes/all", methods=["DELETE"])
@login_required
@roles_required("hr_admin", "admin")
def delete_all_resumes():
    """Delete ALL resumes for the logged-in user (with confirmation)."""
    try:
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"error": "User not authenticated"}), 401
        
        # Optional: check for confirmation token to prevent accidental deletion
        data = request.get_json() or {}
        confirm = data.get("confirm", False)
        
        if not confirm:
            return jsonify({"error": "Confirmation required. Send confirm=true"}), 400
        
        db = get_db()
        
        # Delete all resumes for this user
        db.execute("DELETE FROM resumes WHERE user_id = ?", (user_id,))
        db.commit()
        
        deleted_count = db.total_changes
        
        # Clear session results
        session["results"] = []
        session["total_resumes"] = 0
        session["total_certs"] = 0
        log_audit("resume_deleted_all", "all", {"deleted": deleted_count})
        
        return jsonify({"message": f"Deleted all {deleted_count} resume(s)"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# WhatsApp routes
# ──────────────────────────────────────────────

@app.route("/send-whatsapp", methods=["POST"])
@login_required
@roles_required("recruiter", "hr_admin", "admin")
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

            log_audit("whatsapp_sent", phone_clean, {"candidate": candidate_name})

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
@roles_required("recruiter", "hr_admin", "admin")
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

        log_audit("shortlist_notified", "batch", {"notified": notified, "total": len(candidates)})
        return jsonify({
            "notified": notified,
            "total": len(candidates),
            "errors": errors
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/candidate-action", methods=["POST"])
@login_required
@roles_required("recruiter", "hr_admin", "admin")
def candidate_action():
    """Track recruiter actions for shortlisted candidates."""
    try:
        data = request.get_json() or {}
        action = data.get("action", "").strip().lower()
        candidates = data.get("candidates", [])
        if action not in {"invite", "request_docs", "hold", "reject"}:
            return jsonify({"error": "Invalid action"}), 400
        if not candidates:
            return jsonify({"error": "No candidates provided."}), 400

        log_audit("candidate_action", action, {
            "action": action,
            "count": len(candidates),
            "candidates": candidates[:25]
        })
        return jsonify({"message": "Action logged", "action": action, "count": len(candidates)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/audit-summary")
@login_required
def audit_summary():
    """Return lightweight audit summary and latest activity feed for UI panels."""
    try:
        user_id = session.get("user_id")
        db = get_db()
        rows = db.execute(
            """
            SELECT action, target, details, created_at
            FROM audit_logs
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 25
            """,
            (user_id,)
        ).fetchall()
        summary = {}
        activity = []
        for r in rows:
            summary[r["action"]] = summary.get(r["action"], 0) + 1
            activity.append({
                "action": r["action"],
                "target": r["target"],
                "details": json_mod.loads(r["details"] or "{}"),
                "created_at": r["created_at"]
            })
        return jsonify({"summary": summary, "activity": activity})
    except Exception as e:
        return jsonify({"summary": {}, "activity": [], "error": str(e)})


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
                cert_claims=candidate_info.get("cert_claims", []),
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

@app.route("/test-whatsapp")
def test_whatsapp():
    result = whatsapp_handler.send_shortlist_notification(
        "+917411052683",
        "Test User"
    )
    return jsonify(result)
# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
