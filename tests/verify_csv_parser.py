import os
import sys
import io

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.services.parsers import CSVParser

def run_csv_parser_tests():
    print("=" * 80)
    print("RUNNING CSV PARSER UNIT TESTS")
    print("=" * 80)

    parser = CSVParser()

    # 1. Test parsing valid CSV stream
    csv_data = b"Question,Answer\nWhat is Zone 1?,Delivery is $5\nIs it active?,Yes\n"
    stream = io.BytesIO(csv_data)
    result = parser.parse(stream)
    
    assert "Row 1: Question=What is Zone 1?, Answer=Delivery is $5" in result
    assert "Row 2: Question=Is it active?, Answer=Yes" in result
    print("✓ Valid CSV row mapping verified.")

    # 2. Test empty CSV/missing headers
    empty_csv = b""
    stream_empty = io.BytesIO(empty_csv)
    try:
        parser.parse(stream_empty)
        assert False, "Failed: Should have raised ValueError for empty CSV headers"
    except ValueError as err:
        assert "CSV is empty or missing headers" in str(err)
        print("✓ Empty CSV headers error handled correctly.")

    print("\n✓ ALL CSV PARSER UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_csv_parser_tests()
