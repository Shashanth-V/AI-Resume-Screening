// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title CertificateVerify
 * @dev Stores and verifies certificate metadata on-chain with rich structs.
 *      Only the contract owner (or authorized verifiers) can add certificates.
 */
contract CertificateVerify {

    address public owner;

    struct Certificate {
        string fileHash;
        string candidateName;
        string certTitle;
        string issuerName;
        string issueDate;
        bool   isAuthentic;
        uint256 verifiedAt;
        string credentialId;
    }

    // fileHash → Certificate metadata
    mapping(string => Certificate) public certificates;
    // fileHash → exists flag (kept for backward-compat with simple verify)
    mapping(string => bool) private _exists;
    // phone → list of fileHashes
    mapping(string => string[]) private _candidateHashes;
    // authorized verifiers
    mapping(address => bool) public authorizedVerifiers;

    event CertificateAdded(string hash, uint256 timestamp);
    event CertificateStored(
        string phone,
        string fileHash,
        string candidateName,
        string certTitle,
        string issuerName,
        bool   isAuthentic,
        uint256 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can add certificates");
        _;
    }

    modifier onlyAuthorized() {
        require(msg.sender == owner || authorizedVerifiers[msg.sender], "Not authorized");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    // ── Legacy simple add (backward compat) ──
    function addCertificate(string memory hash) public onlyOwner {
        require(!_exists[hash], "Certificate already exists");
        _exists[hash] = true;
        emit CertificateAdded(hash, block.timestamp);
    }

    // ── Rich store with metadata ──
    function storeCertificate(
        string memory phone,
        string memory fileHash,
        string memory candidateName,
        string memory certTitle,
        string memory issuerName,
        string memory issueDate,
        bool   isAuthentic,
        string memory credentialId
    ) public onlyAuthorized {
        require(!_exists[fileHash], "Certificate already exists");
        _exists[fileHash] = true;
        certificates[fileHash] = Certificate(
            fileHash, candidateName, certTitle, issuerName,
            issueDate, isAuthentic, block.timestamp, credentialId
        );
        _candidateHashes[phone].push(fileHash);
        emit CertificateStored(
            phone, fileHash, candidateName, certTitle,
            issuerName, isAuthentic, block.timestamp
        );
    }

    // ── Read helpers ──
    function verifyCertificate(string memory hash) public view returns (bool) {
        return _exists[hash];
    }

    function getCertificate(string memory fileHash) public view returns (
        string memory, string memory, string memory, string memory,
        string memory, bool, uint256, string memory
    ) {
        Certificate memory c = certificates[fileHash];
        return (
            c.fileHash, c.candidateName, c.certTitle, c.issuerName,
            c.issueDate, c.isAuthentic, c.verifiedAt, c.credentialId
        );
    }

    function getCandidateCertCount(string memory phone) public view returns (uint256) {
        return _candidateHashes[phone].length;
    }

    function getCandidateCertHash(string memory phone, uint256 index) public view returns (string memory) {
        require(index < _candidateHashes[phone].length, "Index out of bounds");
        return _candidateHashes[phone][index];
    }

    // ── Admin ──
    function addVerifier(address verifier) public onlyOwner {
        authorizedVerifiers[verifier] = true;
    }

    function removeVerifier(address verifier) public onlyOwner {
        authorizedVerifiers[verifier] = false;
    }
}
