"""
deploy_contract.py — One-time script to compile & deploy CertificateVerify.sol
to your local Ganache blockchain. After deploying, it automatically updates
the CONTRACT_ADDRESS in blockchain/web3_connect.py.

Usage:
  1. Make sure Ganache is running on http://127.0.0.1:7545
  2. Run:  python deploy_contract.py
  3. Done! Restart your Flask app.
"""

import os
import re
from solcx import compile_standard, install_solc
from web3 import Web3

# ── Config ──
GANACHE_URL = "http://127.0.0.1:7545"
SOL_FILE = os.path.join(os.path.dirname(__file__), "contracts", "CertificateVerify.sol")
WEB3_FILE = os.path.join(os.path.dirname(__file__), "blockchain", "web3_connect.py")

def main():
    # 1. Connect to Ganache
    print("[1/4] Connecting to Ganache...")
    w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
    if not w3.is_connected():
        print("ERROR: Cannot connect to Ganache at", GANACHE_URL)
        print("       Make sure Ganache is open and running.")
        return
    print(f"       Connected! Chain ID: {w3.eth.chain_id}, Accounts: {len(w3.eth.accounts)}")

    # 2. Compile the contract
    print("[2/4] Compiling CertificateVerify.sol...")
    with open(SOL_FILE, "r") as f:
        source = f.read()

    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {"CertificateVerify.sol": {"content": source}},
            "settings": {
                "evmVersion": "london",
                "outputSelection": {
                    "*": {"*": ["abi", "evm.bytecode"]}
                }
            },
        },
        solc_version="0.8.21",
    )

    contract_data = compiled["contracts"]["CertificateVerify.sol"]["CertificateVerify"]
    abi = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]
    print("       Compiled successfully!")

    # 3. Deploy
    print("[3/4] Deploying to Ganache...")
    account = w3.eth.accounts[0]
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor().transact({"from": account})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    address = receipt.contractAddress
    print(f"       Deployed at: {address}")
    print(f"       Tx hash:     {receipt.transactionHash.hex()}")
    print(f"       Gas used:    {receipt.gasUsed}")

    # 4. Update web3_connect.py with the real address
    print("[4/4] Updating blockchain/web3_connect.py...")
    with open(WEB3_FILE, "r") as f:
        content = f.read()

    new_content = re.sub(
        r'CONTRACT_ADDRESS\s*=\s*"0x[0-9a-fA-F]+"',
        f'CONTRACT_ADDRESS = "{address}"',
        content,
    )
    with open(WEB3_FILE, "w") as f:
        f.write(new_content)
    print("       CONTRACT_ADDRESS updated!")

    print()
    print("=" * 55)
    print("  DONE! Contract deployed and address saved.")
    print(f"  Address: {address}")
    print("  Now restart Flask:  python app.py")
    print("=" * 55)


if __name__ == "__main__":
    main()
