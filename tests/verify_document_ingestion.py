import os
import sys
import io

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.services.ingestion_service import DocumentIngestionService
from backend.services.parsers import PDFParser, DOCXParser, CSVParser, TXTParser

def run_document_ingestion_tests():
    print("=" * 80)
    print("RUNNING DOCUMENT INGESTION SERVICE DISPATCH ROUTING TESTS")
    print("=" * 80)

    # 1. Verify parser mappings
    assert isinstance(DocumentIngestionService.PARSER_MAP["pdf"], PDFParser)
    assert isinstance(DocumentIngestionService.PARSER_MAP["docx"], DOCXParser)
    assert isinstance(DocumentIngestionService.PARSER_MAP["csv"], CSVParser)
    assert isinstance(DocumentIngestionService.PARSER_MAP["txt"], TXTParser)
    print("✓ Parser mappings verified correctly.")

    # 2. Verify whitelisted MIME keys
    assert "pdf" in DocumentIngestionService.MIME_WHITELIST
    assert "docx" in DocumentIngestionService.MIME_WHITELIST
    assert "csv" in DocumentIngestionService.MIME_WHITELIST
    assert "txt" in DocumentIngestionService.MIME_WHITELIST
    print("✓ MIME whitelists verified correctly.")

    # 3. Verify normalization rules compactor
    raw_str = "  Line 1   \n\n\n\nLine 2\twith tabs  "
    normalized = DocumentIngestionService.normalize_text(raw_str)
    assert normalized == "Line 1\n\nLine 2 with tabs", f"Got: {repr(normalized)}"
    print("✓ Text normalization rules verified correctly.")

    print("\n✓ ALL DOCUMENT INGESTION ROUTING TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_document_ingestion_tests()
