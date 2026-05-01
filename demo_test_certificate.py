#!/usr/bin/env python
"""
TEST CERTIFICATE GENERATOR FOR EDUCATIONAL DEMONSTRATION
This script creates clearly-marked TEST certificates for mini-project demos.
Use only for educational/demonstration purposes.
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_test_certificate_pdf(candidate_name="Vemuri Venkata Shashanth", output_path=None):
    """Create a TEST certificate PDF that passes verification."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.colors import HexColor
    except ImportError:
        print("❌ reportlab not installed. Install with: pip install reportlab")
        return None
    
    if not output_path:
        output_path = f"test_cert_{candidate_name.replace(' ', '_')}.pdf"
    
    c = canvas.Canvas(output_path, pagesize=letter)
    
    # Red "TEST ONLY" banner at top
    c.setFillColor(HexColor("#FF0000"))
    c.rect(50, 770, 500, 30, fill=1)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(300, 778, "⚠️  TEST ONLY - FOR EDUCATIONAL DEMONSTRATION ⚠️")
    
    # Reset color
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(300, 720, "CERTIFICATE OF ACHIEVEMENT")
    
    c.setFont("Helvetica", 12)
    c.drawCentredString(300, 680, "This is to certify that")
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(300, 660, candidate_name.upper())
    
    c.setFont("Helvetica", 12)
    c.drawCentredString(300, 630, "has successfully completed and demonstrated competency in")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(300, 610, "Android App Development")
    
    c.setFont("Helvetica", 11)
    c.drawCentredString(300, 580, "Course offered by")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(300, 560, "Coursera")
    
    # Details
    c.setFont("Helvetica", 10)
    c.drawString(100, 520, f"Issue Date: {datetime.now().strftime('%B %d, %Y')}")
    c.drawString(100, 500, "Credential ID: TEST-DEMO-2026-001")
    c.drawString(100, 480, "Verification URL: https://coursera.org/verify/TEST-DEMO-2026-001")
    
    # TEST MARKER
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#FF6600"))
    c.drawString(100, 460, "⚠️ This is a TEST certificate for educational demonstration purposes only.")
    c.drawString(100, 445, "Not a real credential. Created for mini-project demo.")
    
    # Footer
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#666666"))
    c.drawCentredString(300, 100, "This is a test artifact for demonstration purposes")
    c.drawCentredString(300, 85, "Created by: AI Resume Screening Mini-Project")
    
    c.save()
    return output_path

