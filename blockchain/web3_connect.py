"""
web3_connect.py
Handles all blockchain interactions — connecting to a local Ganache instance,
storing certificate hashes, and verifying them via the deployed smart contract.
"""

from web3 import Web3

# ──────────────────────────────────────────────
# Configuration – update these after deploying
# the CertificateVerify contract on Ganache
# ──────────────────────────────────────────────
GANACHE_URL = "http://127.0.0.1:7545"

# Replace with the actual deployed contract address from Ganache / Remix
CONTRACT_ADDRESS = "0x40C7e31f3e7249506bAdbAA2B6396f921f64b0B4"

# ABI generated from CertificateVerify.sol — matches the Solidity contract exactly
CONTRACT_ABI = [
    {
        "inputs": [],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
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
        "inputs": [{"internalType": "string", "name": "hash", "type": "string"}],
        "name": "addCertificate",
        "outputs": [],
        "stateMutability": "nonpayable",
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
        "inputs": [{"internalType": "string", "name": "hash", "type": "string"}],
        "name": "verifyCertificate",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
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


def store_certificate(cert_hash: str) -> dict:
    """
    Store a certificate SHA-256 hash on the blockchain.
    Uses the first Ganache account as the transaction sender (contract owner).
    Returns dict with hash, tx_hash, and status.
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


def verify_certificate(cert_hash: str) -> dict:
    """
    Verify whether a certificate hash exists on the blockchain.
    Returns dict with hash and verification status.
    """
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
