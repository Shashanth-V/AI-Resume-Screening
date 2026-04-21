# REVA University
## School of Computer Science and Engineering
### Mini Project Report (6th Semester)

Programs: B Tech CSSE, B Tech CSIT, B Tech ISE, B Tech IoT

---

## Title Page Content

Project Title: RecruitAI - AI Resume Screening and Certificate Verification with Blockchain and WhatsApp Integration

Submitted by:
- Student Name 1 - USN/Roll No: [Enter USN]
- Student Name 2 - USN/Roll No: [Enter USN]
- Student Name 3 - USN/Roll No: [Enter USN]

Course/Subject Name: Mini Project

Department Name: School of Computer Science and Engineering

Institution Name: REVA University

Academic Year: 2025-2026

Guide Name: [Guide Name]

---

## Certificate (Ready Draft)

This is to certify that the mini project titled "RecruitAI - AI Resume Screening and Certificate Verification with Blockchain and WhatsApp Integration" is a bonafide work carried out by [Student Name 1], [Student Name 2], and [Student Name 3], students of 6th Semester, School of Computer Science and Engineering, REVA University, in partial fulfillment of the requirements for the award of the degree of Bachelor of Technology during the academic year 2025-2026.

The work has been completed under my supervision and guidance. The report submitted is found satisfactory and approved for evaluation.

Guide Signature: ____________________

Guide Name: ____________________

Head of Department Signature: ____________________

HOD Name: ____________________

Date: ____________________

Place: Bengaluru

---

## Declaration (Ready Draft)

We hereby declare that the work presented in this mini project report titled "RecruitAI - AI Resume Screening and Certificate Verification with Blockchain and WhatsApp Integration" is an original work carried out by us under the guidance of [Guide Name], School of Computer Science and Engineering, REVA University.

We further declare that this report has not been submitted, in full or in part, to any other institution or university for the award of any degree or diploma. All references used in this work have been properly acknowledged.

Student Signature 1: ____________________

Student Signature 2: ____________________

Student Signature 3: ____________________

Date: ____________________

---

## Acknowledgement

We express our sincere gratitude to our project guide, [Guide Name], for the constant guidance, encouragement, and valuable suggestions throughout this project. We thank the faculty members of the School of Computer Science and Engineering, REVA University, for their support and technical inputs during the development of this system.

We also thank the institution for providing the necessary infrastructure and learning environment to complete this work. Finally, we acknowledge our classmates and friends for their feedback and support during testing and documentation.

---

## Abstract

Recruitment teams often spend significant time manually reviewing resumes and validating candidate certifications. Manual screening is slow, inconsistent, and difficult to scale when the number of applicants increases. To address this issue, this project proposes RecruitAI, a web-based intelligent recruitment assistant that combines resume ranking, certificate verification, and communication automation.

The system uses TF-IDF and cosine similarity to compute how closely each resume matches a given job description. Candidate details such as name, phone number, and certificate claims are extracted from uploaded resumes. For trust validation, certificates are processed through OCR and issuer-based verification. The verified certificate hashes are stored on a blockchain ledger (Ganache + Solidity) to provide immutability and traceability. If blockchain is unavailable, a controlled local fallback store is used. Twilio WhatsApp integration is used to automate certificate request and status communication workflows.

The developed prototype demonstrates improved recruiter productivity, transparent verification tracking, and better shortlist quality through a hybrid score and trust-aware workflow. The solution is suitable for campus hiring, SME recruitment, and internal HR pre-screening pipelines.

---

## Table of Contents

1. Introduction
2. Literature Survey
3. System Analysis
4. System Design
5. Implementation
6. Results and Discussion
7. Conclusion and Future Work
8. References
9. Appendices

Note: Add page numbers while preparing final print/PDF version.

---

## List of Figures (Suggested)

1. System Architecture Diagram
2. Resume Screening Workflow
3. WhatsApp Verification Pipeline
4. Blockchain Certificate Storage Flow
5. Dashboard and Trust Metrics UI

---

## List of Tables (Suggested)

1. Technology Stack
2. Module-Wise Responsibility
3. API Endpoints
4. Test Cases and Outputs
5. Performance Comparison (Manual vs Automated)

---

## CHAPTER 1: INTRODUCTION

### 1.1 Background
Modern hiring processes involve large candidate pools where recruiters must quickly identify relevant profiles. Traditional manual screening is repetitive and prone to human bias. At the same time, certificate authenticity is becoming critical due to frequent fake or unverifiable credentials.

### 1.2 Problem Statement
Existing recruitment workflows face three major issues: slow resume shortlisting, weak certificate validation, and fragmented candidate communication. There is a need for a unified platform that can rank resumes intelligently, verify certifications reliably, and automate communication with candidates.

### 1.3 Objectives
- To build an AI-based resume ranking system using job description matching.
- To extract candidate metadata and certification claims from resumes.
- To verify certificate authenticity with OCR and issuer validation.
- To store certificate verification records on blockchain for integrity.
- To automate candidate communication using WhatsApp.
- To provide dashboard-level visibility for recruiter decisions.

