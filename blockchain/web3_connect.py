"""
web3_connect.py
Handles all blockchain interactions — connecting to a local Ganache instance,
storing certificate hashes (simple + rich metadata), and verifying them
via the deployed smart contract.
"""

import json
import os
from web3 import Web3

# ──────────────────────────────────────────────
# Configuration – update these after deploying
# the CertificateVerify contract on Ganache
# ──────────────────────────────────────────────
GANACHE_URL = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")

# Replace with the actual deployed contract address from Ganache / Remix
CONTRACT_ADDRESS = "0x22e24aE2063EA26E0D04146563FEa9D0b55368f4"

# ABI generated from CertificateVerify.sol (enhanced version)
CONTRACT_ABI = [
    {"inputs": [], "stateMutability": "nonpayable", "type": "constructor"},
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "hash", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "CertificateAdded",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "string", "name": "phone", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "fileHash", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "candidateName", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "certTitle", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "issuerName", "type": "string"},
            {"indexed": False, "internalType": "bool", "name": "isAuthentic", "type": "bool"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "CertificateStored",
        "type": "event"
    },
    # ── Legacy simple add ──
    {
        "inputs": [{"internalType": "string", "name": "hash", "type": "string"}],
        "name": "addCertificate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # ── Rich store ──
    {
        "inputs": [
            {"internalType": "string", "name": "phone", "type": "string"},
            {"internalType": "string", "name": "fileHash", "type": "string"},
            {"internalType": "string", "name": "candidateName", "type": "string"},
            {"internalType": "string", "name": "certTitle", "type": "string"},
            {"internalType": "string", "name": "issuerName", "type": "string"},
            {"internalType": "string", "name": "issueDate", "type": "string"},
            {"internalType": "bool", "name": "isAuthentic", "type": "bool"},
            {"internalType": "string", "name": "credentialId", "type": "string"}
        ],
        "name": "storeCertificate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # ── Reads ──
    {
        "inputs": [{"internalType": "string", "name": "hash", "type": "string"}],
        "name": "verifyCertificate",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "fileHash", "type": "string"}],
        "name": "getCertificate",
        "outputs": [
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "bool", "name": "", "type": "bool"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "string", "name": "", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "phone", "type": "string"}],
        "name": "getCandidateCertCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "phone", "type": "string"},
            {"internalType": "uint256", "name": "index", "type": "uint256"}
        ],
        "name": "getCandidateCertHash",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "verifier", "type": "address"}],
        "name": "addVerifier",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "verifier", "type": "address"}],
        "name": "removeVerifier",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "authorizedVerifiers",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
]


def _get_web3():
    """Return a connected Web3 instance or None if Ganache is unreachable."""
    w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
    if w3.is_connected():
        return w3
    return None


def _get_contract(w3):
    """Return a contract object bound to the configured address."""
    return w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=CONTRACT_ABI
    )


def check_connection():
    """Check if the blockchain node is reachable."""
    w3 = _get_web3()
    return w3 is not None


# ──────────────────────────────────────────────
# Legacy simple store (backward compat)
# ──────────────────────────────────────────────

def store_certificate(cert_hash: str) -> dict:
    """
    Store a certificate SHA-256 hash on the blockchain (simple mode).
    Uses the first Ganache account as the transaction sender (contract owner).
    """
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
        account = w3.eth.accounts[0]

        tx_hash = contract.functions.addCertificate(cert_hash).transact({"from": account})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "hash": cert_hash,
            "tx_hash": receipt.transactionHash.hex(),
            "status": "Stored Successfully"
        }
    except Exception as e:
        msg = str(e)
        if "already exists" in msg.lower():
            return {"error": "Certificate already exists on the blockchain. Use Verify to check it."}
        return {"error": "Blockchain error: " + msg.split("(")[0].strip()}


# ──────────────────────────────────────────────
# Rich store with metadata
# ──────────────────────────────────────────────

def store_verified_certificate(phone: str, cert_metadata: dict,
                                file_hash: str, is_authentic: bool = False) -> dict:
    """
    Store a verified certificate with full metadata on the blockchain.
    Called by the background worker after OCR + issuer verification.
    """
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
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
            "tx_hash": receipt.transactionHash.hex(),
            "status": "Stored Successfully"
        }
    except Exception as e:
        msg = str(e)
        if "already exists" in msg.lower():
            return {"error": "Certificate already exists on the blockchain."}
        return {"error": "Blockchain error: " + msg.split("(")[0].strip()}


# ──────────────────────────────────────────────
# Verify
# ──────────────────────────────────────────────

def verify_certificate(cert_hash: str) -> dict:
    """Verify whether a certificate hash exists on the blockchain."""
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
        exists = contract.functions.verifyCertificate(cert_hash).call()

        return {
            "hash": cert_hash,
            "status": "Verified" if exists else "Fake/Not Found"
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────
# Read certificate metadata from blockchain
# ──────────────────────────────────────────────

def get_certificate_by_hash(file_hash: str) -> dict:
    """Fetch full certificate metadata from blockchain by file hash."""
    try:
        w3 = _get_web3()
        if w3 is None:
            return {"error": "Blockchain not connected"}

        contract = _get_contract(w3)
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
    """Fetch all certificates stored on blockchain for a candidate (by phone)."""
    try:
        w3 = _get_web3()
        if w3 is None:
            return []

        contract = _get_contract(w3)
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
    """
    Fetch blockchain certs for a phone number and cross-check against resume claims.
    Delegates to resume_matcher for the actual matching.
    """
    blockchain_certs = get_candidate_certificates(phone)

    # Import here to avoid circular import
    import resume_matcher
    return resume_matcher.cross_check_resume_vs_blockchain(
        " ".join(resume_claims),
        blockchain_certs,
    )
