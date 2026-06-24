import os
import sys
import io
from unittest.mock import MagicMock, patch

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.services.parsers import DOCXParser

def run_docx_parser_tests():
    print("=" * 80)
    print("RUNNING DOCX PARSER UNIT TESTS")
    print("=" * 80)

    parser = DOCXParser()

    # 1. Test paragraph and table cell extraction
    mock_para_1 = MagicMock()
    mock_para_1.text = "Hello Paragraph 1"
    mock_para_2 = MagicMock()
    mock_para_2.text = "Hello Paragraph 2"
    
    mock_cell_1 = MagicMock()
    mock_cell_1.text = "Cell A1"
    mock_cell_2 = MagicMock()
    mock_cell_2.text = "Cell B2"
    
    mock_row_1 = MagicMock()
    mock_row_1.cells = [mock_cell_1, mock_cell_2]
    
    mock_table_1 = MagicMock()
    mock_table_1.rows = [mock_row_1]
    
    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para_1, mock_para_2]
    mock_doc.tables = [mock_table_1]
    
    with patch("backend.services.parsers.docx.Document", return_value=mock_doc):
        dummy_stream = io.BytesIO(b"PK\x03\x04 mock content")
        result = parser.parse(dummy_stream)
        assert "Hello Paragraph 1" in result
        assert "Hello Paragraph 2" in result
        assert "Cell A1 | Cell B2" in result
        print("✓ DOCX paragraph and table cell text extraction verified.")

    # 2. Test corrupted DOCX exception handling
    with patch("backend.services.parsers.docx.Document", side_effect=Exception("Zipfile corrupt format")):
        try:
            parser.parse(io.BytesIO(b"bad bytes"))
            assert False, "Failed: Should have raised ValueError for corrupted DOCX"
        except ValueError as err:
            assert "Failed to parse DOCX document" in str(err)
            print("✓ Corrupted DOCX parsing exception handled correctly.")

    print("\n✓ ALL DOCX PARSER UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_docx_parser_tests()
