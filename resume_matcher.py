"""
resume_matcher.py — Cross-check resume certification claims against
blockchain-verified certificates using fuzzy matching.
Also extracts phone numbers from resume text.
"""

import re

try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


# ──────────────────────────────────────────────
# Extract phone numbers from resume text
# ──────────────────────────────────────────────

PHONE_PATTERNS = [
    r"(?:\+91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}",          # Indian: +91 98765 43210
    r"(?:\+91[\s\-]?)?\d{5}[\s\-]?\d{5}",                # Indian: 98765 43210
    r"(?:\+1[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}", # US: +1 (555) 123-4567
    r"(?:\+44[\s\-]?)?\d{4}[\s\-]?\d{6}",                # UK: +44 7911 123456
    r"\+\d{1,3}[\s\-]?\d{6,12}",                         # Generic intl format
]


def extract_phone_numbers(resume_text: str) -> list:
    """Extract phone numbers from resume text. Returns list of cleaned numbers."""
    if not resume_text:
        return []
    phones = []
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, resume_text)
        for m in matches:
            digits = re.sub(r"[^\d+]", "", m)
            if len(digits) >= 10 and digits not in phones:
                phones.append(digits)
    return phones[:3]  # Cap at 3 phone numbers per resume


def extract_candidate_name(resume_text: str) -> str:
    """
    Extract candidate's name from resume text.
    Handles multi-column PDFs where the name may appear late in extracted text.
    """
    if not resume_text:
        return ""

    lines = resume_text.split("\n")
    stripped = [(i, l.strip()) for i, l in enumerate(lines) if l.strip()]

    # Strategy 1: Look for explicit name labels like "Name: John Doe" or "T CHAITRA" near "Personal"
    name_label = re.search(
        r"(?:name|candidate)\s*[:\-–]\s*([A-Za-z][A-Za-z .\-']{2,30})",
        resume_text, re.IGNORECASE
    )
    if name_label:
        return name_label.group(1).strip().title()

    # Junk words — anything that's clearly not a person's name
    junk = {
        "blockchain", "storage", "python", "java", "react", "node",
        "developer", "engineer", "manager", "analyst", "designer",
        "software", "data", "cloud", "machine", "learning", "web",
        "full", "stack", "frontend", "backend", "devops", "mobile",
        "android", "ios", "database", "network", "security", "system",
        "artificial", "intelligence", "deep", "science", "intern",
        "senior", "junior", "lead", "associate", "professional",
        "technology", "technologies", "solutions", "services", "digital",
        "profile", "summary", "experience", "education", "skills",
        "projects", "contact", "personal", "details", "objective",
        "certifications", "certificates", "achievements", "technical",
        "programming", "languages", "tools", "frameworks", "interests",
        "hobbies", "references", "declaration", "curriculum", "vitae",
        "resume", "portfolio", "cbse", "puc", "cse", "ece", "eee",
        "ise", "gpa", "cgpa", "ssc", "hsc", "btech", "mtech",
        "be", "bsc", "msc", "bca", "mca", "bba", "mba", "bcom", "mcom",
    }

    def is_name_line(text):
        """Check if a line looks like a person's name."""
        if len(text) < 3 or len(text) > 35:
            return False
        # Must be mostly alphabetic + spaces
        alpha_ratio = sum(c.isalpha() or c == ' ' for c in text) / len(text)
        if alpha_ratio < 0.85:
            return False
        words = text.split()
        if len(words) < 1 or len(words) > 4:
            return False
        # Skip if ANY word is a known junk word
        for w in words:
            if w.lower().rstrip('.') in junk:
                return False
        return True

    # Strategy 2: Find ALL-CAPS name with 2+ words (very reliable for names)
    for _, text in stripped:
        alpha = re.sub(r"[^A-Za-z ]", "", text).strip()
        if not alpha or alpha != alpha.upper():
            continue
        words = alpha.split()
        if len(words) >= 2 and len(words) <= 4 and is_name_line(alpha):
            return alpha.title()

    # Strategy 3: Line right after/near "Personal details" or "Name" section
    for idx, (i, text) in enumerate(stripped):
        if re.search(r"personal\s*(details|info)", text, re.IGNORECASE):
            # Check the next few lines for a name
            for _, next_text in stripped[idx+1:idx+4]:
                if is_name_line(next_text):
                    return next_text.title()

    # Strategy 4: First plausible name from the top
    for _, text in stripped[:12]:
        if is_name_line(text):
            return text.title()

    return ""


# ──────────────────────────────────────────────
# Extract certification claims from resume text
# ──────────────────────────────────────────────

# Common certification keywords / patterns
CERT_KEYWORDS = [
    "certified", "certification", "certificate", "credential",
    "diploma", "degree", "license", "licensed", "accredited",
    "aws certified", "google certified", "microsoft certified",
    "pmp", "scrum master", "comptia", "cisco", "ccna", "ccnp",
    "ceh", "cissp", "itil", "six sigma",
]

