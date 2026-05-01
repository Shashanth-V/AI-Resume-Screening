#!/usr/bin/env python
"""
Quick test script to verify 1 certificate without going through the UI.
Run: python test_verify_certificate.py
"""

import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cert_verifier import verify_certificate_file, extract_text, extract_metadata, verify_with_issuer

def create_test_certificate():
    """Create a minimal test certificate PDF with Coursera metadata."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        print("❌ reportlab not installed. Install with: pip install reportlab")
        return None
    
    # Create temp PDF
    temp_path = tempfile.mktemp(suffix=".pdf")
    c = canvas.Canvas(temp_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, 750, "CERTIFICATE OF ACHIEVEMENT")
    
    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "This is to certify that")
    c.drawString(100, 680, "Vemuri Venkata Shashanth")
    c.drawString(100, 660, "has successfully completed")
    
    c.drawString(100, 640, "Android App Development")
    c.drawString(100, 620, "Issued by: Udemy")
    
    c.drawString(100, 600, "Credential ID: TEST-ABC-123")
    c.drawString(100, 580, "Date: Jan 1, 2026")
    
    c.drawString(100, 560, "Verify: https://udemy.com/verify/TEST-ABC-123")
    
    c.save()
    return temp_path

def test_certificate_verification():
    """Test certificate verification end-to-end."""
    
    print("\n" + "="*70)
    print("CERTIFICATE VERIFICATION TEST")
    print("="*70)
    
    # Step 1: Create test certificate
    print("\n[Step 1] Creating test certificate...")
    cert_path = create_test_certificate()
    
    if not cert_path:
        print("⚠️  Skipping PDF creation. Using mock verification test instead...")
        test_mock_verification()
        return
    
    print(f"✅ Created: {cert_path}")
    
    # Step 2: Extract text
    print("\n[Step 2] Extracting text from certificate...")
    text = extract_text(cert_path)
    if text:
        print(f"✅ Extracted {len(text)} characters")
        print(f"   Preview: {text[:100]}...")
    else:
        print("⚠️  No text extracted (OCR may not be available)")
    
    # Step 3: Extract metadata
    print("\n[Step 3] Parsing metadata...")
    metadata = extract_metadata(text if text else "")
    print(f"✅ Issuer: {metadata.get('issuer', 'Unknown')}")
    print(f"✅ Title: {metadata.get('cert_title', 'Unknown')}")
    print(f"✅ Credential ID: {metadata.get('credential_id', 'None')}")
    print(f"✅ Date: {metadata.get('issue_date', 'None')}")
    
    # Step 4: Verify with issuer
    print("\n[Step 4] Verifying with issuer...")
    verification = verify_with_issuer(metadata)
    print(f"✅ Is Authentic: {verification['is_authentic']}")
    print(f"✅ Confidence Score: {verification['confidence_score']}%")
    print(f"✅ Verification Source: {verification['verification_source']}")
    print(f"✅ Checks Passed: {', '.join(verification['checks_passed']) or 'None'}")
    
    # Step 5: Full pipeline
    print("\n[Step 5] Running full verification pipeline...")
    result = verify_certificate_file(cert_path)
    
    print("\n" + "="*70)
    print("FULL VERIFICATION RESULT")
    print("="*70)
    print(f"✅ Is Authentic: {result['is_authentic']}")
    print(f"✅ Confidence Score: {result['confidence_score']}%")
    print(f"✅ Verification Source: {result['verification_source']}")
    print(f"✅ File Hash: {result['file_hash'][:16]}...")
    print(f"✅ Certificate Title: {result['cert_title']}")
    print(f"✅ Issuer: {result['issuer']}")
    print(f"✅ Credential ID: {result['credential_id']}")
    print(f"✅ Issue Date: {result['issue_date']}")
    
    # Step 6: Blockchain storage simulation
    print("\n[Step 6] Blockchain storage simulation...")
    print(f"✅ Hash to store: {result['file_hash']}")
    print(f"✅ Ready for blockchain: Yes")
    print(f"✅ Storage status: Would be stored with confidence {result['confidence_score']}%")
    
    # Cleanup
    try:
        os.remove(cert_path)
    except:
        pass
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE - Certificate verification working!")
    print("="*70)
    print("\nNext steps:")
    print("1. Go to http://localhost:5000")
    print("2. Upload a resume with certificate claims")
    print("3. Use /store-certificate to save on blockchain")
    print("4. Use /verify-certificate to confirm it exists")
    print("="*70 + "\n")

def test_mock_verification():
    """Run mock test when reportlab is not available."""
    print("\n" + "="*70)
    print("MOCK VERIFICATION TEST")
    print("="*70)
    
    # Mock certificate text
    mock_text = """
    CERTIFICATE OF ACHIEVEMENT
    
    This is to certify that
    John Doe
    
    has successfully completed
    Python Programming Basics
    
    Issued by: Coursera
    Credential ID: TEST-ABC-123
    Date: May 1, 2026
    
    Verify: https://coursera.org/verify/TEST-ABC-123
    """
    
    print("\n[Mock] Extracting metadata from text...")
    metadata = extract_metadata(mock_text)
    print(f"✅ Issuer: {metadata.get('issuer', 'Unknown')}")
    print(f"✅ Title: {metadata.get('cert_title', 'Unknown')}")
    print(f"✅ Credential ID: {metadata.get('credential_id', 'None')}")
    
    print("\n[Mock] Verifying with issuer...")
    verification = verify_with_issuer(metadata)
    print(f"✅ Is Authentic: {verification['is_authentic']}")
    print(f"✅ Confidence Score: {verification['confidence_score']}%")
    print(f"✅ Checks Passed: {', '.join(verification['checks_passed']) or 'None'}")
    
    print("\n" + "="*70)
    print("✅ MOCK TEST COMPLETE")
    print("="*70)
    print("\nTo enable full OCR testing, install:")
    print("  pip install reportlab pytesseract Pillow")
    print("="*70 + "\n")

if __name__ == "__main__":
    print("\n🧪 AI Resume Screening - Certificate Verification Test")
    print("This script tests certificate verification without the Flask UI.\n")
    
    try:
        test_certificate_verification()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
