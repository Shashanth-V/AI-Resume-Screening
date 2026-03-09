// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title CertificateVerify
 * @dev Stores and verifies SHA-256 hashes of certificates on-chain.
 *      Only the contract owner can add new certificate hashes.
 */
contract CertificateVerify {

    address public owner;

    // Mapping from certificate hash string to existence flag
    mapping(string => bool) private certificates;

    // Event emitted when a new certificate hash is stored
    event CertificateAdded(string hash, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can add certificates");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @dev Stores a certificate hash on the blockchain.
     * @param hash The SHA-256 hash string of the certificate file.
     */
    function addCertificate(string memory hash) public onlyOwner {
        require(!certificates[hash], "Certificate already exists");
        certificates[hash] = true;
        emit CertificateAdded(hash, block.timestamp);
    }

    /**
     * @dev Checks whether a certificate hash exists on the blockchain.
     * @param hash The SHA-256 hash string to verify.
     * @return bool True if the certificate hash is stored, false otherwise.
     */
    function verifyCertificate(string memory hash) public view returns (bool) {
        return certificates[hash];
    }
}