CERT_PATTERNS = [
    # "AWS Certified Developer - Associate"
    r"((?:aws|google|microsoft|oracle|cisco|comptia|pmi)\s+certified?\s+[\w\s\-–]{3,40})",
    # "Certificate in Machine Learning"
    r"(certificate\s+(?:in|of|for)\s+[\w\s\-–]{3,40})",
    # "Certified Kubernetes Administrator"
    r"(certified\s+[\w\s\-–]{3,30}(?:administrator|developer|engineer|analyst|professional|architect|specialist|practitioner|associate))",
    # "PMP Certification"  /  "CCNA Certification"
    r"((?:pmp|ccna|ccnp|ceh|cissp|itil|comptia\s+\w+)\s*(?:certification|certified)?)",
    # "B.Tech in Computer Science" / "M.Sc in Data Science" (short degree lines only)
    r"((?:b\.?\s*(?:tech|e|sc|a|com)|m\.?\s*(?:tech|e|sc|a|com|ba|ca)|ph\.?d)\.?\s+(?:in|of)\s+[\w\s]{3,30})",
]


def extract_cert_claims(resume_text: str) -> list:
    """
    Extract certification / degree claims from resume text.
    Returns a list of unique claim strings.
    """
    if not resume_text:
        return []

    claims = set()

    for pattern in CERT_PATTERNS:
        matches = re.findall(pattern, resume_text, re.IGNORECASE)
        for m in matches:
            clean = m.strip().rstrip(".,;:")
            if 5 < len(clean) < 120:
                claims.add(clean)

    # Also look for lines that contain certification keywords (short lines only)
    lines = resume_text.split("\n")
    for line in lines:
        line_s = line.strip()
        line_l = line_s.lower()
        for kw in CERT_KEYWORDS:
            if kw in line_l and 10 < len(line_s) < 60:
                claims.add(line_s.rstrip(".,;:"))
                break

    return list(claims)[:8]  # Cap at 8 claims


# ──────────────────────────────────────────────
# Fuzzy match claim vs blockchain certificate
# ──────────────────────────────────────────────

def _fuzzy_score(claim: str, cert_title: str) -> int:
    """Return a fuzzy match score 0-100 between a claim and a cert title."""
    if FUZZY_AVAILABLE:
        return max(
            fuzz.token_sort_ratio(claim.lower(), cert_title.lower()),
            fuzz.partial_ratio(claim.lower(), cert_title.lower()),
        )
    # Simple fallback: word overlap ratio
    words_a = set(claim.lower().split())
    words_b = set(cert_title.lower().split())
    if not words_a or not words_b:
        return 0
    overlap = len(words_a & words_b)
    return int((overlap / max(len(words_a), len(words_b))) * 100)


# ──────────────────────────────────────────────
# Cross-check resume vs blockchain certs
# ──────────────────────────────────────────────

def cross_check_resume_vs_blockchain(resume_text: str, blockchain_certs: list) -> dict:
    """
    Compare resume certification claims against blockchain-verified certs.

    Args:
        resume_text: Raw text extracted from the candidate's resume.
        blockchain_certs: List of dicts from blockchain, each with at least
                         'cert_title', 'issuer', 'is_authentic', 'file_hash'.

    Returns:
        {
            "resume_claims": [...],
            "blockchain_verified": [...],
            "matches": [
                {"claim": str, "blockchain_cert": dict, "match_score": int, "status": str}
            ],
            "unverified_claims": [...],
            "trust_score": 0-100
        }
    """
    claims = extract_cert_claims(resume_text)

    result = {
        "resume_claims": claims,
        "blockchain_verified": blockchain_certs,
        "matches": [],
        "unverified_claims": [],
        "trust_score": 0,
    }

    if not claims:
        result["trust_score"] = 50  # Neutral if no claims found
        return result

    matched_claim_indices = set()

    for claim in claims:
        best_score = 0
        best_cert = None

        for cert in blockchain_certs:
            title = cert.get("cert_title", "")
            issuer = cert.get("issuer", "")
            compare_text = f"{title} {issuer}"
            score = _fuzzy_score(claim, compare_text)
            if score > best_score:
                best_score = score
                best_cert = cert

        if best_score >= 80:
            status = "MATCH"
        elif best_score >= 50:
            status = "PARTIAL"
        else:
            status = "NOT_FOUND"

        match_entry = {
            "claim": claim,
            "blockchain_cert": best_cert if best_score >= 50 else None,
            "match_score": best_score,
            "status": status,
        }
        result["matches"].append(match_entry)

        if status == "NOT_FOUND":
            result["unverified_claims"].append(claim)

    # Trust score: weighted average of match quality
    if result["matches"]:
        total_score = sum(m["match_score"] for m in result["matches"] if m["status"] != "NOT_FOUND")
        matched_count = sum(1 for m in result["matches"] if m["status"] != "NOT_FOUND")
        if matched_count > 0:
            avg_match = total_score / matched_count
            coverage = matched_count / len(claims)
            result["trust_score"] = min(100, int(avg_match * coverage))
        else:
            result["trust_score"] = 0
    else:
        result["trust_score"] = 0

    return result
