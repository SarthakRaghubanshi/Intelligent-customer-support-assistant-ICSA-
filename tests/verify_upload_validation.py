import os
import sys
import io

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.services.ingestion_service import DocumentIngestionService, IngestionValidationError

def run_upload_validation_tests():
    print("=" * 80)
    print("RUNNING UPLOAD VALIDATION GATES TESTS")
    print("=" * 80)

    # 1. Size Validation Gate (>10MB limit)
    over_limit_data = b"x" * (10 * 1024 * 1024 + 1)
    over_limit_stream = io.BytesIO(over_limit_data)
    try:
        DocumentIngestionService.validate_and_parse(over_limit_stream, "test.pdf")
        assert False, "Failed: Allowed file size over 10MB limit"
    except IngestionValidationError as e:
        assert "exceeds 10MB limit" in str(e)
        print("✓ File size over limit validation gate passed.")

    # 2. Size Validation Gate (0 bytes empty content check)
    empty_stream = io.BytesIO(b"")
    try:
        DocumentIngestionService.validate_and_parse(empty_stream, "test.pdf")
        assert False, "Failed: Allowed empty (0 bytes) stream"
    except IngestionValidationError as e:
        assert "file is empty" in str(e)
        print("✓ Empty 0-byte stream validation gate passed.")

    # 3. Extension Validation Gate
    invalid_ext_stream = io.BytesIO(b"some contents")
    try:
        DocumentIngestionService.validate_and_parse(invalid_ext_stream, "forged.png")
        assert False, "Failed: Allowed unsupported file extension .png"
    except IngestionValidationError as e:
        assert "Unsupported file extension" in str(e)
        print("✓ Extension validation gate passed.")

    # 4. MIME Signature Verification (forged extension check - PDF)
    forged_pdf_stream = io.BytesIO(b"NOT A PDF content bytes")
    try:
        DocumentIngestionService.validate_and_parse(forged_pdf_stream, "fake.pdf")
        assert False, "Failed: Passed PDF without PDF magic header"
    except IngestionValidationError as e:
        assert "MIME validation failed: PDF signature mismatch" in str(e)
        print("✓ Forged PDF extension signature mismatch check passed.")

    # 5. MIME Signature Verification (forged extension check - DOCX)
    forged_docx_stream = io.BytesIO(b"NOT A DOCX zip archive")
    try:
        DocumentIngestionService.validate_and_parse(forged_docx_stream, "fake.docx")
        assert False, "Failed: Passed DOCX without PK header"
    except IngestionValidationError as e:
        assert "MIME validation failed: DOCX signature mismatch" in str(e)
        print("✓ Forged DOCX extension signature mismatch check passed.")

    print("\n✓ ALL UPLOAD VALIDATION GATES TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_upload_validation_tests()