def demonstrate_verification():
    """Run full demonstration showing verification pipeline."""
    print("\n" + "="*80)
    print("AI RESUME SCREENING - CERTIFICATE VERIFICATION DEMO")
    print("Educational Demonstration for College Mini-Project")
    print("="*80)
    
    # Import verification functions
    from cert_verifier import (
        extract_text, extract_metadata, verify_with_issuer, 
        verify_certificate_file
    )
    
    # Step 1: Create test certificate
    print("\n[STEP 1] Creating TEST Certificate for Demonstration")
    print("-" * 80)
    
    cert_name = "Test_Certificate_Demo.pdf"
    cert_path = create_test_certificate_pdf("Vemuri Venkata Shashanth", cert_name)
    
    if cert_path:
        print(f"✅ Certificate created: {cert_path}")
        print(f"   Size: {os.path.getsize(cert_path)} bytes")
    else:
        print("❌ Failed to create certificate")
        return False
    
    # Step 2: Extract text
    print("\n[STEP 2] Extract Text from Certificate (OCR)")
    print("-" * 80)
    
    text = extract_text(cert_path)
    if text:
        print(f"✅ Text extracted successfully ({len(text)} characters)")
        print(f"\n📄 Extracted Content Preview:")
        print(text[:300])
    else:
        print("⚠️  Text extraction had no OCR output (system will use PDF text)")
    
    # Step 3: Parse Metadata
    print("\n[STEP 3] Parse Metadata from Certificate")
    print("-" * 80)
    
    metadata = extract_metadata(text if text else "")
    print(f"✅ Metadata Extracted:")
    print(f"   • Issuer: {metadata.get('issuer', 'Not found')}")
    print(f"   • Certificate Title: {metadata.get('cert_title', 'Not found')}")
    print(f"   • Credential ID: {metadata.get('credential_id', 'Not found')}")
    print(f"   • Issue Date: {metadata.get('issue_date', 'Not found')}")
    print(f"   • Candidate Name: {metadata.get('candidate_name', 'Not found')}")
    
    # Step 4: Verify with Issuer
    print("\n[STEP 4] Verify Certificate with Issuer Database")
    print("-" * 80)
    
    verification = verify_with_issuer(metadata)
    print(f"✅ Verification Results:")
    print(f"   • Is Authentic: {verification['is_authentic']}")
    print(f"   • Confidence Score: {verification['confidence_score']}%")
    print(f"   • Verification Source: {verification['verification_source']}")
    print(f"   • Checks Passed:")
    for check in verification['checks_passed']:
        print(f"      ✓ {check}")
    
    # Step 5: Full Pipeline
    print("\n[STEP 5] Run Full Verification Pipeline")
    print("-" * 80)
    
    result = verify_certificate_file(cert_path)
    
    print(f"✅ Full Pipeline Results:")
    print(f"   • Is Authentic: {result['is_authentic']}")
    print(f"   • Confidence Score: {result['confidence_score']}%")
    print(f"   • Verification Source: {result['verification_source']}")
    print(f"   • File Hash: {result['file_hash'][:32]}...")
    print(f"   • Certificate Title: {result['cert_title']}")
    print(f"   • Issuer: {result['issuer']}")
    
    # Step 6: Blockchain Storage
    print("\n[STEP 6] Blockchain Storage (Simulated)")
    print("-" * 80)
    
    print(f"✅ Certificate Ready for Blockchain:")
    print(f"   • Hash to Store: {result['file_hash']}")
    print(f"   • Candidate: Vemuri Venkata Shashanth")
    print(f"   • Status: {result['cert_title']}")
    print(f"   • Confidence: {result['confidence_score']}%")
    print(f"   • Ledger Entry: PENDING (Click 'Store Certificate' in UI)")
    
    # Summary
    print("\n" + "="*80)
    print("DEMONSTRATION SUMMARY")
    print("="*80)
    
    status = "✅ VERIFIED" if result['is_authentic'] else "❌ NOT VERIFIED"
    print(f"\nCertificate Status: {status}")
    print(f"Confidence Level: {result['confidence_score']}%")
    print(f"Pipeline Stage: Ready for Blockchain Storage")
    
    print("\n📋 What This Demo Shows:")
    print("   1. Certificate file upload & parsing")
    print("   2. Text extraction (OCR simulation)")
    print("   3. Metadata parsing (Issuer, Title, Date, ID)")
    print("   4. Issuer verification (Known institutions check)")
    print("   5. Confidence scoring algorithm")
    print("   6. Blockchain storage preparation")
    
    print("\n🎯 Next Steps in Demo:")
    print("   1. Show the Flask UI at http://localhost:5000")
    print("   2. Upload this test certificate through the interface")
    print("   3. Click 'Store Certificate' to save on blockchain")
    print("   4. Click 'Verify Certificate' to retrieve from blockchain")
    print("   5. Show the certificate in the Ledger dashboard")
    
    print("\n" + "="*80)
    print(f"\n✅ Test certificate saved as: {cert_path}")
    print("Ready for college demonstration!\n")
    
    return True

if __name__ == "__main__":
    print("\n🎓 TEST CERTIFICATE GENERATOR - EDUCATIONAL DEMO\n")
    
    try:
        success = demonstrate_verification()
        if success:
            print("\n✅ Demonstration complete!")
            print("Use the generated certificate for your college mini-project demo.\n")
        else:
            print("\n❌ Demonstration failed. Check errors above.\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
