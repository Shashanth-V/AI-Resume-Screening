"""
worker.py — Background certificate processing pipeline for RecruitAI.
Runs in a separate thread so the Twilio webhook can immediately ACK.

Pipeline:  download → OCR → verify issuer → store blockchain → update status
"""

import os
import json
import threading
import time
from datetime import datetime

import cert_verifier
import whatsapp_handler

# Try importing blockchain module
try:
    from blockchain import web3_connect
    BLOCKCHAIN_AVAILABLE = True
except ImportError:
    BLOCKCHAIN_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "status.json")
CERT_STORE_FILE = os.path.join(BASE_DIR, "cert_store.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "certificates")

# Thread-safe lock for status.json writes
_lock = threading.Lock()


# ──────────────────────────────────────────────
# Status management
# ──────────────────────────────────────────────

def _read_status() -> dict:
    """Read the global status.json file."""
    if not os.path.exists(STATUS_FILE):
        return {}
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _write_status(data: dict):
    """Write the global status.json file (thread-safe)."""
    with _lock:
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)


def get_status(phone: str) -> dict:
    """Get the current pipeline status for a candidate by phone number."""
    all_status = _read_status()
    return all_status.get(phone, {
        "stage": "idle",
        "message": "No activity for this candidate.",
        "certs": [],
        "updated_at": "",
    })


def update_stage(phone: str, stage: str, message: str, cert_detail: dict = None):
    """Update the pipeline stage for a specific candidate."""
    all_status = _read_status()
    if phone not in all_status:
        all_status[phone] = {
            "stage": stage,
            "message": message,
            "certs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
    else:
        all_status[phone]["stage"] = stage
        all_status[phone]["message"] = message
        all_status[phone]["updated_at"] = datetime.utcnow().isoformat()

    if cert_detail:
        all_status[phone]["certs"].append(cert_detail)

    _write_status(all_status)


# ──────────────────────────────────────────────
# Fallback local cert store (when blockchain offline)
# ──────────────────────────────────────────────

def _store_locally(phone: str, cert_data: dict):
    """Store certificate data in cert_store.json as blockchain fallback."""
    try:
        if os.path.exists(CERT_STORE_FILE):
            with open(CERT_STORE_FILE, "r") as f:
                store = json.load(f)
        else:
            store = {}
    except (json.JSONDecodeError, IOError):
        store = {}

    if phone not in store:
        store[phone] = []
    store[phone].append(cert_data)

    with open(CERT_STORE_FILE, "w") as f:
        json.dump(store, f, indent=2, default=str)


# ──────────────────────────────────────────────
# Main pipeline (runs in background thread)
# ──────────────────────────────────────────────

def process_certificate(phone: str, media_url: str, content_type: str,
                        candidate_name: str = "", media_index: int = 0):
    """
    Full pipeline for a single certificate attachment.
    Designed to run in a threading.Thread.
    """
    phone_clean = whatsapp_handler.normalize_phone(phone)
    save_dir = os.path.join(UPLOAD_DIR, phone_clean.replace("+", ""))

    # ── Stage 1: Download ──
    update_stage(phone_clean, "downloading", "Downloading certificate attachment...")

    ext = ".pdf" if "pdf" in content_type.lower() else ".jpg"
    filename = f"cert_{media_index}_{int(time.time())}{ext}"
    local_path = whatsapp_handler.download_media(media_url, save_dir, filename)

    if not local_path:
        update_stage(phone_clean, "error", "Failed to download attachment from WhatsApp.")
        return

    # ── Stage 2: OCR / Extract ──
    update_stage(phone_clean, "extracting", "Extracting text from certificate (OCR)...")

    verification = cert_verifier.verify_certificate_file(local_path)

    cert_title = verification.get("cert_title", "Unknown Certificate")
    issuer = verification.get("issuer", "Unknown")

    # Send confirmation to candidate
    whatsapp_handler.send_confirmation(phone_clean, cert_title)

    # ── Stage 3: Verify with issuer ──
    update_stage(phone_clean, "verifying", f"Verifying '{cert_title}' with {issuer}...")

    is_authentic = verification.get("is_authentic", False)
    confidence = verification.get("confidence_score", 0)

    # ── Stage 4: Store on blockchain ──
    update_stage(phone_clean, "storing", "Storing on blockchain ledger...")

    file_hash = verification.get("file_hash", "")
    stored_on_chain = False
    tx_hash = ""

    if BLOCKCHAIN_AVAILABLE and file_hash:
        try:
            bc_result = web3_connect.store_verified_certificate(
                phone=phone_clean,
                cert_metadata={
                    "candidate_name": candidate_name or verification.get("candidate_name", ""),
                    "cert_title": cert_title,
                    "issuer": issuer,
                    "issue_date": verification.get("issue_date", ""),
                    "credential_id": verification.get("credential_id", ""),
                },
                file_hash=file_hash,
                is_authentic=is_authentic,
            )
            if not bc_result.get("error"):
                stored_on_chain = True
                tx_hash = bc_result.get("tx_hash", "")
        except Exception:
            stored_on_chain = False

    if not stored_on_chain:
        # Fallback: store locally
        _store_locally(phone_clean, {
            "file_hash": file_hash,
            "cert_title": cert_title,
            "issuer": issuer,
            "candidate_name": candidate_name,
            "is_authentic": is_authentic,
            "confidence_score": confidence,
            "stored_at": datetime.utcnow().isoformat(),
            "local_only": True,
        })

    # ── Stage 5: Done ──
    cert_detail = {
        "cert_title": cert_title,
        "issuer": issuer,
        "is_authentic": is_authentic,
        "confidence_score": confidence,
        "file_hash": file_hash,
        "tx_hash": tx_hash,
        "stored_on_chain": stored_on_chain,
        "verification_source": verification.get("verification_source", "none"),
        "verified_at": datetime.utcnow().isoformat(),
    }

    update_stage(phone_clean, "complete", "Certificate verification complete.", cert_detail)

    # Send result to candidate via WhatsApp
    whatsapp_handler.send_result(phone_clean, cert_title, is_authentic, confidence)


def run_pipeline(phone: str, media_list: list, candidate_name: str = ""):
    """
    Process all media attachments from a WhatsApp message.
    Each attachment runs through the full pipeline.
    Designed to be called from a background thread.
    """
    phone_clean = whatsapp_handler.normalize_phone(phone)
    update_stage(phone_clean, "received", f"Received {len(media_list)} attachment(s). Starting pipeline...")

    for i, media in enumerate(media_list):
        process_certificate(
            phone=phone_clean,
            media_url=media["url"],
            content_type=media.get("content_type", ""),
            candidate_name=candidate_name,
            media_index=i,
        )

    # Final stage
    status = get_status(phone_clean)
    total = len(status.get("certs", []))
    authentic = sum(1 for c in status.get("certs", []) if c.get("is_authentic"))
    update_stage(
        phone_clean, "complete",
        f"All done! {authentic}/{total} certificates verified successfully."
    )


def start_pipeline_thread(phone: str, media_list: list, candidate_name: str = ""):
    """Launch the pipeline in a background thread and return immediately."""
    t = threading.Thread(
        target=run_pipeline,
        args=(phone, media_list, candidate_name),
        daemon=True,
    )
    t.start()
    return t