### 1.4 Scope of the Project
The project focuses on a functional prototype for academic and practical demonstration. It supports PDF resume upload, candidate scoring, certificate verification workflow, and recruiter dashboard analytics. It is designed for small to medium hiring batches and can be extended for large-scale enterprise use.

### 1.5 Organization of the Report
Chapter 1 introduces the problem and objectives. Chapter 2 reviews existing approaches. Chapter 3 presents system analysis. Chapter 4 explains architecture and design. Chapter 5 describes implementation details. Chapter 6 presents results and testing. Chapter 7 concludes the project and suggests future enhancements.

---

## CHAPTER 2: LITERATURE SURVEY

### 2.1 Existing Research and Systems
Most ATS platforms provide keyword filtering and basic ranking. Research in NLP-based recruitment recommends vector space models and semantic scoring for improved matching quality. Certificate verification platforms exist but are usually separate from hiring tools.

### 2.2 Comparison of Approaches
- Keyword matching: fast but poor context understanding.
- Rule-based scoring: simple but rigid and domain-specific.
- TF-IDF + cosine similarity: interpretable, lightweight, and effective for shortlisting.
- Deep learning methods: accurate but computationally expensive and data-heavy.

### 2.3 Limitations in Current Solutions
- No integrated flow from shortlisting to certificate trust validation.
- Manual communication overhead with candidates.
- Lack of tamper-proof record for validated credentials.
- Limited audit visibility for recruiter actions.

This project addresses these limitations through an integrated AI + blockchain + WhatsApp pipeline.

---

## CHAPTER 3: SYSTEM ANALYSIS

### 3.1 Existing System
In the existing process, recruiters manually read resumes, shortlist candidates, and ask for certificate proofs via email/phone. Verification is mostly manual and not traceable across teams.

### 3.2 Proposed System
RecruitAI provides a single platform where recruiters can upload resumes, compute match scores, extract candidate details, request certificates on WhatsApp, verify authenticity, and store trust records on blockchain.

### 3.3 Advantages of Proposed System
- Faster shortlisting through automated scoring.
- Reduced fraud risk with certificate verification.
- Transparent and immutable proof using blockchain hashes.
- Better user experience with WhatsApp automation.
- Recruiter action tracking through audit logs.
- Role-based access support.

---

## CHAPTER 4: SYSTEM DESIGN

### 4.1 Architecture Overview
The system follows a modular client-server architecture:
- Frontend: HTML/CSS/JavaScript dashboard
- Backend: Flask REST endpoints
- Database: SQLite for users and resume analysis records
- Verification engine: OCR + issuer checks
- Communication module: Twilio WhatsApp
- Blockchain module: Web3.py + Solidity contract on Ganache

### 4.2 Data Flow (Textual DFD)
1. Recruiter logs in and uploads resumes with job description.
2. Backend extracts text and computes TF-IDF and semantic scores.
3. Candidate metadata and claims are stored.
4. Recruiter triggers WhatsApp certificate request.
5. Candidate responds with certificate attachments.
6. Worker pipeline downloads, verifies, and stores trust record.
7. Dashboard displays final score, cert status, and trust metrics.

### 4.3 UML (Suggested)
- Use Case Diagram: Recruiter, Candidate, Admin
- Activity Diagram: Resume upload to shortlist
- Sequence Diagram: WhatsApp webhook to verification completion

### 4.4 Core Algorithm Logic
- Hybrid Match Score:
  - TF-IDF Score from cosine similarity
  - Semantic overlap score from token intersection
  - Final score combines both metrics
- Certificate trust decision uses source validity and claim match threshold.

---

## CHAPTER 5: IMPLEMENTATION

### 5.1 Tools and Technologies
- Python, Flask, SQLite
- scikit-learn, NLTK, PyPDF2
- pytesseract, Pillow, BeautifulSoup, requests
- Twilio API
- Solidity, Web3.py, Ganache
- HTML, CSS, JavaScript

### 5.2 Hardware and Software Requirements
Hardware:
- Intel i5 or above
- 8 GB RAM (minimum)
- 10 GB free disk space

Software:
- Windows 10/11
- Python 3.10+
- Ganache
- Tesseract OCR
- Modern browser (Chrome/Edge)

### 5.3 Module Description
- Authentication Module: registration, login, role-aware access.
- Resume Analysis Module: PDF parsing, text cleaning, hybrid scoring.
- Candidate Extraction Module: phone and certificate claim extraction.
- WhatsApp Module: request messages and inbound webhook parsing.
- Verification Worker: background OCR, source checks, trust computation.
- Blockchain Module: store/verify certificate hashes and metadata.
- Dashboard Module: insights, filters, shortlist operations, audit feed.

