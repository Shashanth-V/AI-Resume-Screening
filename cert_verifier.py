"""
cert_verifier.py — Certificate authenticity verification for RecruitAI.
1. OCR / text extraction from certificates (images & PDFs)
2. Metadata extraction (issuer, title, credential ID, candidate name, date)
3. Issuer verification against public endpoints
"""

import os
import re
import hashlib
import requests as http_requests
from datetime import datetime

# Optional imports — degrade gracefully
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# Known legitimate institutions (partial list for NLP fallback)
KNOWN_INSTITUTIONS = [
    "coursera", "google", "aws", "amazon", "microsoft", "udemy",
    "linkedin learning", "edx", "mit", "stanford", "harvard", "ibm",
    "meta", "oracle", "cisco", "comptia", "pmi", "salesforce",
    "hubspot", "johns hopkins", "university of michigan", "duke",
    "university of london", "georgia tech", "upenn", "yale",
    "columbia", "caltech", "reva university",
]

# Verification URL patterns per issuer
ISSUER_VERIFY_URLS = {
    "coursera": "https://www.coursera.org/account/accomplishments/verify/{cred_id}",
    "linkedin": "https://www.linkedin.com/learning/certificates/{cred_id}",
    "aws": "https://aws.amazon.com/verification",
    "google": "https://www.credly.com/badges/{cred_id}",
    "udemy": "https://www.udemy.com/certificate/{cred_id}/",
    "credly": "https://www.credly.com/badges/{cred_id}",
}

REQUEST_TIMEOUT = 5


# ──────────────────────────────────────────────
# Text extraction
# ──────────────────────────────────────────────

def extract_text_from_image(file_path: str) -> str:
    """Extract text from an image certificate using OCR."""
    if not OCR_AVAILABLE or not PIL_AVAILABLE:
        return ""
    try:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception:
        return ""


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF certificate."""
    if not PDF_AVAILABLE:
        return ""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
        return text.strip()
    except Exception:
        return ""


def extract_text(file_path: str) -> str:
    """Extract text from a certificate file (PDF or image).
    Falls back from OCR to PDF text extraction."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        if not text:
            text = extract_text_from_image(file_path)
        return text
    # Image formats
    text = extract_text_from_image(file_path)
    if not text and ext == ".pdf":
        text = extract_text_from_pdf(file_path)
    return text


# ──────────────────────────────────────────────
# Metadata extraction via regex/NLP
# ──────────────────────────────────────────────

def extract_metadata(text: str) -> dict:
    """
    Extract certificate metadata from OCR/PDF text.
    Returns dict with: issuer, candidate_name, cert_title, issue_date, credential_id.
    """
    meta = {
        "issuer": "",
        "candidate_name": "",
        "cert_title": "",
        "issue_date": "",
        "credential_id": "",
        "raw_text": text[:500],
    }

    if not text:
        return meta

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # ── Credential / Certificate ID ──
    cred_patterns = [
        r"(?:credential|certificate|cert|badge)\s*(?:id|no|number|#)[:\s]*([A-Za-z0-9\-_]{4,})",
        r"(?:verify|verification)\s*(?:at|url|link)?[:\s]*https?://\S+/([A-Za-z0-9\-_]{6,})",
        r"ID[:\s]+([A-Z0-9\-]{6,})",
    ]
    for pat in cred_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            meta["credential_id"] = m.group(1).strip()
            break

    # ── Issue date ──
    date_patterns = [
        r"(?:issued?|date|completed?|awarded?)\s*(?:on|:)?\s*(\w+\s+\d{1,2},?\s+\d{4})",
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(\w+\s+\d{4})",
    ]
    for pat in date_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            meta["issue_date"] = m.group(1).strip()
            break

    # ── Issuer detection ──
    text_lower = text.lower()
    for inst in KNOWN_INSTITUTIONS:
        if inst in text_lower:
            meta["issuer"] = inst.title()
            break

    if not meta["issuer"]:
        issued_pat = r"(?:issued\s+by|authorized\s+by|from|by)\s*[:\s]*([A-Za-z\s&.]+)"
        m = re.search(issued_pat, text, re.IGNORECASE)
        if m:
            meta["issuer"] = m.group(1).strip()[:60]

    # ── Certificate title ──
    title_patterns = [
        r"(?:certificate\s+(?:of|in|for)\s+)(.+)",
        r"(?:has\s+successfully\s+completed\s+)(.+)",
        r"(?:completed?\s+the\s+)(.+?)(?:\s+course|\s+program|\s+certification)",
    ]
    for pat in title_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            meta["cert_title"] = m.group(1).strip()[:100]
            break

    if not meta["cert_title"] and len(lines) >= 2:
        for line in lines[:5]:
            if 10 < len(line) < 100 and "certificate" not in line.lower():
                meta["cert_title"] = line
                break

    # ── Candidate name ──
    name_patterns = [
        r"(?:this\s+is\s+to\s+certify\s+that|awarded\s+to|presented\s+to|granted\s+to)\s+([A-Z][a-zA-Z\s.]+)",
        r"(?:name)[:\s]+([A-Z][a-zA-Z\s.]+)",
    ]
    for pat in name_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 3 <= len(candidate) <= 50:
                meta["candidate_name"] = candidate
                break

    return meta


