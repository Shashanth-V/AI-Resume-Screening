"""
whatsapp_handler.py — Twilio WhatsApp integration for RecruitAI.
Sends certificate-request messages and handles incoming webhook replies.
"""

import os
import re
import requests as http_requests
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# Lazy-load the Twilio client to avoid import errors when package is missing
_client = None


def _get_client():
    """Return the Twilio REST client (created once)."""
    global _client
    if _client is None:
        try:
            from twilio.rest import Client
            _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        except Exception:
            _client = None
    return _client


# ──────────────────────────────────────────────
# Phone number helpers
# ──────────────────────────────────────────────

def normalize_phone(raw: str) -> str:
    """Normalize a phone string to E.164 format (+91XXXXXXXXXX).
    Strips non-digits, prepends +91 if no country code present."""
    digits = re.sub(r"[^\d]", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if not raw.startswith("+"):
        return "+" + digits
    return "+" + digits


def whatsapp_addr(phone: str) -> str:
    """Wrap a phone number in Twilio WhatsApp format."""
    p = normalize_phone(phone)
    if not p.startswith("whatsapp:"):
        return "whatsapp:" + p
    return p


# ──────────────────────────────────────────────
# Send certificate request
# ──────────────────────────────────────────────

def send_certificate_request(phone_number: str, candidate_name: str, cert_list: list) -> dict:
    """
    Send a WhatsApp message to the candidate asking them to upload certificates.
    Returns dict with 'success' bool and 'message_sid' or 'error'.
    """
    client = _get_client()
    if client is None:
        return {"success": False, "error": "Twilio client not configured. Check .env credentials."}

    # Show only top 5 certs, trim long names
    trimmed = [c[:50] for c in cert_list[:5]] if cert_list else []
    if trimmed:
        certs_text = "\n".join(f"  \u2022 {c}" for c in trimmed)
    else:
        certs_text = "  \u2022 (certificates mentioned in your resume)"

    body = (
        f"Hi! RecruitAI here \U0001f44b\n\n"
        f"We found these certifications on your resume:\n{certs_text}\n\n"
        f"Please reply with photos/PDFs of your certificates for verification. \u2705"
    )

    try:
        message = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_FROM,
            to=whatsapp_addr(phone_number),
        )
        return {"success": True, "message_sid": message.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ──────────────────────────────────────────────
# Send confirmation back to candidate
# ──────────────────────────────────────────────

def send_confirmation(phone_number: str, cert_name: str) -> dict:
    """Send a quick confirmation that a certificate was received & is being verified."""
    client = _get_client()
    if client is None:
        return {"success": False, "error": "Twilio not configured"}

    body = f"\u2705 Received! Verifying your {cert_name} now..."

    try:
        message = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_FROM,
            to=whatsapp_addr(phone_number),
        )
        return {"success": True, "message_sid": message.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_result(phone_number: str, cert_name: str, is_authentic: bool, confidence: int) -> dict:
    """Send verification result back to candidate."""
    client = _get_client()
    if client is None:
        return {"success": False, "error": "Twilio not configured"}

    if is_authentic:
        body = (
            f"\u2705 *{cert_name}* — Verified!\n"
            f"Confidence: {confidence}%\n"
            f"Your certificate has been securely stored on the blockchain."
        )
    else:
        body = (
            f"\u274c *{cert_name}* — Could not verify.\n"
            f"Confidence: {confidence}%\n"
            f"Please ensure the certificate is authentic and try again."
        )

    try:
        message = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_FROM,
            to=whatsapp_addr(phone_number),
        )
        return {"success": True, "message_sid": message.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_shortlist_notification(phone_number: str, candidate_name: str) -> dict:
    """Send shortlist notification to a candidate via WhatsApp."""
    client = _get_client()
    if client is None:
        return {"success": False, "error": "Twilio not configured"}

    body = (
        f"\U0001f389 *Congratulations, {candidate_name}!*\n\n"
        f"Your resume has been *shortlisted* by the recruiter.\n"
        f"You will be contacted soon regarding the next steps.\n\n"
        f"Best of luck! — RecruitAI"
    )

    try:
        message = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_FROM,
            to=whatsapp_addr(phone_number),
        )
        return {"success": True, "message_sid": message.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ──────────────────────────────────────────────
# Download attachment from Twilio media URL
# ──────────────────────────────────────────────

def download_media(media_url: str, save_dir: str, filename: str) -> str:
    """Download an attachment from Twilio's media URL.
    Returns the local file path on success, or empty string on failure."""
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    try:
        resp = http_requests.get(
            media_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=30,
        )
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return save_path
    except Exception:
        pass
    return ""


# ──────────────────────────────────────────────
# Parse incoming webhook data
# ──────────────────────────────────────────────

def parse_webhook(form_data: dict) -> dict:
    """
    Parse Twilio webhook POST form data.
    Returns dict with: phone, body, num_media, media list.
    """
    phone_raw = form_data.get("From", "")
    phone = phone_raw.replace("whatsapp:", "")

    result = {
        "phone": normalize_phone(phone),
        "body": form_data.get("Body", "").strip(),
        "num_media": int(form_data.get("NumMedia", 0)),
        "media": [],
    }

    for i in range(result["num_media"]):
        url = form_data.get(f"MediaUrl{i}", "")
        content_type = form_data.get(f"MediaContentType{i}", "")
        if url:
            result["media"].append({
                "url": url,
                "content_type": content_type,
            })

    return result
