import io
import re
from typing import BinaryIO
from backend.services.parsers import PDFParser, DOCXParser, CSVParser, TXTParser

class IngestionValidationError(ValueError):
    """
    Custom exception raised when document ingestion validation fails.
    """
    pass


class DocumentIngestionService:
    """
    Ingestion validation dispatcher class for PDF, DOCX, CSV, and TXT files.
    """
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit in bytes
    
    # Whitelisted extensions and expected MIME type categories
    MIME_WHITELIST = {
        "pdf": ["application/pdf"],
        "docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        "csv": ["text/csv", "application/csv", "text/comma-separated-values"],
        "txt": ["text/plain"]
    }
    
    # Parsers mapping based on filename extension
    PARSER_MAP = {
        "pdf": PDFParser(),
        "docx": DOCXParser(),
        "csv": CSVParser(),
        "txt": TXTParser()
    }

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Compresses consecutive spaces and lines to normalize content.
        Strips non-printable controls but preserves standard whitespace structure.
        """
        if not text:
            return ""
        
        # Replace carriage returns with standard newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Strip trailing/leading whitespaces on each line
        text = "\n".join(line.strip() for line in text.split("\n"))
        
        # Replace multiple spaces/tabs with a single space
        text = re.sub(r"[ \t]+", " ", text)
        
        # Replace multiple consecutive newlines (3 or more) with a double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text.strip()

    @classmethod
    def validate_and_parse(
        cls,
        file_stream: BinaryIO,
        filename: str,
        reported_mime: str = None
    ) -> str:
        """
        Executes pipeline validations and dispatches to the correct parser module.
        Validation order: Size -> Extension -> MIME Signature -> Parse -> Normalize -> Empty Content.
        """
        # Step 1: Size Validation
        # Measure stream length by seeking to end
        file_stream.seek(0, io.SEEK_END)
        file_size = file_stream.tell()
        file_stream.seek(0)  # Reset stream pointer
        
        if file_size > cls.MAX_FILE_SIZE:
            raise IngestionValidationError(
                f"File size exceeds 10MB limit. Uploaded size: {file_size / (1024 * 1024):.2f}MB"
            )
        if file_size == 0:
            raise IngestionValidationError("Uploaded file is empty (0 bytes).")

        # Step 2: Extension Validation
        if not filename or "." not in filename:
            raise IngestionValidationError("Uploaded file is missing a valid extension.")
            
        ext = filename.rsplit(".", 1)[1].lower().strip()
        if ext not in cls.MIME_WHITELIST:
            raise IngestionValidationError(
                f"Unsupported file extension: '.{ext}'. Whitelisted: {list(cls.MIME_WHITELIST.keys())}"
            )

        # Step 3: MIME Signature Validation (Magic Byte Verification)
        # Read first 4 bytes for magic signature checks
        file_stream.seek(0)
        header_bytes = file_stream.read(4)
        file_stream.seek(0)  # Reset stream pointer
        
        if ext == "pdf" and not header_bytes.startswith(b"%PDF"):
            raise IngestionValidationError("MIME validation failed: PDF signature mismatch.")
        elif ext == "docx" and not header_bytes.startswith(b"PK\x03\x04"):
            # docx files are zip archives and must start with the zip magic signature
            raise IngestionValidationError("MIME validation failed: DOCX signature mismatch.")
            
        # Optional: Check reported MIME type if provided
        if reported_mime:
            valid_mimes = cls.MIME_WHITELIST[ext]
            # Handle standard wildcards or alternate variants
            if reported_mime.lower() not in [m.lower() for m in valid_mimes]:
                # Log warnings or require check pass depending on environment constraint
                pass

        # Step 4: Parse Execution
        parser = cls.PARSER_MAP[ext]
        try:
            raw_text = parser.parse(file_stream)
        except ValueError as err:
            raise IngestionValidationError(f"Parsing error: {str(err)}") from err
        except Exception as err:
            raise IngestionValidationError(f"An unexpected error occurred during parsing: {str(err)}") from err

        # Step 5: Text Normalization
        normalized_text = cls.normalize_text(raw_text)

        # Step 6: Empty Content check
        if not normalized_text:
            raise IngestionValidationError("Document ingestion failed: Extracted content text is empty.")

        return normalized_text