### 5.4 Sample Code Snippet (Conceptual)
```python
# Hybrid score (concept)
tfidf_score = cosine_similarity(jd_vector, resume_vector) * 100
semantic_score = overlap(jd_tokens, resume_tokens) * 100
final_score = 0.7 * tfidf_score + 0.3 * semantic_score
```

---

## CHAPTER 6: RESULTS AND DISCUSSION

### 6.1 Output Summary
The application successfully performs multi-resume ranking, displays ordered shortlists, and allows certificate verification tracking. WhatsApp communication and webhook-driven processing reduce manual follow-up workload.

### 6.2 Performance Discussion
- Resume scoring is near real-time for small-to-medium batches.
- Verification latency depends on OCR quality, internet response from issuer endpoints, and blockchain transaction confirmation time.
- Role-based access and audit logs improve operational control.

### 6.3 Test Cases and Results (Sample)
- Test Case 1: Upload valid resumes and JD -> Expected ranked output -> Passed.
- Test Case 2: Upload invalid file type -> Expected validation error -> Passed.
- Test Case 3: Send WhatsApp request with valid phone -> Message dispatched -> Passed.
- Test Case 4: Candidate sends certificate -> Worker pipeline updates status -> Passed.
- Test Case 5: Verify duplicate certificate hash -> Duplicate detection response -> Passed.
- Test Case 6: Blockchain offline -> Local fallback store used -> Passed.

### 6.4 Key Observations
- Hybrid scoring gives better practical ranking than strict keyword match.
- Certificate trust signals help recruiters prioritize review effort.
- End-to-end integration provides measurable time savings.

---

## CHAPTER 7: CONCLUSION AND FUTURE WORK

### 7.1 Conclusion
This project presents a practical recruitment intelligence system that integrates AI-based resume screening, certificate trust validation, blockchain-backed integrity, and WhatsApp automation. The developed prototype demonstrates that combining these components in a single workflow improves speed, transparency, and decision quality in hiring operations.

### 7.2 Key Findings
- Automated scoring significantly reduces manual screening effort.
- Trust-aware certificate checks reduce credential fraud risk.
- Blockchain storage adds tamper resistance for verification records.
- WhatsApp integration improves candidate response workflow.

### 7.3 Limitations
- OCR quality depends on document clarity.
- External API/source availability can affect verification confidence.
- Current blockchain setup uses local Ganache (development environment).

### 7.4 Future Enhancements
- Cloud deployment with production-grade blockchain integration.
- Queue-based background workers (Celery/RQ).
- Advanced semantic models (transformers/embeddings).
- Multi-language resume support.
- Email/SMS fallback notifications.
- Recruiter analytics with predictive hiring insights.

---

## REFERENCES (IEEE Style Samples)

[1] G. Salton and C. Buckley, "Term-weighting approaches in automatic text retrieval," Information Processing and Management, vol. 24, no. 5, pp. 513-523, 1988.

[2] C. D. Manning, P. Raghavan and H. Schutze, Introduction to Information Retrieval. Cambridge, U.K.: Cambridge University Press, 2008.

[3] S. Russell and P. Norvig, Artificial Intelligence: A Modern Approach, 4th ed. Pearson, 2020.

[4] Flask Documentation. [Online]. Available: https://flask.palletsprojects.com/

[5] scikit-learn Documentation. [Online]. Available: https://scikit-learn.org/

[6] Web3.py Documentation. [Online]. Available: https://web3py.readthedocs.io/

[7] Twilio WhatsApp API Documentation. [Online]. Available: https://www.twilio.com/docs/whatsapp

[8] Solidity Documentation. [Online]. Available: https://docs.soliditylang.org/

---

## APPENDICES

### Appendix A: API Endpoint List
- /register
- /login
- /upload-resume
- /send-whatsapp
- /whatsapp-webhook
- /verify-certificate
- /store-certificate
- /dashboard-data
- /audit-summary

### Appendix B: Screenshots to Include
- Login and registration page
- Resume upload and result cards
- Dashboard ranking table
- WhatsApp request panel
- Verification status panel
- Ledger/trust view

### Appendix C: Dataset Notes
Use sample resumes and certificate files for controlled testing. Store anonymized test inputs in project-specific folders for reproducibility.

---

## Formatting Guidelines (As Required)
- Font: Times New Roman
- Font Size:
  - Headings: 14-16 (bold)
  - Body: 12
- Line Spacing: 1.5
- Margins: 1 inch on all sides
- Page Numbering: Bottom center

---

## Optional Sections (If Required)

### Abbreviations
- ATS: Applicant Tracking System
- OCR: Optical Character Recognition
- DFD: Data Flow Diagram
- API: Application Programming Interface

### Glossary
- Cosine Similarity: A metric to measure text similarity by vector angle.
- Certificate Hash: Unique SHA-256 fingerprint of certificate content.
- Webhook: Endpoint that receives real-time external event data.

### List of Symbols
- %: Percentage score
- >=: Greater than or equal to
- ->: Flow direction
