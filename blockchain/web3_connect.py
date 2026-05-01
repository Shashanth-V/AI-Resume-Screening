"""
web3_connect.py
Handles all blockchain interactions — safely for both:
- Localhost (Ganache works)
- Render/Cloud deployment (Blockchain gracefully disabled)
"""

import json
import os

# Safe Web3 import
try:
    from web3 import Web3
except Exception as e:
    print("Web3 import failed:", e)
    Web3 = None


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
GANACHE_URL = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")

CONTRACT_ADDRESS = "0x22e24aE2063EA26E0D04146563FEa9D0b55368f4"

# ABI remains unchanged
CONTRACT_ABI = [
    # Keep your FULL existing ABI here exactly as before
]


# ──────────────────────────────────────────────
# Safe blockchain initialization
# ──────────────────────────────────────────────

def _get_web3():
    """Return connected Web3 instance or None safely."""

    if Web3 is None:
        print("Web3 unavailable.")
        return None

    # Disable localhost Ganache on deployed servers
    if not GANACHE_URL or "127.0.0.1" in GANACHE_URL or "localhost" in GANACHE_URL:
        print("Blockchain disabled: Local Ganache unavailable in deployment.")
        return None

    try:
        w3 = Web3(Web3.HTTPProvider(GANACHE_URL))

        if w3.is_connected():
            print("Blockchain connected successfully.")
            return w3
        else:
            print("Blockchain connection failed.")
            return None

    except Exception as e:
        print("Blockchain initialization failed:", e)
        return None


def _get_contract(w3):
    """Return contract instance."""
    if w3 is None:
        return None

    try:
        return w3.eth.contract(
            address=w3.to_checksum_address(CONTRACT_ADDRESS),
            abi=CONTRACT_ABI
        )
    except Exception as e:
        print("Contract initialization failed:", e)
        return None


def check_connection():
    """Check blockchain availability."""
    return _get_web3() is not None


# ──────────────────────────────────────────────
# Legacy simple store
# ──────────────────────────────────────────────

def store_certificate(cert_hash: str) -> dict:
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
        if contract is None:
            return {"error": "Contract unavailable"}

        account = w3.eth.accounts[0]

        tx_hash = contract.functions.addCertificate(cert_hash).transact({"from": account})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "hash": cert_hash,
            "tx_hash": receipt["transactionHash"].hex(),
            "status": "Stored Successfully"
        }

    except Exception as e:
        msg = str(e)
        if "already exists" in msg.lower():
            return {"error": "Certificate already exists on blockchain"}
        return {"error": "Blockchain error: " + msg}


# ──────────────────────────────────────────────
# Rich store
# ──────────────────────────────────────────────

def store_verified_certificate(phone: str, cert_metadata: dict,
                               file_hash: str, is_authentic: bool = False) -> dict:
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
        if contract is None:
            return {"error": "Contract unavailable"}

        account = w3.eth.accounts[0]

        tx_hash = contract.functions.storeCertificate(
            phone,
            file_hash,
            cert_metadata.get("candidate_name", ""),
            cert_metadata.get("cert_title", ""),
            cert_metadata.get("issuer", ""),
            cert_metadata.get("issue_date", ""),
            is_authentic,
            cert_metadata.get("credential_id", ""),
        ).transact({"from": account})

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "hash": file_hash,
            "tx_hash": receipt["transactionHash"].hex(),
            "status": "Stored Successfully"
        }

    except Exception as e:
        msg = str(e)
        if "already exists" in msg.lower():
            return {"error": "Certificate already exists on blockchain"}
        return {"error": "Blockchain error: " + msg}


# ──────────────────────────────────────────────
# Verify certificate
# ──────────────────────────────────────────────

def verify_certificate(cert_hash: str) -> dict:
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
        if contract is None:
            return {"error": "Contract unavailable"}

        exists = contract.functions.verifyCertificate(cert_hash).call()

        return {
            "hash": cert_hash,
            "status": "Verified" if exists else "Fake/Not Found"
        }

    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# Read certificate metadata
# ──────────────────────────────────────────────

def get_certificate_by_hash(file_hash: str) -> dict:
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
        if contract is None:
            return {"error": "Contract unavailable"}

        result = contract.functions.getCertificate(file_hash).call()

        return {
            "file_hash": result[0],
            "candidate_name": result[1],
            "cert_title": result[2],
            "issuer": result[3],
            "issue_date": result[4],
            "is_authentic": result[5],
            "verified_at": result[6],
            "credential_id": result[7],
        }

    except Exception as e:
        return {"error": str(e)}


def get_candidate_certificates(phone: str) -> list:
    try:
        w3 = _get_web3()
        if w3 is None:
            return []

        contract = _get_contract(w3)
        if contract is None:
            return []

        count = contract.functions.getCandidateCertCount(phone).call()

        certs = []
        for i in range(count):
            hash_val = contract.functions.getCandidateCertHash(phone, i).call()
            cert_data = get_certificate_by_hash(hash_val)

            if not cert_data.get("error"):
                certs.append(cert_data)

        return certs

    except Exception:
        return []


def cross_check_with_resume(phone: str, resume_claims: list) -> dict:
    blockchain_certs = get_candidate_certificates(phone)

    import resume_matcher
    return resume_matcher.cross_check_resume_vs_blockchain(
        " ".join(resume_claims),
        blockchain_certs,
    )