# ──────────────────────────────────────────────
# Issuer verification
# ──────────────────────────────────────────────

def _check_url(url: str) -> bool:
    """Hit a URL and check if it returns a valid (non-error) page."""
    try:
        resp = http_requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code == 200:
            body = resp.text.lower()
            if "not found" in body or "invalid" in body or "error" in body or "expired" in body:
                return False
            return True
    except Exception:
        pass
    return False


def _check_coursera(cred_id: str) -> bool:
    url = ISSUER_VERIFY_URLS["coursera"].format(cred_id=cred_id)
    return _check_url(url)


def _check_linkedin(cred_id: str) -> bool:
    url = ISSUER_VERIFY_URLS["linkedin"].format(cred_id=cred_id)
    return _check_url(url)


def _check_udemy(cred_id: str) -> bool:
    url = ISSUER_VERIFY_URLS["udemy"].format(cred_id=cred_id)
    return _check_url(url)


def _check_credly(cred_id: str) -> bool:
    url = ISSUER_VERIFY_URLS["credly"].format(cred_id=cred_id)
    return _check_url(url)


def _check_generic_verification_url(text: str) -> bool:
    """Look for a verification URL in the certificate text and check it."""
    url_match = re.search(r"(https?://\S+verif\S+)", text, re.IGNORECASE)
    if not url_match:
        url_match = re.search(r"(https?://\S+badge\S+)", text, re.IGNORECASE)
    if url_match:
        return _check_url(url_match.group(1))
    return False


def _institution_known(issuer: str) -> bool:
    """Check if the issuer is in the known-institutions list."""
    if not issuer:
        return False
    issuer_l = issuer.lower()
    return any(inst in issuer_l for inst in KNOWN_INSTITUTIONS)


def verify_with_issuer(cert_metadata: dict) -> dict:
    """
    Verify certificate authenticity against public records.
    Returns dict with: is_authentic, confidence_score, verification_source.
    """
    result = {
        "is_authentic": False,
        "confidence_score": 0,
        "verification_source": "none",
        "checks_passed": [],
    }

    cred_id = cert_metadata.get("credential_id", "")
    issuer = cert_metadata.get("issuer", "").lower()
    raw_text = cert_metadata.get("raw_text", "")
    checks_run = 0
    checks_passed = 0

    # Check 1: Issuer-specific verification
    if cred_id:
        checks_run += 1
        verified = False
        if "coursera" in issuer:
            verified = _check_coursera(cred_id)
            if verified:
                result["verification_source"] = "coursera_api"
        elif "linkedin" in issuer:
            verified = _check_linkedin(cred_id)
            if verified:
                result["verification_source"] = "linkedin_api"
        elif "udemy" in issuer:
            verified = _check_udemy(cred_id)
            if verified:
                result["verification_source"] = "udemy_api"
        else:
            verified = _check_credly(cred_id)
            if verified:
                result["verification_source"] = "credly_api"

        if verified:
            checks_passed += 1
            result["checks_passed"].append("issuer_api")

    # Check 2: Generic verification URL in text
    checks_run += 1
    if _check_generic_verification_url(raw_text):
        checks_passed += 1
        result["checks_passed"].append("verification_url")
        if not result["verification_source"] or result["verification_source"] == "none":
            result["verification_source"] = "verification_url"

    # Check 3: Known institution check
    checks_run += 1
    if _institution_known(cert_metadata.get("issuer", "")):
        checks_passed += 1
        result["checks_passed"].append("known_institution")
        if result["verification_source"] == "none":
            result["verification_source"] = "known_institution"

    # Check 4: Has credential ID at all
    if cred_id:
        checks_run += 1
        checks_passed += 1
        result["checks_passed"].append("has_credential_id")

    # Compute confidence (0-100)
    if checks_run > 0:
        base = (checks_passed / checks_run) * 100
        result["confidence_score"] = min(100, int(base))
    else:
        result["confidence_score"] = 0

    # Authentic if ANY meaningful check passed
    result["is_authentic"] = checks_passed > 0

    return result


# ──────────────────────────────────────────────
# Full pipeline: file → metadata → verify → result
# ──────────────────────────────────────────────

def verify_certificate_file(file_path: str) -> dict:
    """
    Complete verification pipeline for a single certificate file.
    1. Extract text (OCR / PDF)
    2. Parse metadata
    3. Verify with issuer
    4. Compute file hash
    Returns complete result dict.
    """
    # Extract text
    text = extract_text(file_path)

    # Parse metadata
    metadata = extract_metadata(text)

    # Verify
    verification = verify_with_issuer(metadata)

    # File hash
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
    except Exception:
        file_hash = ""

    return {
        "file_path": file_path,
        "file_hash": file_hash,
        "issuer": metadata.get("issuer", "Unknown"),
        "candidate_name": metadata.get("candidate_name", ""),
        "cert_title": metadata.get("cert_title", "Unknown Certificate"),
        "issue_date": metadata.get("issue_date", ""),
        "credential_id": metadata.get("credential_id", ""),
        "is_authentic": verification["is_authentic"],
        "confidence_score": verification["confidence_score"],
        "verification_source": verification["verification_source"],
        "checks_passed": verification["checks_passed"],
        "extracted_text": text[:300],
    }
