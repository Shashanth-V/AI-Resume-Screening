"""
app.py — Flask backend for AI Resume Screening with Blockchain Certificate Verification.
Provides authentication (register / login / logout), resume analysis
(TF-IDF + cosine similarity), and certificate storage & verification
via a blockchain smart contract (Web3 / Ganache).
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

import nltk
# Auto-download NLTK stopwords if not present
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)

from nltk.corpus import stopwords

# Blockchain helper
from blockchain import web3_connect

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

        # Accumulate results across analyses (don't overwrite)
        all_results = session.get("results", [])
        all_results.extend(results)
        # Re-rank the entire cumulative list by score
        all_results.sort(key=lambda x: x["score"], reverse=True)
        for rank, item in enumerate(all_results, start=1):
            item["rank"] = rank
        session["results"] = all_results
        session["total_resumes"] = session.get("total_resumes", 0) + len(results)

        return jsonify({"results": results, "all_results": all_results})

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
    """Return persisted session data for the recruiter dashboard."""
    return jsonify({
        "results": session.get("results", []),
        "total_resumes": session.get("total_resumes", 0),
        "total_certs": session.get("total_certs", 0)
    })


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
