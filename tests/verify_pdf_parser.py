import os
import sys
import io
from unittest.mock import MagicMock, patch

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.services.parsers import PDFParser

def run_pdf_parser_tests():
    print("=" * 80)
    print("RUNNING PDF PARSER UNIT TESTS")
    print("=" * 80)

    # 1. Test PDF parsing with valid pages
    parser = PDFParser()
    
    mock_page_1 = MagicMock()
    mock_page_1.extract_text.return_value = "Page 1 Content Text"
    mock_page_2 = MagicMock()
    mock_page_2.extract_text.return_value = "Page 2 Content Text"
    
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page_1, mock_page_2]
    
    with patch("backend.services.parsers.pypdf.PdfReader", return_value=mock_reader):
        dummy_stream = io.BytesIO(b"%PDF-1.4 mock content")
        result = parser.parse(dummy_stream)
        assert "Page 1 Content Text" in result
        assert "Page 2 Content Text" in result
        print("✓ PDF page text extraction verified.")

    # 2. Test corrupted PDF exception handling
    with patch("backend.services.parsers.pypdf.PdfReader", side_effect=Exception("Corrupted PDF structure")):
        try:
            parser.parse(io.BytesIO(b"bad bytes"))
            assert False, "Failed: Should have raised ValueError for corrupted PDF"
        except ValueError as err:
            assert "Failed to parse PDF document" in str(err)
            print("✓ Corrupted PDF parsing exception handled correctly.")

    print("\n✓ ALL PDF PARSER UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_pdf_parser_tests()
